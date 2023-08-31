##
##

import attr
import concurrent.futures
import logging
import paramiko
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
        for command in self.config.commands:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname, username=self.config.nodes.username, key_filename=self.config.nodes.ssh_key)
            stdin, stdout, stderr = ssh.exec_command(command)
            last_exit = stdout.channel.recv_exit_status()
            for line in stdout:
                output.write(line)
            for line in stderr:
                output.write(line)
            if last_exit != 0:
                break
        return hostname, output, last_exit

    def exec(self):
        for node_ip in self.config.nodes.list_public_ip():
            self.tasks.add(self.executor.submit(self.exec, node_ip))

    def join(self):
        while self.tasks:
            done, self.tasks = concurrent.futures.wait(self.tasks, return_when=concurrent.futures.FIRST_COMPLETED)
            for task in done:
                try:
                    hostname, output, last_exit = task.result()
                    for line in output.readlines():
                        line_out = line.strip()
                        print(line_out)
                except Exception as err:
                    raise ProvisionerError(err)
