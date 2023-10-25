##
##

import os
import logging
import uuid
import collections
from uuid import UUID
from shutil import copyfile
from pwd import getpwnam
from grp import getgrnam
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

    def make_dir(self, name: str, owner: str = None, group: str = None, mode: int = 0o775):
        owner_id = getpwnam(owner).pw_uid if owner else None
        group_id = getgrnam(group).gr_gid if group else None
        if not os.path.exists(name):
            path_dir = os.path.dirname(name)
            if not os.path.exists(path_dir):
                self.make_dir(path_dir)
            try:
                uid = os.stat(path_dir).st_uid if not owner_id else owner_id
                gid = os.stat(path_dir).st_gid if not group_id else group_id
                os.mkdir(name)
                os.chown(name, uid, gid)
                os.chmod(name, mode)
            except OSError:
                raise

    def set_perms(self, name: str, owner: str, group: str, mode: int = 0o775):
        if os.path.exists(name):
            uid = getpwnam(owner).pw_uid
            gid = getgrnam(group).gr_gid
            os.chown(name, uid, gid)
            os.chmod(name, mode)
        else:
            self.make_dir(name, owner, group, mode)

    @staticmethod
    def copy_file(source: str, destination: str) -> None:
        try:
            logger.debug(f"Copying {source} to {destination}")
            copyfile(source, destination)
        except Exception as err:
            raise FileManagerError(f"can not copy {source} to {destination}: {err}")


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
