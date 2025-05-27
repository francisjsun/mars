# usage
# url = """\
# http://mirrors.us.kernel.org/ubuntu-releases/18.04.2/ubuntu-18.04.2-live-server-amd64.iso
# """
# d = Downloader(url)
#
# d.start()
#
# d = DownloaderAsync(url)
# d.start()
# d.join()

from . import url
import threading


def _pick_downloader(src):
    # TODO
    return url.downloader


class Downloader:
    def __init__(self, src_path, dst_path=None):
        self.__downloader = _pick_downloader(src_path)
        self.__src_path = src_path
        self.__dst_path = dst_path

    def start(self):
        return self.__downloader(self.__src_path, self.__dst_path)


class AsyncDownloader(threading.Thread):
    def __init__(self, src_path, dst_path=None):
        super(AsyncDownloader, self).__init__()
        self.__Downloader = Downloader(src_path, dst_path)

    def run(self):
        d = self.__Downloader
        d.start()
