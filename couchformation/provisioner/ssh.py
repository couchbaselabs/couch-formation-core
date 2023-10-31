##
##

import paramiko
import paramiko.util
import subprocess
import logging
import io
import time
import socket
import os
import couchformation.constants as C

logger = logging.getLogger('couchformation.provisioner.ssh')
logger.addHandler(logging.NullHandler())


class SSHError(Exception):
    pass


old_factory = logging.getLogRecordFactory()


def record_factory_factory(context_id):
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.ip_address = context_id
        return record
    return record_factory


class CustomLogFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: f"{C.FORMAT_TIMESTAMP} (%(ip_address)s) [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.INFO: f"{C.FORMAT_TIMESTAMP} (%(ip_address)s) [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.WARNING: f"{C.FORMAT_TIMESTAMP} (%(ip_address)s) [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.ERROR: f"{C.FORMAT_TIMESTAMP} (%(ip_address)s) [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}",
        logging.CRITICAL: f"{C.FORMAT_TIMESTAMP} (%(ip_address)s) [{C.FORMAT_LEVEL}] {C.FORMAT_MESSAGE}"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        if logging.DEBUG >= logging.root.level:
            log_fmt += C.FORMAT_EXTRA
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


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
    def lib_exec(ssh_key: str, ssh_user: str, hostname: str, command: str, working_dir: str, retry_count=30, factor=0.5):
        bufsize = 4096
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.WarningPolicy())

        file_output = logging.getLogger("paramiko")
        file_output.propagate = False
        log_file = os.path.join(working_dir, 'connect.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(CustomLogFormatter())
        file_output.addHandler(file_handler)
        file_output.setLevel(logging.root.level)
        # file_output.setLevel(logging.DEBUG)
        logging.setLogRecordFactory(record_factory_factory(hostname))

        for retry_number in range(retry_count + 1):
            try:
                ssh.connect(hostname, username=ssh_user, key_filename=ssh_key, timeout=10, auth_timeout=10, banner_timeout=10, allow_agent=False)
                ssh.get_transport().set_keepalive(5)
            except paramiko.ssh_exception.BadHostKeyException as err:
                raise RuntimeError(f"host key mismatch for {hostname}: {err}")
            except paramiko.ssh_exception.AuthenticationException as err:
                raise RuntimeError(f"failed to authenticate to {hostname}: {err}")
            except (paramiko.ssh_exception.SSHException, TimeoutError, socket.timeout):
                if retry_number == retry_count:
                    raise RuntimeError(f"can not connect to {hostname}")
                logger.info(f"Waiting for an SSH connection to {hostname}")
                wait = factor
                wait *= (retry_number + 1)
                time.sleep(wait)
            except Exception as err:
                raise RuntimeError(f"can not connect to {hostname}: {err}")

        for retry_number in range(retry_count + 1):
            try:
                stdin, stdout, stderr = ssh.exec_command(command, bufsize=bufsize, timeout=10)
                channel = stdout.channel
                stdin.close()
                channel.shutdown_write()
                exit_code = channel.recv_exit_status()
                timeout = 5
                end_time = time.time() + timeout
                while not stdout.channel.eof_received:
                    time.sleep(0.5)
                    if time.time() > end_time:
                        stdout.channel.close()
                        break
                ssh.close()
                return exit_code, stdout, stderr
            except Exception as err:
                if retry_number == retry_count:
                    raise RuntimeError(f"command failed on {hostname}: {err}")
                logger.info(f"Retrying command on {hostname}")
                wait = factor
                wait *= (2 ** (retry_number + 1))
                time.sleep(wait)
