##
##
import logging
import distutils.spawn
import subprocess
import time
import re
import json
import datetime
import os
import couchformation.constants as C
from datetime import datetime
from typing import Union
from couchformation.exception import FatalError
from couchformation.util import FileManager
from couchformation.config import BaseConfig, DeploymentConfig

logger = logging.getLogger('couchformation.exec.process')
logger.addHandler(logging.NullHandler())


class ExecError(FatalError):
    pass


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


class TFRun(object):
    DEPLOYMENT_CONFIG = "deployment.cfg"

    def __init__(self, config: BaseConfig):
        self.working_dir = config.working_dir

        try:
            FileManager().make_dir(self.working_dir)
        except Exception as err:
            raise ExecError(f"can not create working dir: {err}")

        self.log_file = os.path.join(self.working_dir, 'deploy.log')
        self.file_output = logging.getLogger('couchformation.tfrun.output')
        self.file_output.propagate = False
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(CustomLogFormatter())
        self.file_output.addHandler(file_handler)
        self.file_output.setLevel(logging.DEBUG)

        self.deployment_data = None
        self.check_binary()

    def check_binary(self) -> bool:
        if not distutils.spawn.find_executable("terraform"):
            raise ExecError("can not find terraform executable")

        version = self._version()
        version_number = float('.'.join(version['terraform_version'].split('.')[:2]))

        if version_number < 1.2:
            raise ExecError("terraform 1.2.0 or higher is required")

        return True

    @staticmethod
    def parse_output(line: str) -> Union[dict, None]:
        line_string = line.rstrip()
        try:
            message = json.loads(line_string)
        except json.decoder.JSONDecodeError:
            return None

        return message

    def _terraform(self, *args: str, output=False, ignore_error=False):
        command_output = ''
        tf_cmd = [
            'terraform',
            *args
        ]
        self.file_output.info(f">>> Call: {' '.join(tf_cmd)}")

        if logging.DEBUG >= logging.root.level:
            os.environ["TF_LOG"] = "DEBUG"
            os.environ["TF_LOG_PATH"] = self.log_file

        p = subprocess.Popen(tf_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=self.working_dir, bufsize=1)

        while True:
            line = p.stdout.readline()
            if not line:
                break
            line_string = line.decode("utf-8")
            escape_char = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            line_string = escape_char.sub('', line_string)
            if output:
                command_output += line_string
            else:
                self.file_output.info(line_string.strip())

        p.communicate()

        if p.returncode != 0:
            if ignore_error:
                return False
            else:
                raise ExecError(f"environment deployment error (see deploy.log file for details)")

        if len(command_output) > 0:
            try:
                self.deployment_data = json.loads(command_output)
            except json.decoder.JSONDecodeError:
                self.deployment_data = command_output

        self.file_output.info(">>> Call Completed <<<")
        return True

    def _command(self, cmd: list, output=False, ignore_error=False):
        now = datetime.now()
        time_string = now.strftime("%D %I:%M:%S %p")
        self.file_output.info(f" --- start {cmd[0]} at {time_string}")

        start_time = time.perf_counter()
        result = self._terraform(*cmd, output=output, ignore_error=ignore_error)
        end_time = time.perf_counter()
        run_time = time.strftime("%H hours %M minutes %S seconds.", time.gmtime(end_time - start_time))

        now = datetime.now()
        time_string = now.strftime("%D %I:%M:%S %p")
        self.file_output.info(f" --- end {cmd[0]} at {time_string}")

        self.file_output.info(f"Step complete in {run_time}.")

        return result

    def store_deployment_cfg(self, deployment: DeploymentConfig):
        deployment_data = {
            'core': deployment.core.as_dict,
            'config': []
        }
        for node_config in deployment.config:
            deployment_data['config'].append(node_config.as_dict)
        self.write_file(deployment_data, TFRun.DEPLOYMENT_CONFIG)

    def get_deployment_cfg(self):
        config_data = self.read_file(TFRun.DEPLOYMENT_CONFIG)
        return config_data

    def deploy(self, config_data: dict):
        self.write_file(config_data, "main.tf.json")
        self._init()
        if not self._validate():
            raise ExecError("Configuration validation failed, please check the log and try again.")
        self._apply()

    def destroy(self):
        if not self._validate():
            self._init()
        self._destroy()

    def output(self):
        return self._output()

    def read_file(self, name: str):
        cfg_file = os.path.join(self.working_dir, name)
        try:
            with open(cfg_file, 'r') as cfg_file_h:
                data = json.load(cfg_file_h)
                return data
        except FileNotFoundError:
            return None
        except Exception as err:
            raise ExecError(f"can not read from config file {cfg_file}: {err}")

    def write_file(self, data: dict, name: str):
        cfg_file = os.path.join(self.working_dir, name)
        try:
            with open(cfg_file, 'w') as cfg_file_h:
                json.dump(data, cfg_file_h, indent=2)
                cfg_file_h.write('\n')
        except Exception as err:
            raise ExecError(f"can not write to config file {cfg_file}: {err}")

    def _init(self):
        cmd = ['init', '-input=false']

        self.file_output.info("Initializing environment")
        self._command(cmd)

    def _apply(self):
        cmd = ['apply', '-input=false', '-auto-approve']

        self.file_output.info("Deploying environment")

        self._command(cmd)

    def _destroy(self, refresh=True, ignore_error=False):
        cmd = ['destroy', '-input=false', '-auto-approve']

        if not refresh:
            cmd.append('-refresh=false')
        else:
            ignore_error = True

        self.file_output.info("Removing resources")

        if not self._command(cmd, ignore_error=ignore_error):
            self.file_output.warning("First destroy attempt failed, retrying without refresh ...")
            self._destroy(refresh=False, ignore_error=False)

    def _validate(self):
        cmd = ['validate']

        return self._command(cmd, ignore_error=True)

    def _output(self):
        cmd = ['output', '-json']

        self.file_output.info("Getting environment information")

        self._command(cmd, output=True)

        return self.deployment_data

    def _version(self):
        cmd = ['version', '-json']

        self._command(cmd, output=True)

        return self.deployment_data

    def _list(self):
        cmd = ['state', 'list']

        self._command(cmd, output=True)

        return self.deployment_data

    def _remove(self, resource):
        cmd = ['state', 'rm', resource]

        self._command(cmd)
