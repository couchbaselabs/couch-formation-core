##
##

import os
import logging
import uuid
import collections
import string
import random
import tarfile
import hashlib
import threading
from typing import Union, List, Callable
from uuid import UUID
from shutil import copyfile
from functools import wraps
from couchformation.provisioner.shell import RunShellCommand
from couchformation.exception import FatalError

logger = logging.getLogger('couchformation.util')
logger.addHandler(logging.NullHandler())
lock = threading.Lock()


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


def dict_merge_not_none(source, target):
    new_dict = dict(target)
    for key, value in source.items():
        if new_dict.get(key) is None and source.get(key) is not None:
            new_dict[key] = value
    return new_dict


def progress_bar(iteration, total, decimals=1, length=100, fill='#', end="\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled = int(length * iteration // total)
    bar = fill * filled + '-' * (length - filled)
    print(f'\rProgress: |{bar}| {percent}% Complete', end=end)
    if iteration == total:
        print()


def synchronize() -> Callable:
    def lock_handler(func):
        @wraps(func)
        def f_wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return f_wrapper
    return lock_handler


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
    def copy_file(source: Union[str, bytes], destination: Union[str, bytes]) -> None:
        try:
            logger.debug(f"Copying {source} to {destination}")
            copyfile(source, destination)
        except Exception as err:
            raise FileManagerError(f"can not copy {source} to {destination}: {err}")

    @staticmethod
    def list_dir(dir_name: str):
        for name in os.listdir(dir_name):
            yield name

    @staticmethod
    def create_archive(file_name: str, root_dir: str, file_list: List[str]):
        path_list = []
        file_count = 0

        for path_name in file_list:
            if os.path.isdir(path_name):
                for root, dirs, files in os.walk(path_name):
                    for filename in dirs + files:
                        full_path = os.path.join(root, filename)
                        if not os.path.isfile(full_path):
                            continue
                        path_list.append(full_path)
                        file_count += 1
            else:
                path_list.append(path_name)
                file_count += 1

        progress_bar(0, file_count, length=50)
        with tarfile.open(file_name, mode='w:gz') as tar:
            for n, file_name in enumerate(path_list):
                rel_name = os.path.relpath(file_name, root_dir) if file_name.startswith(root_dir) else file_name
                tar.add(file_name, arcname=rel_name)
                progress_bar(n + 1, file_count, length=50)


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

    @staticmethod
    def get_project_uid(project_name):
        return hashlib.md5(f"{uuid.getnode()}-{project_name}".encode()).hexdigest()[:10]

    @staticmethod
    def text_hash(text):
        return hashlib.md5(text.encode()).hexdigest()[:8]


class Synchronize(object):

    def __init__(self):
        pass

    def __enter__(self):
        lock.acquire()

    def __exit__(self, *args):
        lock.release()


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
