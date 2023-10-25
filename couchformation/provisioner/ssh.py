##
##

import paramiko
import subprocess
import logging
import io
import select
import time

logger = logging.getLogger('couchformation.provisioner.ssh')
logger.addHandler(logging.NullHandler())


class SSHError(Exception):
    pass


class RunSSHCommand(object):

    def __init__(self):
        pass

    @staticmethod
    def local_exec(ssh_key: str, ssh_user: str, hostname: str, command: str, directory: str):
        buffer = io.BytesIO()
        logger.debug(f"Shell command: {command}")

        ssh_cmd = f"""ssh -i {ssh_key} -l {ssh_user} {hostname} '{command}'"""

        p = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=directory)

        while True:
            data = p.stdout.read()
            if not data:
                break
            buffer.write(data)

        p.communicate()
        buffer.seek(0)

        return p.returncode, buffer

    @staticmethod
    def lib_exec(ssh_key: str, ssh_user: str, hostname: str, command: str, retry_count=60, factor=0.5):
        output = io.BytesIO()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        for retry_number in range(retry_count + 1):
            try:
                ssh.connect(hostname, username=ssh_user, key_filename=ssh_key, timeout=60, auth_timeout=30, banner_timeout=30)
            except paramiko.ssh_exception.SSHException:
                if retry_number == retry_count:
                    raise RuntimeError(f"can not connect to {hostname} with SSH")
                logger.info(f"Waiting for an SSH connection to {hostname}")
                wait = factor
                wait *= (2 ** (retry_number + 1))
                time.sleep(wait)

        stdin, stdout, stderr = ssh.exec_command(command)
        channel = stdout.channel
        stdin.close()
        channel.shutdown_write()

        while not channel.closed:
            readq, _, _ = select.select([channel], [], [], 0)
            for c in readq:
                if c.recv_ready():
                    output.write(channel.recv(len(c.in_buffer)))
                if c.recv_stderr_ready():
                    output.write(channel.recv(len(c.in_buffer)))
            if channel.exit_status_ready() and not channel.recv_stderr_ready() and not channel.recv_ready():
                channel.shutdown_read()
                channel.close()
                break

        stdout.close()
        stderr.close()

        exit_code = channel.recv_exit_status()

        ssh.close()
        output.seek(0)

        return exit_code, output
