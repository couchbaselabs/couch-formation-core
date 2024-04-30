##
##

import attr
import logging
import socket
import time
import os
import jinja2
import json
from typing import Optional, List
from couchformation.exception import NonFatalError
from couchformation.config import NodeList, get_state_dir
from couchformation.provisioner.ssh import RunSSHCommand
from couchformation.provisioner.sftp import SFTPFile
import couchformation.constants as C

logger = logging.getLogger('couchformation.provisioner.remote')
logger.addHandler(logging.NullHandler())
logging.getLogger("paramiko").setLevel(logging.ERROR)


class ProvisionerError(NonFatalError):
    pass


class CustomLogFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.INFO: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.WARNING: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.ERROR: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.CRITICAL: f"{C.FORMAT_TIMESTAMP} [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        if logging.DEBUG >= logging.root.level:
            log_fmt += C.FORMAT_EXTRA
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


@attr.s
class ProvisionSet:
    pre_install_cmd: Optional[List[str]] = attr.ib(default=[])
    install_cmd: Optional[List[str]] = attr.ib(default=[])
    post_install_cmd: Optional[List[str]] = attr.ib(default=[])
    nodes: Optional[NodeList] = attr.ib(default=None)

    @classmethod
    def create(cls):
        return cls(
            [],
            [],
            [],
            None
        )

    def add_pre_install(self, pre_install_cmds: List[str]):
        self.pre_install_cmd.extend(pre_install_cmds)

    def add_install(self, install_cmds: List[str]):
        self.install_cmd.extend(install_cmds)

    def add_post_install(self, post_install_cmds: List[str]):
        self.post_install_cmd.extend(post_install_cmds)

    def add_nodes(self, node_list: NodeList):
        self.nodes = node_list


class RemoteProvisioner(object):

    def __init__(self, parameters: dict, command: str = '', root: bool = True):
        self.parameters = parameters
        self.command = command
        self.root = root
        self.service = self.parameters.get('service')
        self.project = self.parameters.get('project')
        self.public_ip = self.parameters.get('public_ip')
        self.private_ip = self.parameters.get('private_ip')
        self.public_hostname = self.parameters.get('public_hostname')
        self.private_hostname = self.parameters.get('private_hostname')
        self.public = self.parameters.get('public') if 'public' in self.parameters else False
        self.username = self.parameters.get('username')
        self.ssh_key = self.parameters.get('ssh_key')
        self.zone = self.parameters.get('zone')
        self.password = self.parameters.get('password') if 'password' in self.parameters else 'password'
        self.host_password = self.parameters.get('host_password')
        self.upload_file = self.parameters.get('upload')
        self.sw_version = self.parameters.get('sw_version') if 'sw_version' in self.parameters else 'latest'
        self.services = self.parameters.get('services')
        self.connect = ','.join(self.parameters.get('connect')) \
            if self.parameters.get('connect') and type(self.parameters.get('connect')) is list \
            else self.parameters.get('connect')
        self.private_ip_list = ','.join(self.parameters.get('private_ip_list'))
        self.public_ip_list = ','.join(self.parameters.get('public_ip_list'))
        self.service_list = ':'.join(self.parameters.get('service_list'))
        if self.parameters.get('private_host_list') and len(self.parameters.get('private_host_list')) > 0:
            self.private_host_list = ','.join(self.parameters.get('private_host_list'))
        else:
            self.private_host_list = 'null'
        if self.parameters.get('public_host_list') and len(self.parameters.get('public_host_list')) > 0:
            self.public_host_list = ','.join(self.parameters.get('public_host_list'))
        else:
            self.public_host_list = 'null'
        self.use_private_ip = self.parameters.get('use_private_ip') if self.parameters.get('use_private_ip') else False

        logger.debug(f"Parameters:\n{json.dumps(self.parameters, indent=2)}")

    def upload(self):
        if self.use_private_ip:
            hostname = self.private_ip
        else:
            hostname = self.public_ip

        filename = os.path.basename(self.upload_file)

        if not self.wait_port(hostname):
            raise ProvisionerError(f"Host {hostname} is not reachable")

        logger.info(f"Connection to {hostname} successful")
        time.sleep(0.5)

        SFTPFile(self.ssh_key, self.username, hostname, self.upload_file, f"/var/tmp/{filename}").upload()

        return 0

    def run(self):
        working_dir = get_state_dir(self.project, self.service)
        file_output = logging.getLogger('couchformation.provisioner.output')
        file_output.propagate = False
        log_file = os.path.join(working_dir, 'provision.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(CustomLogFormatter())
        file_output.addHandler(file_handler)
        file_output.setLevel(logging.DEBUG)

        if self.use_private_ip:
            hostname = self.private_ip
        else:
            hostname = self.public_ip

        if self.root:
            command = f"""sudo {self.command}"""
        else:
            command = self.command

        if not self.wait_port(hostname):
            raise ProvisionerError(f"Host {hostname} is not reachable")

        logger.info(f"Connection to {hostname} successful")
        time.sleep(0.5)

        _command = self.resolve_variables(command)

        logger.info(f"Connecting to {hostname} as {self.username}")
        logger.debug(f"Using SSH key {self.ssh_key}")
        logger.debug(f"Running command: {_command}")

        file_output.info(f"{hostname}: [{_command}] begins")

        exit_code, stdout, stderr = RunSSHCommand(self.ssh_key, self.username, hostname, _command, working_dir).exec()

        for line in stdout.readlines():
            line_out = line.strip()
            log_out = f"{hostname}: {line_out}"
            logger.info(log_out)
            file_output.info(log_out)

        file_output.info(f"{hostname}: [{_command}] complete")

        logger.info(f"Command complete for host {hostname}")
        logger.debug(f"[{_command}] returned {exit_code} on {hostname}")

        file_output.removeHandler(file_handler)
        file_handler.close()
        return exit_code

    @staticmethod
    def wait_port(address: str, port: int = 22, retry_count=300, factor=0.1):
        for retry_number in range(retry_count + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((address, port))
            sock.close()
            if result == 0:
                return True
            else:
                if retry_number == retry_count:
                    return False
                logger.info(f"Waiting for {address} to become reachable")
                wait = factor
                wait *= (2 ** (retry_number + 1))
                time.sleep(wait)

    def resolve_variables(self, line: str):
        env = jinja2.Environment(undefined=jinja2.DebugUndefined)
        raw_template = env.from_string(line)
        formatted_value = raw_template.render(
            SERVICE_NAME=self.service,
            SOFTWARE_VERSION=self.sw_version,
            PASSWORD=self.password,
            PRIVATE_IP_LIST=self.private_ip_list,
            PUBLIC_IP_LIST=self.public_ip_list,
            SERVICE_LIST=self.service_list,
            IP_LIST=self.public_ip_list if self.public else self.private_ip_list,
            HOST_LIST=self.public_host_list if self.public else self.private_host_list,
            NODE_ZONE=self.zone,
            SERVICES=self.services,
            CONNECT_SERVICE=self.connect,
            CONNECT_IP=self.connect,
            CONNECT_LIST=self.connect if self.connect else '127.0.0.1'
        )
        return formatted_value
