import os
import logging
import re
import subprocess

_logger = logging.getLogger(__name__)


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
        _logger.error("dir must be a str")
        return ret_files

    if not isinstance(extensions, list) and not isinstance(extensions, str):
        _logger.error("extensions must be either a list or str")
        return ret_files

    if not isinstance(excluding_dirs, list) and not isinstance(excluding_dirs, str):
        _logger.error("excluding_dirs must be either a list or str")
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


def run_cmd(cmd):
    lst_cmd = cmd
    if isinstance(cmd, str):
        lst_cmd = cmd.split(" ")
    elif isinstance(cmd, list):
        lst_cmd = cmd
    else:
        _logger.error(f"wrong type of cmd {type(cmd)}")

    ret = subprocess.run(lst_cmd, capture_output=True, text=True)
    return ret.returncode, ret.stdout[:-1] if ret.stdout[-1] == "\n" else ret.stdout
