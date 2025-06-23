__doc__ = """
convenient wrapper for pycmake
"""
import pycmake.cmake as cmk
from . import misc
import re
import logging
import platform

logger = logging.getLogger(__name__)


class Target:

    def __init__(self, **kwargs):
        """
        type:[exe, static_lib, shared_lib],
        source,
        name,
        dependency_target_name: list of dependency target names
        """
        self._type = kwargs.get("type", "exe")

        self._source = kwargs.get("source", [])

        self._name = kwargs.get("name")

        self._dependency_target_name = [
            dt_n for dt_n in kwargs.get("dependency_target_name", [])
        ]

        self._cmake_target_generated = False

    def generate_cmake_target(self, project):
        if self._name is None:
            self._name = project._project_name

        if self._type == "exe":
            cmk.add_executable(self._name, self._source)
        else:
            cmk.add_library(
                self._name,
                (cmk.STATIC if self._type == "static_lib" else cmk.SHARED),
            )

        cpp_version_compiler_option = "-std=c++" + project._cpp_version
        if project._cpp_compiler == "msvc":
            cpp_version_compiler_option = "/std:c++" + project._cpp_version
        cmk.target_compile_options(
            self._name, cmk.PRIVATE, cpp_version_compiler_option
        )

        cpp_additional_compiler_options = (
            "-Wall -Wextra -Wconversion -pedantic"
        )
        if project._cpp_compiler == "msvc":
            cpp_additional_compiler_options = "/WX /Zc:preprocessor"

        cmk.target_compile_options(
            self._name, cmk.PRIVATE, cpp_additional_compiler_options
        )

        cmk.target_link_libraries(self._name, self._dependency_target_name)
        cmk.add_dependencies(self._name, self._dependency_target_name)

        self._cmake_target_generated = True


class Project:
    DEFAULT_CPP_VERSION = "20"

    @staticmethod
    def get_pycmake_language(language: str):
        pycmake_language = None
        if language == "cpp":
            pycmake_language = cmk.CXX
        elif language == "swift":
            pycmake_language = cmk.SWIFT
        elif language == "objcxx":
            pycmake_language = cmk.OBJCXX

        return pycmake_language

    @staticmethod
    def get_default_cpp_compiler():
        sys_name = platform.system()
        cpp_compiler = "clang"
        if sys_name == "Windows":
            cpp_compiler = "msvc"
        elif sys_name == "Linux":
            cpp_compiler = "gcc"
        return cpp_compiler

    def __init__(self, project_name, **kwargs) -> None:
        """
        kwargs consists of cmake_version,
        cpp_version: i.e. 17,
        language:i.e. cpp,
        project_version,
        cpp_compiler,
        target
        """
        self._project_name = project_name
        cmake_version = kwargs.get("cmake_version")
        if cmake_version is None:
            # use cmake --version
            ret_int, ret_str = misc.run_cmd("cmake --version")
            if ret_int == 0:
                ret_ws = ret_str.split(" ")
                ver = re.search(r"[0-9]+\.[0-9]+\.[0-9]+", ret_str)
                if ver is not None:
                    cmake_version = ver.group(0)

        if cmake_version is None:
            logger.error("cmake_version is not specified")
            return

        self._cmake_version = cmake_version

        self._cpp_version = kwargs.get(
            "cpp_version", Project.DEFAULT_CPP_VERSION
        )

        language = kwargs.get("language", ["cpp"])
        self._language = [Project.get_pycmake_language(l) for l in language]

        self._project_version = kwargs.get("project_version", "0.1.0")

        self._cpp_compiler = kwargs.get(
            "cpp_compiler", Project.get_default_cpp_compiler()
        )

        self._target = dict()
        if "target" in kwargs:
            target = kwargs.get("target")
            if target is not None:
                if target._name is None:
                    target._name = self._project_name
                self._target[target._name] = target

    def add_target(self, target):
        target_name = target._name
        if target_name is not None:
            self._target[target_name] = target
        else:
            logger.error(
                "target name must be specified when using in add_target"
            )

    def get_target(self, target_name):
        if target_name in self._target:
            return self._target[target_name]
        else:
            logger.error(
                f"no specified target found, target_name: {target_name}"
            )
            return None

    def generate_cmake(self):
        cmk.cmake_minimum_required(cmk.VERSION, self._cmake_version)
        cmk.project(
            self._project_name,
            cmk.VERSION,
            self._project_version,
            cmk.LANGUAGES,
            self._language,
        )

        # add cmake target according to topological order of dependency graph
        count_of_target_generated = 0
        while count_of_target_generated < len(self._target):

            for t in list(self._target.values()):
                if t._cmake_target_generated:
                    continue
                has_unresolved_dep = False
                for dt_n in t._dependency_target_name:
                    dep_t = self._target[dt_n]
                    if not dep_t._cmake_target_generated:
                        # still has dependency not being resolved
                        has_unresolved_dep = True
                        break
                if has_unresolved_dep:
                    # continue to try next one
                    continue
                else:
                    t.generate_cmake_target(self)
                    count_of_target_generated += 1
