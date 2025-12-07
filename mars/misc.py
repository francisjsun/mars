import os
import logging
import re
import subprocess
import shutil
import enum
import argparse
import typing
import platform

logger = logging.getLogger(__name__)

arg_parser = argparse.ArgumentParser(description=__doc__)


class MEnum(enum.Enum):
    @classmethod
    def _get_map_from_str_to_enum(cls, map_str_to_enum) -> dict:
        if not hasattr(cls, "MAP_STR_TO_ENUM"):
            cls.MAP_STR_TO_ENUM = map_str_to_enum

        return cls.MAP_STR_TO_ENUM

    @classmethod
    def get_map_from_enum_to_str(cls) -> dict:
        if not hasattr(cls, "MAP_ENUM_TO_STR"):
            cls.MAP_ENUM_TO_STR = {}
            for k, v in cls.MAP_STR_TO_ENUM.items():
                cls.MAP_ENUM_TO_STR[v] = k

        return cls.MAP_ENUM_TO_STR

    def __str__(self):
        # the MAP_STR_TO_ENUM stores in derived class
        return type(self).get_map_from_enum_to_str()[self]


class TargetOS(MEnum):
    INVALID = 0
    MACOS = 1
    IOS = 2
    WIN = 3
    ANDROID = 4
    LINUX = 5
    IOS_SIMULATOR = 6

    @classmethod
    def get_map_from_str_to_enum(cls) -> dict:
        return super()._get_map_from_str_to_enum(
            {
                "macos": cls.MACOS,
                "Darwin": cls.MACOS,
                "ios": cls.IOS,
                "win": cls.WIN,
                "Windows": cls.WIN,
                "android": cls.ANDROID,
                "linux": cls.LINUX,
                "Linux": cls.LINUX,
                "ios-sim": cls.IOS_SIMULATOR,
            }
        )

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


arg_parser.add_argument(
    "--target-os",
    action="store",
    dest="target_os",
    default=os.uname()[0],
    help=f"specify the building target os, must be one of {[ os_name for os_name in TargetOS.get_map_from_str_to_enum().keys()]}",
)


class TargetABI(MEnum):
    INVALID = 0
    ARM64_V8A = 1
    X86 = 2

    @classmethod
    def get_map_from_str_to_enum(cls):
        return super()._get_map_from_str_to_enum(
            {
                "arm64-v8a": cls.ARM64_V8A,
                "arm64": cls.ARM64_V8A,
                "x86": cls.X86,
            }
        )


arg_parser.add_argument(
    "--target-abi",
    action="store",
    dest="target_abi",
    default=os.uname()[4],
    help=f"specify the building target abi, must be one of {[ abi_name for abi_name in TargetABI.get_map_from_str_to_enum().keys()]}",
)


def find_files_in_dir_with_extensions(
    dir,
    extensions=None,
    recursively=True,
    excluding_dirs="(.*" + os.sep + ")*\\..*",  # exclude hidden dir by default
):
    """
    Find all files in the given dir with specified extensions.
    extensions and excluding_dirs support regular expressions.
    """
    ret_files = []

    if not isinstance(dir, str):
        logger.error("dir must be a str")
        return ret_files

    if not isinstance(extensions, list) and not isinstance(extensions, str):
        logger.error("extensions must be either a list or str")
        return ret_files

    if not isinstance(excluding_dirs, list) and not isinstance(
        excluding_dirs, str
    ):
        logger.error("excluding_dirs must be either a list or str")
        return ret_files

    if not isinstance(extensions, list):
        extensions = [extensions]
    if not isinstance(excluding_dirs, list):
        excluding_dirs = [excluding_dirs]

    # build regular expressions for extensions and excluding_dirs
    extensions_re = []
    for e in extensions:
        extensions_re.append(re.compile(e))

    excluding_dirs_re = []
    # escape regular expression special characters
    dir_re_compatible = ""
    for c in dir:
        if c != ".":
            dir_re_compatible += c
        else:
            dir_re_compatible += "\\."
    for ed in excluding_dirs:
        excluding_dirs_re.append(
            re.compile(os.path.join(dir_re_compatible, ed))
        )  # needs full path here for later matching

    for dir_path, dirs, files in os.walk(dir):
        dirs_to_be_rm = []
        for d in dirs:
            dir_full_path = os.path.join(dir_path, d)
            for ed_re in excluding_dirs_re:
                if ed_re.match(dir_full_path):
                    dirs_to_be_rm.append(d)

        for d in dirs_to_be_rm:
            dirs.remove(d)

        if not extensions:
            for f in files:
                ret_files.extend(os.path.join(dir_path, f))
        else:
            for f in files:
                f_ext = f.split(".")[-1]
                for e_re in extensions_re:
                    if e_re.match(f_ext):
                        ret_files.append(os.path.join(dir_path, f))

        if not recursively:
            break

    return ret_files


def run_cmd(
    cmd,
    *,
    capture_output: bool = False,
    working_dir: typing.Union[None, str] = None,
):
    lst_cmd = cmd
    if isinstance(cmd, str):
        lst_cmd = cmd.split(" ")
    elif isinstance(cmd, list):
        lst_cmd = cmd
    else:
        logger.error(f"wrong type of cmd {type(cmd)}")

    ret = subprocess.run(
        lst_cmd,
        capture_output=capture_output,
        text=capture_output,
        cwd=working_dir,
    )
    return ret.returncode, (
        ret.stdout[:-1]
        if ret.stdout is not None and ret.stdout[-1] == "\n"
        else ret.stdout
    )


def copy_file_with_dir_structure(
    src_file: str, src_dir_start: str, dst_dir_start: str
):
    h_dir = os.path.dirname(src_file)
    intermediate_dir = os.path.relpath(h_dir, src_dir_start)
    dst_dir = os.path.join(dst_dir_start, intermediate_dir)
    if not os.path.isdir(dst_dir):
        if os.path.isfile(dst_dir):
            logger.error(f"dst_dir is a file: {dst_dir}")
            return
        os.makedirs(dst_dir)
    shutil.copy(src_file, dst_dir)
