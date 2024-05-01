##
##

import io
import os
import getpass
import stat
import sys
import logging
import platform
import tarfile
import time
import json
import csv
import plistlib
from typing import List, Any, Tuple
from couchformation.config import get_log_dir, get_root_dir, get_base_dir
from pathlib import Path
from datetime import datetime
import couchformation.kvdb as kvdb
if os.name == 'nt':
    group_name = "staff"
else:
    import grp
    group_name = grp.getgrgid(os.getgid())[0]

logger = logging.getLogger('couchformation.support')
logger.addHandler(logging.NullHandler())


class CreateDebugPackage(object):

    def __init__(self):
        now = datetime.now()
        time_string = now.strftime("%m%d%y%H%M%S")
        self.os_release = "/etc/os-release"
        self.macos_release = "/System/Library/CoreServices/SystemVersion.plist"
        self.log_dir = get_log_dir()
        self.root_dir = get_root_dir()
        self.state_dir = get_base_dir()
        self.debug_file = os.path.join(self.log_dir, "formation.log")
        self.crash_file = os.path.join(self.log_dir, "crash.log")
        self.tgz_file = f"cf-debug-{time_string}.tar.gz"
        self.support_bundle = os.path.join(Path.home(), self.tgz_file)
        self.file_list = []

        logger.debug(f"Python version: {''.join(sys.version.splitlines())}")
        logger.debug(f"System: {platform.system()} Release: {platform.release()}")

        if os.path.exists(self.debug_file):
            self.file_list.append(('path', self.debug_file))
        if os.path.exists(self.crash_file):
            self.file_list.append(('path', self.crash_file))

        state_dir_listing = self.state_file_list()
        self.file_list.append(("state_dir_listing.log", state_dir_listing))

        state_data_dump = self.state_data_dump()
        self.file_list.append(("state_data.json", state_data_dump))

        os_info = self.os_info()
        self.file_list.append(("os_info.txt", os_info))

    def create_snapshot(self):
        logger.info(f"Writing support bundle to {self.support_bundle}")
        self.support_archive(self.support_bundle, self.root_dir, self.file_list)

    def os_info(self):
        data = io.BytesIO()

        if os.path.exists(self.os_release):
            with open(self.os_release) as f:
                reader = csv.reader(f, delimiter="=")
                for rows in reader:
                    if len(rows) < 2:
                        continue
                    data.write(f"{rows[0]}: {rows[1]}\n".encode())
        elif os.path.exists(self.macos_release):
            with open(self.macos_release, 'rb') as f:
                sys_info = plistlib.load(f)
            data.write(f"NAME      : {os.uname().sysname}\n".encode())
            data.write(f"VERSION   : {os.uname().version}\n".encode())
            data.write(f"ID        : {sys_info.get('ProductName')}\n".encode())
            data.write(f"VERSION_ID: {sys_info.get('ProductVersion')}\n".encode())

        uname = platform.uname()
        data.write(f"Node     : {uname.node}\n".encode())
        data.write(f"System   : {uname.system}\n".encode())
        data.write(f"Version  : {uname.version}\n".encode())
        data.write(f"Release  : {uname.release}\n".encode())
        data.write(f"Machine  : {uname.machine}\n".encode())
        data.write(f"Processor: {uname.processor}\n".encode())

        data.seek(0)
        return data

    def state_file_list(self):
        data = io.BytesIO()

        for root, dirs, files in os.walk(self.state_dir):
            for filename in dirs + files:
                full_path = os.path.join(root, filename)
                try:
                    st = os.stat(full_path)
                    is_dir = 'd' if stat.S_ISDIR(st.st_mode) else '-'
                    d = {'7': 'rwx', '6': 'rw-', '5': 'r-x', '4': 'r--', '0': '---'}
                    perm = str(oct(st.st_mode)[-3:])
                    prefix = is_dir + ''.join(d.get(x, x) for x in perm)
                    user = getpass.getuser()
                    group = group_name
                    data.write(f"{prefix} {user:<9} {group:<9} {full_path}\n".encode())
                except Exception as err:
                    data.write(f"{full_path}: {err}\n".encode())

        data.seek(0)
        return data

    def state_data_dump(self):
        data = io.BytesIO()
        obj_list = []

        for root, dirs, files in os.walk(self.state_dir):
            for filename in dirs + files:
                full_path = os.path.join(root, filename)
                st = os.stat(full_path)
                if stat.S_ISREG(st.st_mode):
                    with open(full_path, 'rb') as data_file:
                        header = data_file.read(16)
                        if header.decode('utf-8').startswith('SQLite format 3'):
                            try:
                                block = {
                                    'file_name': full_path,
                                    'documents': {}
                                }
                                for doc in kvdb.documents(full_path):
                                    block['documents'][doc.document_id] = {}
                                    null_c = 1
                                    for key, value in doc.items():
                                        if not key:
                                            key = f"null_{null_c}"
                                            null_c += 1
                                        if key == 'host_password' or key == 'password':
                                            continue
                                        block['documents'][doc.document_id].update({key: value})
                                obj_list.append(block)
                            except Exception as err:
                                block = {
                                    'file_name': full_path,
                                    'error': err
                                }
                                obj_list.append(block)

        data.write(json.dumps(obj_list, indent=2).encode())
        data.seek(0)
        return data

    @staticmethod
    def support_archive(file_name: str, root_dir: str, file_list: List[Tuple[str, Any]]):
        with tarfile.open(file_name, mode='w:gz') as tar:
            for n, file_tuple in enumerate(file_list):
                file_text = file_tuple[0]
                if isinstance(file_tuple[1], io.BytesIO):
                    file_data: io.BytesIO = file_tuple[1]
                    tar_info = tarfile.TarInfo(name=f"log/{file_text}")
                    tar_info.mtime = time.time()
                    tar_info.uid = 0
                    tar_info.gid = 0
                    tar_info.size = file_data.getbuffer().nbytes
                    tar.addfile(tarinfo=tar_info, fileobj=file_data)
                else:
                    file_path = file_tuple[1]
                    rel_name = os.path.relpath(file_path, root_dir) if file_path.startswith(root_dir) else file_path
                    tar.add(file_path, arcname=rel_name)
