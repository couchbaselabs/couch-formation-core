##
##

import paramiko
import subprocess
import logging
import io
import time
import socket

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
        bufsize = 4096
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        for retry_number in range(retry_count + 1):
            try:
                ssh.connect(hostname, username=ssh_user, key_filename=ssh_key, timeout=10, auth_timeout=10, banner_timeout=10)
            except paramiko.ssh_exception.BadHostKeyException as err:
                raise RuntimeError(f"host key mismatch for {hostname}: {err}")
            except paramiko.ssh_exception.AuthenticationException as err:
                raise RuntimeError(f"failed to authenticate to {hostname}: {err}")
            except (paramiko.ssh_exception.SSHException, TimeoutError, socket.timeout):
                if retry_number == retry_count:
                    raise RuntimeError(f"can not connect to {hostname}")
                logger.info(f"Waiting for an SSH connection to {hostname}")
                wait = factor
                wait *= (2 ** (retry_number + 1))
                time.sleep(wait)

        try:
            ssh.get_transport().set_keepalive(5)
            chan = ssh.get_transport().open_session()
        except Exception as err:
            raise RuntimeError(f"failed to open SSH session on {hostname}: {err}")

        chan.exec_command(command)

        stdout = b''.join(chan.makefile('rb', bufsize))
        stderr = b''.join(chan.makefile_stderr('rb', bufsize))

        exit_code = chan.recv_exit_status()

        ssh.close()

        return exit_code, stdout, stderr
