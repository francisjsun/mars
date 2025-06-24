from . import misc
import shutil
import tarfile
import zipfile
import enum
from . import smart_list as sl
import os


class PkgType(enum.Enum):
    INVALID = 0
    FLODER = 1
    TAR = 2
    ZIP = 3


HEADER_EXT = ["h"]

LIB_EXT = ["a", "lib", "dll"]


def pkg(
    *,
    pkg_dir: str,
    pkg_name: str,
    include_dir: sl.SmartList,
    lib_dir: sl.SmartList,
    pkg_type: PkgType = PkgType.FLODER
):

    pkg_dir = os.path.join(pkg_dir, pkg_name)
    if os.path.isdir(pkg_dir):
        shutil.rmtree(pkg_dir)
    else:
        os.mkdir(pkg_dir)
    # copy files to pkg_dir
    header = []
    lib = []
    for d in sl.get_list(include_dir):
        header.extend(misc.find_files_in_dir_with_extensions(d, HEADER_EXT))
    for d in sl.get_list(lib_dir):
        lib.extend(misc.find_files_in_dir_with_extensions(d, LIB_EXT))

    # if PkgType not folder, continue
    if pkg_type == PkgType.FLODER:
        return
    else:
        if pkg_type == PkgType.TAR:
            pkg_path = pkg_name + ".tar.xz"
            if os.path.isfile(pkg_path):
                os.remove(pkg_path)
            with tarfile.open(pkg_path, "x:xz") as f:
                f.add(pkg_dir)
        elif pkg_type == PkgType.ZIP:
            pkg_path = pkg_name + ".zip"
            if os.path.isfile(pkg_path):
                os.remove(pkg_path)
            with zipfile.ZipFile(pkg_path, "w") as f:
                # TODO
                pass
