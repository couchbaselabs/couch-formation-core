##
##

import logging
import io
import subprocess
from typing import Union, List

logger = logging.getLogger('couchformation.exec.process')
logger.addHandler(logging.NullHandler())


def cmd_exec(command: Union[str, List[str]], directory: Union[str, None] = None) -> io.BytesIO:
    buffer = io.BytesIO()

    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=directory)

    while True:
        data = p.stdout.read()
        if not data:
            break
        buffer.write(data)

    p.communicate()

    if p.returncode != 0:
        raise ValueError("command exited with non-zero return code")

    buffer.seek(0)
    return buffer


def get_output_buffer(buffer: io.BytesIO):
    while True:
        line = buffer.readline()
        if not line:
            break
        line_string = line.decode("utf-8")
        yield line_string
