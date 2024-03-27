##
##

from typing import Union, List
import subprocess
import logging
import io

logger = logging.getLogger('couchformation.provisioner.shell')
logger.addHandler(logging.NullHandler())


class ShellCommandError(Exception):
    pass


class RCNotZero(Exception):
    pass


class RunShellCommand(object):

    def __init__(self):
        pass

    @staticmethod
    def cmd_exec(command: Union[str, List[str]], directory: str):
        buffer = io.BytesIO()
        logger.debug(f"Shell command: {' '.join(command)}")

        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=directory)

        while True:
            data = p.stdout.read()
            if not data:
                break
            buffer.write(data)

        p.communicate()
        buffer.seek(0)

        if p.returncode != 0:
            output_text = buffer.read().decode("utf-8").strip()
            raise ShellCommandError(f"command error: {output_text}")

        return buffer

    @staticmethod
    def cmd_output(command: Union[str, List[str]], directory: str, split: bool = False, split_sep: str = None, no_raise: bool = False):
        out_lines = []
        try:
            output: io.BytesIO = RunShellCommand().cmd_exec(command, directory)
        except ShellCommandError as err:
            if not no_raise:
                raise RCNotZero(err)
            else:
                return None

        while True:
            line = output.readline()
            if not line:
                break
            line_string = line.decode("utf-8").strip()
            if len(line_string) > 0:
                if split:
                    items = line_string.split(split_sep)
                    out_lines.append(items)
                else:
                    out_lines.append(line_string)

        return out_lines
