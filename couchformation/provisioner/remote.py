##
##

import attr
import logging
import socket
import time
import os
import jinja2
from typing import Optional, List
from couchformation.exception import NonFatalError
from couchformation.config import NodeList, get_state_dir
from couchformation.provisioner.ssh import RunSSHCommand
from couchformation.executor.targets import BuildConfig, Provisioner
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

    def __init__(self, provisioner: Provisioner, default: BuildConfig, build: BuildConfig):
        self.parameters = provisioner.parameters
        self.build = build
        self.default = default
        self.service = self.parameters.get('service')
        self.project = self.parameters.get('project')
        self.public_ip = self.parameters.get('public_ip')
        self.private_ip = self.parameters.get('private_ip')
        self.username = self.parameters.get('username')
        self.ssh_key = self.parameters.get('ssh_key')
        self.zone = self.parameters.get('zone')
        self.services = self.parameters.get('services')
        self.connect = self.parameters.get('connect')
        self.private_ip_list = ','.join(self.parameters.get('private_ip_list'))
        self.use_private_ip = self.parameters.get('use_private_ip') if self.parameters.get('use_private_ip') else False

        self.file_output = logging.getLogger('couchformation.provisioner.output')
        self.file_output.propagate = False

        self.log_file = os.path.join(get_state_dir(self.project, self.service), 'provision.log')
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(CustomLogFormatter())
        self.file_output.addHandler(file_handler)
        self.file_output.setLevel(logging.DEBUG)

    def run(self):
        for command in self.default.commands:
            if self.build.root:
                command = f"""sudo {command}"""
            res = self.exec(command)
            if res != 0:
                return res
        for command in self.build.commands:
            if self.build.root:
                command = f"""sudo {command}"""
            res = self.exec(command)
            if res != 0:
                return res
        return 0

    def exec(self, command: str):
        if self.use_private_ip:
            hostname = self.private_ip
        else:
            hostname = self.public_ip

        if not self.wait_port(hostname):
            raise ProvisionerError(f"Host {hostname} is not reachable")

        logger.info(f"Connection to {hostname} successful")

        _command = self.resolve_variables(command)

        logger.info(f"Connecting to {hostname} as {self.username}")
        logger.debug(f"Using SSH key {self.ssh_key}")
        logger.debug(f"Running command: {_command}")

        time.sleep(1)
        self.file_output.info(f"{hostname}: [{_command}] begins")

        exit_code, stdout, stderr = RunSSHCommand().lib_exec(self.ssh_key, self.username, hostname, _command)

        output = stdout.decode("utf-8").split('\n')
        for line in output:
            if len(line) == 0:
                continue
            log_out = f"{hostname}: {line}"
            logger.info(log_out)
            self.file_output.info(log_out)

        self.file_output.info(f"{hostname}: [{_command}] complete")

        logger.info(f"Command complete for host {hostname}")
        logger.debug(f"[{_command}] returned {exit_code} on {hostname}")

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
            PRIVATE_IP_LIST=self.private_ip_list,
            NODE_ZONE=self.zone,
            SERVICES=self.services,
            CONNECT_SERVICE=self.connect,
            CONNECT_IP=self.connect,
            CONNECT_LIST=self.connect if self.connect else '127.0.0.1'
        )
        return formatted_value
