# Copyright (C) 2020 Francis Sun, all rights reserved.

"""
DepInfo: dependency data , src_path supports git repository address which
may have a form repository_addr[?revision], dst_dir is relative to cwd
DepMethod: a wrapper of a function with addtional __seq_num member
DepSolution: a container of DepMethod
Dependency: map a DepInfo to a DepSolution
"""
from . import downloader
import tarfile
import os
import sys
import stat
import subprocess
import shutil
import logging
import argparse
import runpy


logger = logging.getLogger(__name__)

arg_parser = argparse.ArgumentParser(description=__doc__)
arg_parser.add_argument(
    "-l", "--local", action="store_true", dest="local", help="Use local repository"
)
arg_parser.add_argument(
    "-d", "--dirty", action="store_true", dest="dirty", help="Use dirty local"
)
args = arg_parser.parse_args()


class DepInfo:
    def __init__(self, dep_info):
        self.src_path = dep_info["src_path"].strip()
        self.dst_dir = dep_info.get("dst_dir", None)
        self.seq_num = dep_info.get("seq_num", 0)
        self.last_dep_method_ret = None
        self.dst_abs_path = None
        self.cache = None

    def __lt__(self, other):
        return self.seq_num < other.seq_num

    def __str__(self):
        return "{{ src_path: {}, dst_dir: {}, seq_num: {}}}".format(
            self.src_path, self.dst_dir, self.seq_num
        )


def _fixer_download(dep_info):
    if dep_info.cache is None:
        d = downloader.Downloader(dep_info.src_path, dep_info.dst_dir)
        ret_file = d.start()
        if ret_file == None:
            return
        logger.info("dependency @name: {0} has been downloaded.".format(ret_file))
        dep_info.last_dep_method_ret = ret_file
        dep_info.dst_abs_path = os.path.abspath(ret_file)
    else:
        dep_info.last_dep_method_ret = dep_info.cache


def _process_git_url(url):
    REV_INDICATOR = "?"
    src_info = url.split(REV_INDICATOR)
    src_path = src_info[0]
    if len(src_info) > 1:
        rev = src_info[1]
    else:
        raise RuntimeError("No rev was found in @src_path: " + url)

    dep_name = src_path.split("/")[-1].split(".")[0]
    if dep_name is None or dep_name == "":
        raise RuntimeError("dep_name is either None or empty @src_path: " + src_path)
    return src_path, rev, dep_name


def _fixer_fs_git_proj_download_method(dep_info):
    old_cwd = os.getcwd()
    if not os.path.isdir("dep_tmp"):
        os.mkdir("dep_tmp")
    os.chdir("dep_tmp")

    src_path, rev, dep_name = _process_git_url(dep_info.src_path)

    def get_fixed_dst_dir():
        if dep_info.dst_dir is None:
            dst_dir = old_cwd
        else:
            dst_dir = dep_info.dst_dir

        # append dep_name to dst_dir
        return os.path.join(dst_dir, dep_name)

    if dep_info.cache is not None:
        dep_info.last_dep_method_ret = dep_info.cache
        dep_info.dst_dir = get_fixed_dst_dir()
        os.chdir(old_cwd)
        return

    if os.path.isdir(dep_name):
        os.chdir(dep_name)  # cd to target dir
        if not args.dirty:  # want a clean version
            if not args.local:  # want update from remote
                subprocess.run(["git", "fetch", "-f", "origin", "{0}".format(rev)])
            subprocess.run(["git", "reset", "--hard", "origin/" + rev])
    else:
        # clone git repository
        subprocess.run(["git", "clone", "-b", rev, "--single-branch", src_path])
        os.chdir(dep_name)

    if os.path.isfile("setup.py"):
        sys.path.insert(0, os.getcwd())
        new_setup_py_path = os.path.join(os.getcwd(), "setup.py")
        runpy.run_path(new_setup_py_path, run_name="__main__")

    if os.path.isfile("vesta/build.py"):
        # build a pkg tar file
        shutil.copy("vesta/build.py", ".")
        subprocess.run([sys.executable, "build.py", "-p"])

        # set last_dep_method_ret for next step
        dep_info.last_dep_method_ret = os.path.abspath(dep_name + ".tar.xz")
    else:
        dep_info.dst_dir = get_fixed_dst_dir()
        dep_info.last_dep_method_ret = os.getcwd()

    dep_info.dst_abs_path = dep_info.last_dep_method_ret
    os.chdir(old_cwd)


def _fixer_copy(dep_info):
    # rm dst_dir if it exists
    def rmtree_onerror(func, path, excinfo):
        os.chmod(path, stat.S_IWUSR)
        func(path)

    if os.path.isdir(dep_info.dst_dir):
        shutil.rmtree(dep_info.dst_dir, onerror=rmtree_onerror)
    # copy
    shutil.copytree(dep_info.last_dep_method_ret, dep_info.dst_dir)


def _fixer_extract(dep_info):
    tar_file_path = dep_info.last_dep_method_ret
    if tar_file_path is None:
        return
    if dep_info.dst_dir is None:
        dst_dir = os.getcwd()
    else:
        dst_dir = dep_info.dst_dir

    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)

    if tarfile.is_tarfile(tar_file_path):
        with tarfile.open(tar_file_path) as f:
            old_cwd = os.getcwd()
            os.chdir(dst_dir)
            f.extractall()
            os.chdir(old_cwd)
            logger.info(
                """\
dependency @name: {0} has been extracted into @dst_dir: {1}.""".format(
                    tar_file_path, dst_dir
                )
            )
    else:
        raise


class DepSolution:
    def __init__(self, *dep_methods):
        if dep_methods is None:
            raise
        self.__dep_methods = {}
        for dm in dep_methods:
            if not isinstance(dm, dict):
                raise
            self.__dep_methods[dm["seq_num"]] = dm["fixer"]

    def __call__(self, dep_info):
        sorted_dms = sorted(self.__dep_methods.items(), key=lambda kv: kv[0])
        for dm in sorted_dms:
            dm[1](dep_info)

    def add_method(self, dep_method):
        self.__dep_methods[dep_method["seq_num"]] = dep_method["fixer"]


default_dep_sln = DepSolution(
    {"seq_num": 0, "fixer": _fixer_download}, {"seq_num": 1, "fixer": _fixer_extract}
)

del default_dep_sln.add_method  # disable further adding method

fs_git_proj_dep_sln = DepSolution(
    {"seq_num": 0, "fixer": _fixer_fs_git_proj_download_method},
    {"seq_num": 1, "fixer": _fixer_extract},
)

fs_trivial_git_proj_dep_sln = DepSolution(
    {"seq_num": 0, "fixer": _fixer_fs_git_proj_download_method},
    {"seq_num": 1, "fixer": _fixer_copy},
)

del fs_git_proj_dep_sln.add_method


class Dependency:
    def __init__(self, root_dir=None):
        self.__deps = {}
        if root_dir is None:
            self.__root_dir = os.getcwd()

    def add(self, dep_info, dep_sln=None):
        if dep_sln is None:
            dep_sln = default_dep_sln
        self.__deps[dep_info] = dep_sln

    def get_solution(self, dep_info):
        return self.__deps[dep_info]

    dep_info_cache = {}

    def fix(self):
        sorted_deps = sorted(self.__deps.items(), key=lambda kv: kv[0])
        for kv in sorted_deps:
            current_dep_info = kv[0]
            logger.info("Fixing " + str(current_dep_info))
            current_src_path = current_dep_info.src_path

            # if has been cached
            if current_src_path in Dependency.dep_info_cache:
                current_dep_info.cache = Dependency.dep_info_cache[current_src_path]

            kv[1](current_dep_info)

            if current_src_path not in Dependency.dep_info_cache:
                Dependency.dep_info_cache[current_src_path] = (
                    current_dep_info.dst_abs_path
                )
