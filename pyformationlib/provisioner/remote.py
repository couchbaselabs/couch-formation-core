##
##

import attr
import concurrent.futures
import logging
import paramiko
import socket
import time
from io import StringIO
from typing import Optional, List
from pyformationlib.exception import FatalError
from pyformationlib.config import NodeList

logger = logging.getLogger('pyformationlib.provisioner.remote')
logger.addHandler(logging.NullHandler())


class ProvisionerError(FatalError):
    pass


@attr.s
class ProvisionSet:
    commands: Optional[List[str]] = attr.ib(default=[])
    nodes: Optional[NodeList] = attr.ib(default=None)

    @classmethod
    def create(cls):
        return cls(
            [],
            None
        )

    def add_cmd(self, command: str):
        self.commands.append(command)

    def add_cmds(self, commands: List[str]):
        self.commands.extend(commands)

    def add_nodes(self, node_list: NodeList):
        self.nodes = node_list


class RemoteProvisioner(object):

    def __init__(self, config: ProvisionSet):
        self.config = config
        self.executor = concurrent.futures.ThreadPoolExecutor()
        self.tasks = set()

    def dispatch(self, hostname: str):
        output = StringIO()
        last_exit = 0

        if not self.wait_port(hostname):
            raise ProvisionerError(f"Host {hostname} is not reachable")

        for command in self.config.commands:
            username = self.config.nodes.username
            ssh_key_file = self.config.nodes.ssh_key
            logger.info(f"Connecting to {hostname} as {username}")
            logger.debug(f"Using SSH key {ssh_key_file}")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname, username=username, key_filename=ssh_key_file)
            stdin, stdout, stderr = ssh.exec_command(command)
            last_exit = stdout.channel.recv_exit_status()
            for line in stdout.readlines():
                output.write(line)
            for line in stderr.readlines():
                output.write(line)
            if last_exit != 0:
                break
        output.seek(0)
        return hostname, output, last_exit

    def exec(self):
        for node_ip in self.config.nodes.list_public_ip():
            self.tasks.add(self.executor.submit(self.dispatch, node_ip))

    def join(self):
        while self.tasks:
            done, self.tasks = concurrent.futures.wait(self.tasks, return_when=concurrent.futures.FIRST_COMPLETED)
            for task in done:
                try:
                    hostname, output, last_exit = task.result()
                    for line in output.readlines():
                        line_out = line.strip()
                        print(f"{hostname}: {line_out}")
                except Exception as err:
                    raise ProvisionerError(err)

    @staticmethod
    def wait_port(address: str, port: int = 22, retry_count=300, factor=0.1):
        for retry_number in range(retry_count + 1):
            socket.setdefaulttimeout(1)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
