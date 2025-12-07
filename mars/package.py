from . import misc
import shutil
import tarfile
import zipfile
import enum
from . import smart_list as sl
import os
import logging
import typing

logger = logging.getLogger(__name__)


class PkgType(enum.Enum):
    INVALID = 0
    FLODER = 1
    TAR = 2
    ZIP = 3

    @classmethod
    def get_type(cls, type_str: str):
        if type_str == "folder":
            return cls.FLODER
        elif type_str == "tar":
            return cls.TAR
        elif type_str == "zip":
            return cls.ZIP
        else:
            return cls.INVALID


HEADER_EXT = ["h"]

LIB_EXT = ["a", "lib", "dll"]


def pkg(
    *,
    pkg_dir: str,
    pkg_name: str,
    include_dir: str,
    lib_dir: typing.Union[
        None, str
    ],  # lib_dir could be None when it's a HEADER_ONLY target
    pkg_type: PkgType = PkgType.FLODER,
):

    logger.info(f"packaging {pkg_name} ...")

    pkg_dir = os.path.join(os.path.abspath(pkg_dir), pkg_name)

    if os.path.isfile(pkg_dir):
        logger.error(f"pkg_dir is a file: {pkg_dir}")
        return

    if os.path.isdir(pkg_dir):
        shutil.rmtree(pkg_dir)

    os.makedirs(pkg_dir)

    # copy files to pkg_dir
    header = misc.find_files_in_dir_with_extensions(include_dir, HEADER_EXT)
    lib = []
    if lib_dir is not None:
        lib = misc.find_files_in_dir_with_extensions(lib_dir, LIB_EXT)

    # copy fiiles to pkg_dir, note! header dir should also contain the pkg_name at the end
    dst_header_dir = os.path.join(pkg_dir, "include", pkg_name)
    for h in header:
        logger.info(f"copying {h}")
        misc.copy_file_with_dir_structure(h, include_dir, dst_header_dir)

    if lib_dir is not None:
        dst_lib_dir = os.path.join(pkg_dir, "lib")
        for l in lib:
            logger.info(f"copying {l}")
            misc.copy_file_with_dir_structure(l, lib_dir, dst_lib_dir)

    # if PkgType not folder, continue
    if pkg_type != PkgType.FLODER:
        if pkg_type == PkgType.TAR:
            pkg_path = pkg_name + ".tar.xz"
            if os.path.isfile(pkg_path):
                os.remove(pkg_path)

            logger.info(f"packaging to {pkg_path}")
            with tarfile.open(pkg_path, "x:xz") as f:
                f.add(pkg_dir)
        elif pkg_type == PkgType.ZIP:
            pkg_path = pkg_name + ".zip"
            if os.path.isfile(pkg_path):
                os.remove(pkg_path)

            logger.info(f"packaging to {pkg_path}")
            with zipfile.ZipFile(pkg_path, "w") as f:
                # TODO
                pass

    logger.info(f"end of packaging: {os.path.abspath(pkg_dir)}")
