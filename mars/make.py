__doc__ = """
convenient wrapper for pycmake
"""
import pycmake.cmake as cmk
from . import misc
import re
import logging
import platform
import os
import runpy
import sys
import typing
import enum

logger = logging.getLogger(__name__)

MMK_FILE_NAME = "mmk.py"  # mmk short for mars make

ROOT_DIR = os.path.dirname(sys.argv[0])


def _get_list(potential_list) -> list:
    if potential_list is None:
        return []
    elif not isinstance(potential_list, list):
        return [potential_list]
    else:
        return potential_list


class Target:
    class Type(enum.Enum):
        INVALID = 0
        EXE = 1
        STATIC_LIB = 2
        SHARED_LIB = 3

    def __init__(
        self,
        type: Type = Type.EXE,
        source: typing.Union[None, str, list[str]] = None,
        name: typing.Union[None, str] = None,
        dependency_target: typing.Union[None, str, list[str]] = None,
        include_dir: typing.Union[None, str, list[str]] = None,
        link_lib: typing.Union[None, str, list[str]] = None,
        link_lib_dir: typing.Union[None, str, list[str]] = None,
        predefine: typing.Union[None, str, list[str]] = None,
    ):
        """
        type:str [exe, static_lib, shared_lib],
        source,
        name,
        dependency_target_name: list of dependency target names
        """
        self._type = type

        self._source_in_full_path = []
        self.add_source(_get_list(source))

        self._name = name

        self._dependency_target = _get_list(dependency_target)

        self._include_dir = _get_list(include_dir)

        self._link_lib = _get_list(link_lib)

        self._link_lib_dir = _get_list(link_lib_dir)

        self._predefine = _get_list(predefine)

        self._cmake_target_generated = False

    def add_source(self, source: typing.Union[str, list[str]]):
        if isinstance(source, str):
            self._source_in_full_path.append(
                os.path.join(Project.get_current_dir(), source)
            )
        elif isinstance(source, list):
            for s in source:
                self.add_source(s)
        else:
            logger.error(f"unknown type of source: {type(source)}")

    def generate_cmake_target(self, project):
        if self._name is None:
            self._name = project._project_name

        if self._type == Target.Type.EXE:
            cmk.add_executable(self._name, self._source_in_full_path)
        else:
            cmk.add_library(
                self._name,
                (
                    (
                        cmk.STATIC
                        if self._type == Target.Type.STATIC_LIB
                        else cmk.SHARED
                    ),
                    self._source_in_full_path,
                ),
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

        if len(self._include_dir) > 0:
            cmk.target_include_directories(self._name, self._include_dir)

        if len(self._link_lib_dir) > 0:
            cmk.target_link_directories(self._name, self._link_lib_dir)

        if len(self._link_lib) > 0:
            cmk.target_link_directories(self._name, self._link_lib)

        if len(self._predefine) > 0:
            cmk.target_compile_definitions(self._name, self._predefine)

        if len(self._dependency_target) > 0:
            cmk.target_link_libraries(self._name, self._dependency_target)
            cmk.add_dependencies(self._name, self._dependency_target)

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
        cpp_version: i.e. 20,
        language:i.e. cpp,
        project_version,
        cpp_compiler,
        target
        """

        Project._project_stack.append(self)

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

    def add_target(self, target: Target):
        target_name = target._name
        if target_name is not None:
            self._target[target_name] = target
        else:
            logger.error(
                "target name must be specified when using in add_target"
            )

        return target

    def get_target(self, target_name: str) -> typing.Union[Target, None]:
        if target_name in self._target:
            return self._target[target_name]
        else:
            logger.error(
                f"no specified target found in project: {self._project_name}, target_name: {target_name}"
            )
            return None

    _project_stack = []

    @classmethod
    def get_project(cls) -> "Project":
        return cls._project_stack[-1]

    _current_dir_stack = [ROOT_DIR]

    @classmethod
    def get_current_dir(cls):
        return cls._current_dir_stack[-1]

    def add_sub_dir(self, sub_dir: str):
        cur_dir = os.path.join(Project.get_current_dir(), sub_dir)
        mmk_path = os.path.join(cur_dir, MMK_FILE_NAME)
        if os.path.isfile(mmk_path):

            Project._project_stack.append(self)
            Project._current_dir_stack.append(os.path.join(cur_dir))
            runpy.run_path(mmk_path)
            Project._project_stack.pop()
            Project._current_dir_stack.pop()

        else:
            logger.error(f"no mmk.py found in specified sub_dir: {sub_dir}")

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
                for dt_n in t._dependency_target:
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
