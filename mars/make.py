__doc__ = """
convenient wrapper for pycmake
"""
import pycmake.cmake as cmk


class Make:
    def __init__(self, proj_name) -> None:
        self._proj_name = proj_name
