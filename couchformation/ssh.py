##
##

import logging
import os
import rsa
from pathlib import Path
from enum import Enum
from typing import Union, List
from Crypto.PublicKey import RSA
from Crypto.Util.number import long_to_bytes
from Crypto.Cipher import PKCS1_OAEP
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa as rsa_primitive
import hashlib
from cryptography.exceptions import UnsupportedAlgorithm
from couchformation.exception import FatalError, NonFatalError
from couchformation.util import FileManager

logger = logging.getLogger('couchformation.ssh')
logger.addHandler(logging.NullHandler())
HOME_DIRECTORY = str(Path.home())
SSH_DIRECTORY = os.path.join(HOME_DIRECTORY, '.ssh')

SSH_PATHS = [
    HOME_DIRECTORY + '/.ssh',
    HOME_DIRECTORY,
    HOME_DIRECTORY + '/Documents',
    HOME_DIRECTORY + '/Downloads'
]


class SSHExtensions(Enum):
    PEM = ".pem"
    DER = ".der"
    KEY = ".key"


class OpenSSHExtensions(Enum):
    PUB = ".pub"


class SSHError(FatalError):
    pass


class EmptyResultSet(NonFatalError):
    pass


class SSHUtil(object):

    def __init__(self):
        pass

    @staticmethod
    def ssh_key_absolute_path(name: str) -> Union[str, None]:
        for location in SSH_PATHS:
            for file_found in os.listdir(location):
                if file_found == name or next((f"{name}{e.value}" for e in SSHExtensions if f"{name}{e.value}" == file_found), None):
                    return location + '/' + file_found
        return None

    @staticmethod
    def decrypt_with_key(encrypted_data: bytes, key_file: str) -> str:
        try:
            with open(key_file, 'r') as file_handle:
                blob = file_handle.read()
                private_key = rsa.PrivateKey.load_pkcs1(blob.encode('latin-1'))
                decrypted = rsa.decrypt(encrypted_data, private_key)
                return decrypted.decode('utf-8')
        except OSError as err:
            raise SSHError(f"can not read key file {key_file}: {err}.")

    @staticmethod
    def list_private_key_files() -> Union[List[dict], None]:
        dir_list = []
        key_file_list = []

        for location in SSH_PATHS:
            for file_name in os.listdir(location):
                full_path = location + '/' + file_name
                dir_list.append(full_path)

        for i in range(len(dir_list)):
            if not os.path.isfile(dir_list[i]) or not os.access(dir_list[i], os.R_OK):
                continue

            file_ext = os.path.splitext(dir_list[i])
            if file_ext[0] != "id_rsa":
                if not next((e for e in SSHExtensions if e.value == file_ext[1]), None):
                    continue

            file_handle = open(dir_list[i], 'r')
            blob = file_handle.read()
            pem_key_bytes = str.encode(blob)

            try:
                key = serialization.load_pem_private_key(
                    pem_key_bytes, password=None, backend=default_backend()
                )
            except (ValueError, TypeError, UnsupportedAlgorithm):
                continue

            key_entry = {"file": dir_list[i]}
            pri_der = key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            der_digest = hashlib.sha1(pri_der)
            hex_digest = der_digest.hexdigest()
            key_fingerprint = ':'.join(hex_digest[i:i + 2] for i in range(0, len(hex_digest), 2))
            key_entry.update({"fingerprint": key_fingerprint})
            pub_der = key.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo
            )
            pub_der_digest = hashlib.md5(pub_der)
            pub_hex_digest = pub_der_digest.hexdigest()
            pub_key_fingerprint = ':'.join(pub_hex_digest[i:i + 2] for i in range(0, len(pub_hex_digest), 2))
            key_entry.update({"pub_fingerprint": pub_key_fingerprint})

            key_file_list.append(key_entry)

        if len(key_file_list) == 0:
            raise EmptyResultSet("No SSH keys found. Please make sure you have at least one SSH key configured.")

        return key_file_list

    def get_key_by_fingerprint(self, fingerprint: str):
        key_list = self.list_private_key_files()
        for key in key_list:
            if key['fingerprint'] == fingerprint or key['pub_fingerprint'] == fingerprint:
                return key['file']
        return None

    @staticmethod
    def get_ssh_public_key(key_file: str) -> str:
        if not os.path.isabs(key_file):
            key_file = SSHUtil.ssh_key_absolute_path(key_file)
        fh = open(key_file, 'r')
        key_pem = fh.read()
        fh.close()
        rsa_key = RSA.importKey(key_pem)
        modulus = rsa_key.n
        pub_exp_e = rsa_key.e
        pri_exp_d = rsa_key.d
        prime_p = rsa_key.p
        prime_q = rsa_key.q
        private_key = RSA.construct((modulus, pub_exp_e, pri_exp_d, prime_p, prime_q))
        public_key = private_key.public_key().exportKey('OpenSSH')
        ssh_public_key = public_key.decode('utf-8')
        return ssh_public_key

    @staticmethod
    def get_mod_exp(key_file: str):
        if not os.path.isabs(key_file):
            key_file = SSHUtil.ssh_key_absolute_path(key_file)
        fh = open(key_file, 'r')
        key_pem = fh.read()
        fh.close()
        rsa_key = RSA.importKey(key_pem)
        modulus = long_to_bytes(rsa_key.n)
        exponent = long_to_bytes(rsa_key.e)
        return modulus, exponent

    @staticmethod
    def decrypt_with_rsa(encrypted_data: bytes, key_file: str):
        if not os.path.isabs(key_file):
            key_file = SSHUtil.ssh_key_absolute_path(key_file)
        fh = open(key_file, 'r')
        key_pem = fh.read()
        fh.close()
        rsa_key = RSA.importKey(key_pem)
        cipher = PKCS1_OAEP.new(rsa_key)
        return cipher.decrypt(encrypted_data)

    @staticmethod
    def write_file(file_name: str, data: str) -> bool:
        try:
            file_handle = open(file_name, 'w')
            file_handle.write(data)
            file_handle.write("\n")
            file_handle.close()
            return True
        except OSError as err:
            raise SSHError(f"can not write to file {file_name}: {err}.")

    @staticmethod
    def get_ssh_public_key_file(key_file: str) -> str:
        dir_list = []

        if not os.path.isabs(key_file):
            key_file = SSHUtil.ssh_key_absolute_path(key_file)

        gen_public_key = SSHUtil.get_ssh_public_key(key_file)

        for location in SSH_PATHS:
            for file_name in os.listdir(location):
                full_path = location + '/' + file_name
                dir_list.append(full_path)

        for i in range(len(dir_list)):
            if not os.path.isfile(dir_list[i]) or not os.access(dir_list[i], os.R_OK):
                continue
            file_handle = open(dir_list[i], 'r')
            try:
                public_key = file_handle.readline()
            except (UnicodeDecodeError, IOError):
                continue
            file_size = os.fstat(file_handle.fileno()).st_size
            read_size = len(public_key)
            if file_size != read_size:
                continue
            public_key = public_key.rstrip()
            key_parts = public_key.split(' ')
            pub_key_part = ' '.join(key_parts[0:2])
            pub_key_bytes = str.encode(pub_key_part)
            try:
                serialization.load_ssh_public_key(pub_key_bytes)
            except (ValueError, UnsupportedAlgorithm):
                continue
            if gen_public_key == public_key:
                return dir_list[i]

        private_key_dir = os.path.dirname(key_file)
        private_key_file = os.path.basename(key_file)
        private_key_name = os.path.splitext(private_key_file)[0]
        pub_file_name = private_key_dir + '/' + private_key_name + '.pub'

        SSHUtil.write_file(pub_file_name, gen_public_key)

        return pub_file_name

    @staticmethod
    def create_key_pair(key_file: str, overwrite: bool = False):
        key = rsa_primitive.generate_private_key(backend=default_backend(), public_exponent=65537, key_size=2048)
        private_key = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
        public_key = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)

        pub_file_name = os.path.join(SSH_DIRECTORY, key_file + OpenSSHExtensions.PUB.value)
        pem_file_name = os.path.join(SSH_DIRECTORY, key_file + SSHExtensions.PEM.value)

        if os.path.exists(pub_file_name) and not overwrite:
            raise SSHError(f"File {pub_file_name} already exists")
        if os.path.exists(pem_file_name) and not overwrite:
            raise SSHError(f"File {pem_file_name} already exists")

        try:
            if not os.path.exists(SSH_DIRECTORY):
                FileManager().make_dir(SSH_DIRECTORY)
        except Exception as err:
            raise SSHError(f"can not create ssh dir: {err}")

        SSHUtil.write_file(pub_file_name, public_key.decode('utf-8'))
        logger.info(f"created ssh public key: {pub_file_name}")
        SSHUtil.write_file(pem_file_name, private_key.decode('utf-8'))
        logger.info(f"created ssh private key: {pem_file_name}")

        return pub_file_name, pem_file_name
