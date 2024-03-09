##
##

import os
import logging
import jinja2
from couchformation.config import get_state_dir
from couchformation.docker.driver.container import Container
import couchformation.constants as C

logger = logging.getLogger('couchformation.provisioner.docker')
logger.addHandler(logging.NullHandler())
logging.getLogger("docker").setLevel(logging.WARNING)


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


class ContainerExec(object):

    def __init__(self, parameters: dict, command: str = '', root: bool = True):
        self.parameters = parameters
        self.command = command
        self.root = root
        self.container_name = self.parameters.get('name')
        self.service = self.parameters.get('service')
        self.project = self.parameters.get('project')
        self.public_ip = self.parameters.get('public_ip')
        self.private_ip = self.parameters.get('private_ip')
        self.services = self.parameters.get('services')
        self.connect = ','.join(self.parameters.get('connect')) \
            if self.parameters.get('connect') and type(self.parameters.get('connect')) is list \
            else self.parameters.get('connect')
        self.private_ip_list = ','.join(self.parameters.get('private_ip_list'))
        self.use_private_ip = self.parameters.get('use_private_ip') if self.parameters.get('use_private_ip') else False

    @staticmethod
    def copy():
        logger.warning("File copy not implemented")

    def run(self):
        working_dir = get_state_dir(self.project, self.service)
        file_output = logging.getLogger('couchformation.provisioner.output')
        file_output.propagate = False
        log_file = os.path.join(working_dir, 'provision.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(CustomLogFormatter())
        file_output.addHandler(file_handler)
        file_output.setLevel(logging.DEBUG)

        command = self.command

        _command = self.resolve_variables(command)

        logger.info(f"Connecting to {self.container_name}")
        logger.debug(f"Running command: {_command}")

        file_output.info(f"{self.container_name}: [{_command}] begins")

        exit_code, output = Container(self.parameters).run_in_container(self.container_name, _command)

        for line in output.readlines():
            if not line:
                break
            line_out = line.decode("utf-8").strip()
            log_out = f"{self.container_name}: {line_out}"
            logger.info(log_out)
            file_output.info(log_out)

        file_output.info(f"{self.container_name}: [{_command}] complete")

        logger.info(f"Command complete for {self.container_name}")
        logger.debug(f"[{_command}] returned {exit_code} on {self.container_name}")

        file_output.removeHandler(file_handler)
        file_handler.close()
        return exit_code

    def resolve_variables(self, line: str):
        env = jinja2.Environment(undefined=jinja2.DebugUndefined)
        raw_template = env.from_string(line)
        formatted_value = raw_template.render(
            SERVICE_NAME=self.service,
            PRIVATE_IP_LIST=self.private_ip_list,
            SERVICES=self.services,
            CONNECT_SERVICE=self.connect,
            CONNECT_IP=self.connect,
            CONNECT_LIST=self.connect if self.connect else '127.0.0.1'
        )
        return formatted_value
