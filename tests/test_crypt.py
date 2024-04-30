#!/usr/bin/env python3

import os
import sys
import argparse
from pathlib import Path

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)
sys.path.append(current)

from common import encrypt_file, decrypt_file, random_string


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-e', '--encrypt', action='store')
    parser.add_argument('-d', '--decrypt', action='store')
    parser.add_argument('-k', '--key', action='store')
    parser.add_argument('-g', '--keygen', action='store_true')
    parser.add_argument('-?', action='help')
    args = parser.parse_args()
    return args


def main():
    options = parse_args()
    key_file = os.path.join(Path.home(), '.crypt.key')

    if options.keygen:
        text = random_string(32)
        with open(key_file, 'w') as f:
            f.write(text)
            f.write('\n')
        return

    if not options.key:
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                key = f.readline().strip()
        else:
            raise FileNotFoundError("No key file found, use the -k option to specify a key")
    else:
        key = options.key

    file_name = options.encrypt if options.encrypt else options.decrypt
    if not Path(file_name).is_absolute():
        file_name = os.path.join(Path.home(), file_name)

    if options.encrypt:
        encrypt_file(file_name, key)
    elif options.decrypt:
        decrypt_file(file_name, key)


if __name__ == '__main__':
    main()
