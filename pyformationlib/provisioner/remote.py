##
##

import concurrent.futures
import logging
import paramiko
from pyformationlib.exception import FatalError

logger = logging.getLogger('pyformationlib.provisioner.remote')
logger.addHandler(logging.NullHandler())


class ProvisionerError(FatalError):
    pass


class RemoteProvisioner(object):

    def __init__(self,
                 username: str,
                 ssh_key: str):
        self.executor = concurrent.futures.ThreadPoolExecutor()
        self.username = username
        self.ssh_key = ssh_key
        self.tasks = set()

    def connect(self, hostname: str, command: str):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=self.username, key_filename=self.ssh_key)
        stdin, stdout, stderr = ssh.exec_command(command)
        return stdout.readlines(), stderr.readlines(), stdout.channel.recv_exit_status()

    def dispatch(self, hostname: str, command: str):
        self.tasks.add(self.executor.submit(self.connect, hostname, command))

    def join(self):
        while self.tasks:
            done, self.tasks = concurrent.futures.wait(self.tasks, return_when=concurrent.futures.FIRST_COMPLETED)
            for task in done:
                try:
                    stdout, stderr, exit_code = task.result()
                    for line in stdout:
                        line_out = line.strip()
                        print(line_out)
                except Exception as err:
                    raise ProvisionerError(err)
