from zipfile import ZipFile, ZIP_DEFLATED
import os

class FileStorage:
    """Base file storage class"""
    def __init__(self):
        pass

    def exists(self, name):
        raise NotImplemented

    def store(self, filename, content):
        raise NotImplemented

    def close(self):
        """Default implementation. Don't do anything"""
        pass


class ZipFileStorage(FileStorage):
    def __init__(self, filename, mode='a', compression=ZIP_DEFLATED):
        FileStorage.__init__(self)
        self.mzip = ZipFile(filename, mode=mode, compression=compression)
        self.allfiles = self.mzip.namelist()
        pass

    def store(self, filename, content):
        self.mzip.writestr(filename, content)
        self.allfiles.append(filename)

    def exists(self, filename):
        if filename in self.allfiles:
            return True
        return False

    def close(self):
        self.mzip.close()

class FilesystemStorage(FileStorage):
    def __init__(self, dirpath=os.path.join('storage', 'files')):
        FileStorage.__init__(self)
        self.dirpath = dirpath
        pass

    def exists(self, filename):
        fullname = os.path.join(self.dirpath, filename)
        return os.path.exists(fullname)

    def store(self, filename, content):
        fullname = os.path.join(self.dirpath, filename)
        f = open(fullname, 'wb')
        f.write(content)
        f.close()
