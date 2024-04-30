#!/usr/bin/env python3
#
import subprocess
import sys
import os

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

if __name__ == '__main__':
    os.environ['PYTHONSTARTUP'] = os.path.join(current, 'interactive.py')
    result = subprocess.run(["python"])
