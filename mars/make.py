__doc__ = """
mars make, a.k.a. mmk
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
from . import smart_list as sl
import argparse
from . import package
import shutil

logger = logging.getLogger(__name__)

MMK_FILE_NAME = "mmk.py"  # mmk short for mars make

_ROOT_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))

_DEFAULT_PACKAGE_DIR_NAME = "."  # TODO "mars_pkg"

arg_parser = argparse.ArgumentParser(description=__doc__)


class TargetOS(enum.Enum):
    INVALID = 0
    MACOS = 1
    IOS = 2
    WIN = 3
    ANDROID = 4
    LINUX = 5
    IOS_SIMULATOR = 6

    @classmethod
    def from_str(cls, os_name: str):
        if os_name == "macos" or os_name == "Darwin":
            return cls.MACOS
        elif os_name == "ios":
            return cls.IOS
        elif os_name == "ios-sim":
            return cls.IOS_SIMULATOR
        elif os_name == "win" or os_name == "Windows":
            return cls.WIN
        elif os_name == "android":
            return cls.ANDROID
        elif os_name == "linux" or os_name == "Linux":
            return cls.LINUX
        else:
            logger.error(f"unknown os_name: {os_name}")
            raise

    def is_apple_os(self):
        return (
            self == TargetOS.MACOS
            or self == TargetOS.IOS
            or self == TargetOS.IOS_SIMULATOR
        )

    def get_apple_sdk_name(self):
        return {
            TargetOS.MACOS: "macosx",
            TargetOS.IOS: "iphoneos",
            TargetOS.IOS_SIMULATOR: "iphonesimulator",
        }[self]

    def __str__(self):
        return {
            TargetOS.MACOS: "macos",
            TargetOS.IOS: "ios",
            TargetOS.WIN: "win",
            TargetOS.ANDROID: "android",
            TargetOS.LINUX: "linux",
            TargetOS.IOS_SIMULATOR: "ios-sim",
        }[self]


arg_parser.add_argument(
    "-t",
    "--target-os",
    action="store",
    dest="target_os",
    default=platform.system(),
    help="specify build target, must be one of [macos, ios, win, android, linux, ios-sim]",
)

arg_parser.add_argument(
    "-p",
    "--package",
    dest="package_type",
    default=None,
    help="package and specify packaging type: [folder|tar|zip]. i.e. -p tar",
)

args = arg_parser.parse_args()


def get_target_os() -> TargetOS:
    return TargetOS.from_str(args.target_os)


def get_apple_sdk_dir() -> str:
    if get_target_os().is_apple_os():
        return_code, apple_sdk_dir = misc.run_cmd(
            f"xcrun --sdk {get_target_os().get_apple_sdk_name()} --show-sdk-path",
            capture_output=True,
        )
        if return_code != 0:
            logger.error("failed to find apple sdk path")
            raise
        return apple_sdk_dir
    else:
        raise


class Target:
    class Type(enum.Enum):
        INVALID = 0
        HEADER_ONLY = 1
        EXE = 2
        STATIC_LIB = 3
        SHARED_LIB = 4

    class SubType(enum.Enum):
        INVALID = 0
        WIN32 = 1
        MACOSX_BUNDLE = 2

    def __init__(
        self,
        *,
        name: typing.Union[None, str] = None,
        type: Type = Type.EXE,
        sub_type: typing.Union[SubType, None] = None,
        source: sl.StrList = None,
        dependency_target: sl.StrList = None,
        include_dir: sl.StrList = None,
        system_include_dir: sl.StrList = None,
        link_lib: sl.StrList = None,
        link_lib_dir: sl.StrList = None,
        predefine: sl.StrList = None,
        compile_option: sl.StrList = None,
        link_option: sl.StrList = None,
        output_dir: typing.Union[None, str] = None,
        target_property: sl.PairList = None,
        package_header_dir_hint: typing.Union[None, str] = None,
    ):
        """
        type:str [exe, static_lib, shared_lib],
        source,
        name,
        dependency_target_name: list of dependency target names
        """
        self._type = type

        self._sub_type = sub_type

        self._source_in_full_path = []
        self.add_source(sl.get_list(source))

        self._name = name

        self._dependency_target = sl.get_list(dependency_target)

        self._include_dir = sl.get_list(include_dir)

        self._system_include_dir = sl.get_list(system_include_dir)

        self._link_lib = sl.get_list(link_lib)

        self._link_lib_dir = sl.get_list(link_lib_dir)

        self._predefine = sl.get_list(predefine)

        self._compile_option = sl.get_list(compile_option)

        self._link_option = sl.get_list(link_option)

        self._cmake_target_generated = False

        self._output_dir = output_dir

        self._target_property = sl.get_list(target_property)

        self._package_header_dir_hint = package_header_dir_hint

    def add_source(self, source: sl.StrList):
        self._source_in_full_path.extend(
            [
                os.path.join(Project.get_project().get_current_mmk_dir(), fp_s)
                for fp_s in sl.get_list(source)
            ]
        )

    def add_dependency_target(self, dependency_target: sl.StrList):
        self._dependency_target.extend(sl.get_list(dependency_target))

    def add_include_dir(
        self, include_dir: sl.StrList, is_system_header: bool = False
    ):
        if not is_system_header:
            self._include_dir.extend(sl.get_list(include_dir))
        else:
            self._system_include_dir.extend(sl.get_list(include_dir))

    def add_link_lib(self, link_lib: sl.StrList):
        self._link_lib.extend(sl.get_list(link_lib))

    def add_link_lib_dir(self, link_lib_dir: sl.StrList):
        self._link_lib_dir.extend(sl.get_list(link_lib_dir))

    def add_predefine(self, predefine: sl.StrList):
        self._predefine.extend(sl.get_list(predefine))

    def add_compile_option(self, compile_option: sl.StrList):
        self._compile_option.extend(sl.get_list(compile_option))

    def add_link_option(self, link_option: sl.StrList):
        self._link_option.extend(sl.get_list(link_option))

    def add_target_property(self, target_property: sl.PairList):
        self._target_property.extend(sl.get_list(target_property))

    def generate_cmake_target(self):
        if self._type == Target.Type.HEADER_ONLY:
            return
        if self._name is None:
            logger.error("target name not being set")
            raise

        if self._type == Target.Type.EXE:
            if self._sub_type is None:
                cmk.add_executable(self._name, self._source_in_full_path)
            elif self._sub_type == Target.SubType.WIN32:
                cmk.add_executable(
                    self._name, cmk.WIN32, self._source_in_full_path
                )
            elif self._sub_type == Target.SubType.MACOSX_BUNDLE:
                cmk.add_executable(
                    self._name, cmk.MACOSX_BUNDLE, self._source_in_full_path
                )
            else:
                logger.error(
                    f"unknown subtype: {self._sub_type} for target: {self._name}"
                )
                raise
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

        if len(self._include_dir) > 0:
            cmk.target_include_directories(
                self._name, cmk.PRIVATE, self._include_dir
            )

        if len(self._system_include_dir) > 0:
            cmk.target_include_directories(
                self._name, cmk.SYSTEM, cmk.PRIVATE, self._system_include_dir
            )

        if len(self._link_lib_dir) > 0:
            cmk.target_link_directories(
                self._name, cmk.PRIVATE, self._link_lib_dir
            )

        if len(self._link_lib) > 0:
            cmk.target_link_libraries(self._name, cmk.PRIVATE, self._link_lib)

        if len(self._predefine) > 0:
            cmk.target_compile_definitions(
                self._name, cmk.PRIVATE, self._predefine
            )

        if len(self._compile_option) > 0:
            cmk.target_compile_options(
                self._name, cmk.PRIVATE, self._compile_option
            )

        if len(self._link_option) > 0:
            cmk.target_link_options(self._name, cmk.PRIVATE, self._link_option)

        if len(self._dependency_target) > 0:
            cmk.target_link_libraries(
                self._name, cmk.PRIVATE, self._dependency_target
            )
            cmk.add_dependencies(self._name, self._dependency_target)

        if len(self._target_property) > 0:
            cmk.set_target_properties(
                self._name, cmk.PROPERTIES, self._target_property
            )

        proj = Project.get_project()
        if self._output_dir is None:
            self._output_dir = proj._output_dir

        cmk.set_target_properties(
            self._name,
            cmk.PROPERTIES,
            cmk.ARCHIVE_OUTPUT_DIRECTORY,
            self._output_dir,
            cmk.LIBRARY_OUTPUT_DIRECTORY,
            self._output_dir,
            cmk.RUNTIME_OUTPUT_DIRECTORY,
            self._output_dir,
            cmk.DEBUG_POSTFIX,
            proj._bin_debug_postfix,
        )

        self._cmake_target_generated = True

    def build(self, build_type: str):
        if self._type != Target.Type.HEADER_ONLY:
            if os.path.isdir("build"):
                shutil.rmtree("build")
            ret, _ = misc.run_cmd(
                f"cmake -DCMAKE_BUILD_TYPE={build_type} -S . -B build"
            )
            if ret == 0:
                ret, _ = misc.run_cmd(
                    f"cmake --build build --target {self._name}"
                )

            return ret

    def package(self, package_type: str):
        if (
            self._name is not None
            and self._package_header_dir_hint is not None
        ):
            package.pkg(
                pkg_dir=os.path.join(
                    Project.get_project().get_project_dir(),
                    _DEFAULT_PACKAGE_DIR_NAME,
                ),
                pkg_name=self._name,
                include_dir=self._package_header_dir_hint,
                lib_dir=self._output_dir,
                pkg_type=package.PkgType.get_type(package_type),
            )


_DEFAULT_CPP_VERSION = "17"


def _get_pycmake_language(language: str):
    pycmake_language = None
    if language == "cpp":
        pycmake_language = cmk.CXX
    elif language == "swift":
        pycmake_language = cmk.SWIFT
    elif language == "objcxx":
        pycmake_language = cmk.OBJCXX

    return pycmake_language


def _get_default_cpp_compiler():
    sys_name = platform.system()
    cpp_compiler = "clang"
    if sys_name == "Windows":
        cpp_compiler = "msvc"
    elif sys_name == "Linux":
        cpp_compiler = "gcc"
    return cpp_compiler


DEFAULT_OUTPUT_DIR = "bin"
BIN_DEBUG_POSTFIX = "d"


class Project:
    """
    each mmk can only have one Project
    """

    _THE_PROJECT = None

    def __init__(
        self,
        project_name: str,
        *,
        cmake_version: typing.Union[str, None] = None,
        cpp_version: str = _DEFAULT_CPP_VERSION,
        language: sl.StrList = "cpp",
        project_version: str = "0.1.0",
        cpp_compiler: str = _get_default_cpp_compiler(),
        target: typing.Union[Target, None] = None,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        bin_debug_postfix: str = BIN_DEBUG_POSTFIX,
        compile_option: sl.StrList = None,
        use_preset_compile_option: bool = True,
    ) -> None:
        """
        kwargs consists of cmake_version,
        cpp_version: i.e. 20,
        language:i.e. cpp,
        project_version,
        cpp_compiler,
        target
        """

        if Project._THE_PROJECT is None:
            Project._THE_PROJECT = self
        else:
            logger.error("the project has been created, cannot create more")
            raise

        self._current_mmk_dir_stack = [_ROOT_DIR]
        self._project_dir = _ROOT_DIR

        self._project_name = project_name
        if cmake_version is None:
            # use cmake --version
            ret_int, ret_str = misc.run_cmd(
                "cmake --version", capture_output=True
            )
            if ret_int == 0:
                ret_ws = ret_str.split(" ")
                ver = re.search(r"[0-9]+\.[0-9]+\.[0-9]+", ret_str)
                if ver is not None:
                    cmake_version = ver.group(0)

        if cmake_version is None:
            logger.error("cmake_version is not specified")
            return

        self._cmake_version = cmake_version

        self._cpp_version = cpp_version

        self._language = sl.get_list(language)

        self._project_version = project_version

        self._cpp_compiler = cpp_compiler

        self._target: dict[str, Target] = dict()
        if target is not None:
            if target._name is None:
                # main project could share the same name of project
                # if the name not provided
                target._name = self._project_name
            self._target[target._name] = target

        self._output_dir = os.path.join(self._project_dir, output_dir)

        self._bin_debug_postfix = bin_debug_postfix

        self._compile_option = sl.get_list(compile_option)

        self._use_preset_compile_option = use_preset_compile_option

    def add_target(self, target: Target):
        target_name = target._name
        if target_name is not None:
            self._target[target_name] = target
        else:
            logger.error(
                "target name must be specified when using in add_target"
            )

        return target

    def get_target(self, target_name: str) -> Target:
        if target_name in self._target:
            return self._target[target_name]
        else:
            logger.error(
                f"no specified target found in project: {self._project_name}, target_name: {target_name}"
            )
            raise

    @classmethod
    def get_project(cls) -> "Project":
        if cls._THE_PROJECT is not None:
            return cls._THE_PROJECT
        else:
            logger.error("the project has not been created yet")
            raise

    def get_current_mmk_dir(self):
        return self._current_mmk_dir_stack[-1]

    def get_project_dir(self):
        return self._project_dir

    def add_sub_dir(self, sub_dir: str):
        cur_dir = os.path.join(self.get_current_mmk_dir(), sub_dir)
        mmk_path = os.path.join(cur_dir, MMK_FILE_NAME)
        if os.path.isfile(mmk_path):

            self._current_mmk_dir_stack.append(os.path.join(cur_dir))
            runpy.run_path(mmk_path)
            self._current_mmk_dir_stack.pop()

        else:
            logger.error(f"no mmk.py found in specified sub_dir: {sub_dir}")
            raise

    def generate_cmake(self):
        cmk.cmake_minimum_required(cmk.VERSION, self._cmake_version)

        if get_target_os().is_apple_os():
            cmk.cmake_set(
                "CMAKE_OSX_SYSROOT", get_target_os().get_apple_sdk_name()
            )

        cmk.project(
            self._project_name,
            cmk.VERSION,
            self._project_version,
            cmk.LANGUAGES,
            [_get_pycmake_language(l) for l in self._language],
        )

        # CMAKE_CXX_FLAGS IS a cmake variable which is a string, not like target_compile_options
        proj_compile_option = []
        proj_compile_option.extend(self._compile_option)

        cpp_version_compile_option = "-std=c++" + self._cpp_version
        if self._cpp_compiler == "msvc":
            cpp_version_compile_option = "/std:c++" + self._cpp_version
        proj_compile_option.append(cpp_version_compile_option)

        if self._use_preset_compile_option:

            prefix_compile_option = "-Wall -Wextra -Wconversion -pedantic"
            if self._cpp_compiler == "msvc":
                prefix_compile_option = "/WX /Zc:preprocessor"

            proj_compile_option.extend(prefix_compile_option.split(" "))

        # cmk.add_compile_options(proj_compile_option)

        proj_compile_option = " ".join(proj_compile_option)
        cmk.cmake_set(
            cmk.CMAKE_CXX_FLAGS, "${CMAKE_CXX_FLAGS} " + proj_compile_option
        )

        if "objcxx" in self._language:
            cmk.cmake_set(
                cmk.CMAKE_OBJCXX_FLAGS,
                "${CMAKE_OBJCXX_FLAGS} " + proj_compile_option,
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
                    t.generate_cmake_target()
                    count_of_target_generated += 1

        # package
        if args.package_type != None:
            for t in self._target.values():
                if t._package_header_dir_hint is not None:
                    t.build("debug")
                    t.build("release")

                    t.package(args.package_type)
