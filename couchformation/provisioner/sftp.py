##
##

import paramiko
import paramiko.util
import logging
import time
import socket

logger = logging.getLogger('couchformation.provisioner.sftp')
logger.addHandler(logging.NullHandler())


class SSHError(Exception):
    pass


class KeepAliveFilter(logging.Filter):
    def filter(self, record):
        return record.msg.find('keepalive@lag.net') < 0


class SFTPFile(object):

    def __init__(self, ssh_key: str, ssh_user: str, hostname: str, source: str, destination: str):
        self.ssh_key = ssh_key
        self.ssh_user = ssh_user
        self.hostname = hostname
        self.source = source
        self.destination = destination

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
                wait = factor
                wait *= n_retry
                time.sleep(wait)

    def upload(self, connect_retry=35, op_retry=10, factor=0.5):
        ssh = self.ssh_connect(retry_count=connect_retry, factor=factor)
        sftp_client = ssh.open_sftp()

        for retry_number in range(op_retry):
            try:
                sftp_client.put(self.source, self.destination)
            except Exception as err:
                n_retry = retry_number + 1
                if n_retry == op_retry:
                    raise RuntimeError(f"upload failed on {self.hostname}: {err}")
                logger.info(f"Retrying upload on {self.hostname}")
                wait = factor
                wait *= n_retry
                time.sleep(wait)

        sftp_client.close()

    def download(self, connect_retry=35, op_retry=10, factor=0.5):
        ssh = self.ssh_connect(retry_count=connect_retry, factor=factor)
        sftp_client = ssh.open_sftp()

        for retry_number in range(op_retry):
            try:
                sftp_client.get(self.source, self.destination)
            except Exception as err:
                n_retry = retry_number + 1
                if n_retry == op_retry:
                    raise RuntimeError(f"upload failed on {self.hostname}: {err}")
                logger.info(f"Retrying upload on {self.hostname}")
                wait = factor
                wait *= n_retry
                time.sleep(wait)

        sftp_client.close()
