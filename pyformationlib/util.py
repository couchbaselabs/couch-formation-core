##
##

import os
from pwd import getpwnam
from grp import getgrnam


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
