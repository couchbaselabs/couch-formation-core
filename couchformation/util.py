##
##

import os
import logging
import uuid
import collections
import string
import random
from typing import Union
from uuid import UUID
from shutil import copyfile
from multiprocessing import Lock
from pyhostprep.command import RunShellCommand
from couchformation.exception import FatalError

logger = logging.getLogger('couchformation.util')
logger.addHandler(logging.NullHandler())


class FileManagerError(FatalError):
    pass


def dict_merge(dict1, dict2):
    new_dict = dict(dict1)
    new_dict.update(dict2)
    return new_dict


def dict_merge_list(*dicts):
    res = collections.defaultdict(list)
    for d in dicts:
        for k, v in d.items():
            res[f"{k}_list"].append(v)
    return {k: set(v) for k, v in res.items()}


class FileManager(object):

    def __init__(self):
        pass

    def make_dir(self, name: str):
        if not os.path.exists(name):
            path_dir = os.path.dirname(name)
            if not os.path.exists(path_dir):
                self.make_dir(path_dir)
            try:
                os.mkdir(name)
            except OSError:
                raise

    def dir_populate(self, path: str, command: Union[str, None] = None):
        self.make_dir(path)
        if command:
            cmd = command.split()
            RunShellCommand().cmd_exec(cmd, path)

    @staticmethod
    def copy_file(source: str, destination: str) -> None:
        try:
            logger.debug(f"Copying {source} to {destination}")
            copyfile(source, destination)
        except Exception as err:
            raise FileManagerError(f"can not copy {source} to {destination}: {err}")

    @staticmethod
    def list_dir(dir_name: str):
        for name in os.listdir(dir_name):
            yield name


class UUIDGen(object):

    def __init__(self):
        self._last_uuid = UUID('00000000000000000000000000000000')
        self._uuid = self._last_uuid

    def recompute(self, text):
        self._uuid = uuid.uuid5(self._last_uuid, text)
        self._last_uuid = self._uuid

    @property
    def uuid(self):
        return self._uuid


class Synchronize(object):

    def __init__(self, lock: Lock):
        self._lock = lock

    def __enter__(self):
        self._lock.acquire()

    def __exit__(self, *args):
        self._lock.release()


class PasswordUtility(object):

    def __init__(self):
        pass

    @staticmethod
    def valid_password(password: str, min_length: int = 8, max_length: int = 64) -> bool:
        lower = 0
        upper = 0
        digit = 0
        special = 0
        if min_length <= len(password) <= max_length:
            for i in password:
                if i.islower():
                    lower += 1
                if i.isupper():
                    upper += 1
                if i.isdigit():
                    digit += 1
                if not i.isalnum():
                    special += 1

        if lower >= 1 and upper >= 1 and digit >= 1 and special >= 1:
            return True
        else:
            return False

    def generate(self, length: int = 8):
        while True:
            text = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits + '%@#', k=length))
            password = str(text)
            if self.valid_password(password, min_length=length):
                return password
