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


class KeepAliveFilter(logging.Filter):
    def filter(self, record):
        return record.msg.find('keepalive@lag.net') < 0


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

    def __init__(self, ssh_key: str, ssh_user: str, hostname: str, command: str, working_dir: str):
        self.ssh_key = ssh_key
        self.ssh_user = ssh_user
        self.hostname = hostname
        self.command = command

        self.file_output = logging.getLogger("paramiko")
        self.file_output.propagate = False
        log_file = os.path.join(working_dir, 'connect.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(CustomLogFormatter())
        self.file_output.addHandler(file_handler)
        # file_output.setLevel(logging.root.level)
        self.file_output.setLevel(logging.DEBUG)
        logging.setLogRecordFactory(record_factory_factory(hostname))

        paramiko.util.get_logger('paramiko.transport').addFilter(KeepAliveFilter())

    def ssh_connect(self, retry_count=35, factor=0.5):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.WarningPolicy())

        for retry_number in range(retry_count):
            try:
                ssh.connect(self.hostname, username=self.ssh_user, key_filename=self.ssh_key, timeout=10, auth_timeout=10, banner_timeout=10, allow_agent=False)
                ssh.get_transport().set_keepalive(5)
                return ssh
            except paramiko.ssh_exception.BadHostKeyException as err:
                raise RuntimeError(f"host key mismatch for {self.hostname}: {err}")
            except paramiko.ssh_exception.AuthenticationException as err:
                raise RuntimeError(f"failed to authenticate to {self.hostname}: {err}")
            except (paramiko.ssh_exception.SSHException, TimeoutError, socket.timeout) as err:
                n_retry = retry_number + 1
                if n_retry == retry_count:
                    raise RuntimeError(f"can not connect to {self.hostname}: {err}")
                logger.info(f"Waiting for an SSH connection to {self.hostname}")
                self.file_output.error(f"retrying SSH connect: count {n_retry}: {err}")
                wait = factor
                wait *= n_retry
                time.sleep(wait)

    def exec(self, connect_retry=35, command_retry=10, factor=0.5):
        bufsize = 4096

        ssh = self.ssh_connect(retry_count=connect_retry, factor=factor)

        for retry_number in range(command_retry):
            try:
                stdin, stdout, stderr = ssh.exec_command(self.command, bufsize=bufsize, timeout=10)
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
                n_retry = retry_number + 1
                if n_retry == command_retry:
                    raise RuntimeError(f"command failed on {self.hostname}: {err}")
                logger.info(f"Retrying command on {self.hostname}")
                self.file_output.error(f"retrying command exec: count {n_retry}: {err}")
                wait = factor
                wait *= n_retry
                time.sleep(wait)


class RunSSHCommandExec(object):

    def __init__(self):
        pass

    @staticmethod
    def exec(ssh_key: str, ssh_user: str, hostname: str, command: str, directory: str):
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
