##
##

import logging
import winrm
import socket
import time
import jinja2
from couchformation.exception import NonFatalError

logger = logging.getLogger('couchformation.provisioner.winrm')
logger.addHandler(logging.NullHandler())


class ProvisionerError(NonFatalError):
    pass


class WinRMProvisioner(object):

    def __init__(self, parameters: dict, command: str = '', root: bool = True):
        self.parameters = parameters
        self.command = command
        self.root = root
        self.service = self.parameters.get('service')
        self.project = self.parameters.get('project')
        self.username = self.parameters.get('username')
        self.public_ip = self.parameters.get('public_ip')
        self.private_ip = self.parameters.get('private_ip')
        self.public_hostname = self.parameters.get('public_hostname')
        self.private_hostname = self.parameters.get('private_hostname')
        self.public = self.parameters.get('public') if 'public' in self.parameters else False
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

        if not self.host_password:
            raise ProvisionerError('WinRM provisioner requires host_password property to be set')

    @staticmethod
    def upload():
        logger.warning("Upload not implemented")

    def run(self):
        if self.use_private_ip:
            hostname = self.private_ip
        else:
            hostname = self.public_ip

        url = f"https://{hostname}:5986/wsman"

        if not self.wait_port(hostname):
            raise ProvisionerError(f"Host {hostname} is not reachable")

        logger.info(f"Connection to {hostname} successful")
        time.sleep(0.5)

        _command = self.resolve_variables(self.command)

        logger.info(f"Connecting to {hostname} as {self.username}")
        logger.debug(f"Running command: {_command}")

        s = winrm.Session(url, auth=(self.username, self.host_password), transport='ntlm', server_cert_validation='ignore')

        if not self.wait_service(s):
            raise ProvisionerError(f"WinRM service unavailable on {hostname}")

        r = s.run_ps(_command)

        for line in r.std_out.decode('utf-8').splitlines():
            line_out = line.strip()
            if len(line_out) == 0:
                continue
            log_out = f"{hostname}: {line_out}"
            logger.info(log_out)

        return r.status_code

    @staticmethod
    def wait_port(address: str, port: int = 5986, retry_count=300, factor=0.1):
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

    @staticmethod
    def wait_service(session: winrm.Session, retry_count=300, factor=0.1):
        for retry_number in range(retry_count + 1):
            try:
                session.run_cmd('whoami')
                return True
            except Exception as err:
                logger.debug(f"WinRM unavailable: {err}")
                if retry_number == retry_count:
                    return False
                logger.info(f"Waiting for provisioner service")
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
