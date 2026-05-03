import errno
import os
import shutil
import posixpath
from zipfile import ZipFile, ZipInfo
from contextlib import contextmanager


class ZipFileHander:
    def __init__(self, filename: str):
        # TODO: assert abs path?
        self.zipfile = ZipFile(filename, "w")
        self._dir_lists: set[str] = set()
        self._file_lists: set[str] = set()

    @classmethod
    def _list_file_parents(cls, file_path: str | os.PathLike[str]):
        assert not os.fspath(file_path).endswith("/")
        file = str(posixpath.normpath(file_path))
        assert not file.startswith("..")
        assert not file.startswith("/")

        parents = []
        parent = file
        while parent := posixpath.split(parent)[0]:
            parents.append(parent)
        return file, parents

    def _make_zipinfo(self, filename: str | os.PathLike[str], mode: int):
        filename, parents = self._list_file_parents(filename)
        if filename in self._dir_lists:
            raise FileExistsError(
                errno.EEXIST, os.strerror(errno.EEXIST), "[zip]/" + filename
            )
        if filename in self._file_lists:
            raise FileExistsError(
                errno.EEXIST, os.strerror(errno.EEXIST), "[zip]/" + filename
            )
        common = self._file_lists.intersection(parents)
        if common:
            longest = max(common, key=len)
            raise FileExistsError(
                errno.EEXIST, os.strerror(errno.EEXIST), "[zip]/" + longest
            )
        self._file_lists.add(filename)
        self._dir_lists.update(parents)

        info = ZipInfo(filename)
        info.external_attr = (mode & 0xFFFF) << 16
        return info

    @contextmanager
    def open(
        self, filename: str | os.PathLike[str], flag: str = "w", mode: int = 0o644
    ):
        info = self._make_zipinfo(filename, mode)
        with self.zipfile.open(info, flag) as f:
            yield f

    def write_file(
        self, dst: str | os.PathLike[str], src: str | os.PathLike[str]
    ) -> None:
        with open(src, "rb") as f:
            info = self._make_zipinfo(dst, os.stat(src).st_mode)
            with self.zipfile.open(info, "w") as zf:
                shutil.copyfileobj(f, zf)

    def write_str(
        self, dst: str | os.PathLike[str], content: str, mode: int = 0o644
    ) -> None:
        info = self._make_zipinfo(dst, mode)
        with self.zipfile.open(info, "w") as zf:
            zf.write(content.encode())

    def close(self):
        self.zipfile.close()
