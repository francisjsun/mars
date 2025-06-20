import urllib.request
import sys
import numbers
import os
import os.path
import logging


logger = logging.getLogger(__name__)


def _fancy_bytes_format(size_in_b):
    if not isinstance(size_in_b, int):
        return
    KB = 1024
    MB = 1024 * KB
    G = 1024 * MB
    unit, scale = "B", size_in_b
    if size_in_b > G:
        unit = "G"
        scale = size_in_b / G
    elif size_in_b > MB:
        unit = "MB"
        scale = size_in_b / MB
    elif size_in_b > KB:
        unit = "KB"
        scale = size_in_b / KB
    return "{0:06.2f} {1}".format(scale, unit)


def downloader(url, dst_path=None):
    url = url.strip()
    if len(url) == 0:
        return None

    if dst_path is None:
        dst_path = url.split("/")[-1]
    elif dst_path != "":
        # make dir if not exists
        filename = os.path.basename(dst_path)
        dst_dir = os.path.dirname(dst_path)
        if os.path.isdir(dst_path):
            dst_dir = dst_path
            filename = url.split("/")[-1]
        else:
            if not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)
        dst_path = os.path.join(dst_dir, filename)
    else:
        return None

    if dst_path is None or dst_path == "":
        return None

    # open url
    with urllib.request.urlopen(url) as response:
        # info of file
        content_len = int(response.getheader("Content-Length"))
        logger.info(
            "file @name: {0}, @size: {1}".format(
                dst_path, _fancy_bytes_format(content_len)
            )
        )
        # download procedure
        sizeOfWritten = 0
        tmp_file_name = dst_path + ".tmp"
        with open(tmp_file_name, "wb") as f:
            for i in range(0, content_len, 1024):
                # data[0:1024] = response.read(1024)
                data = response.read(1024)
                sizeOfWritten += len(data)
                f.write(data)
                sys.stdout.write(
                    "@size: {0}\r".format(_fancy_bytes_format(sizeOfWritten))
                )
                sys.stdout.flush()

            f.flush()
            f.close()
            if os.path.isfile(dst_path):
                os.remove(dst_path)
            os.rename(tmp_file_name, dst_path)
            sys.stdout.flush()
            return dst_path
