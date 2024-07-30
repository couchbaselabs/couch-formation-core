##
##

import base64
import ipaddress
import datetime
from typing import List
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_der_private_key
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


class CertMgr(object):

    def __init__(self):
        pass

    @staticmethod
    def private_key(size=2048):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=size,
            backend=default_backend(),
        )
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        return base64.b64encode(pem.encode()).decode()

    @staticmethod
    def certificate_hostname(filename: str, private_key: str, domain_name: str = None, alt_name: List[str] = None, alt_ip_list: List[str] = None):
        one_day = datetime.timedelta(1, 0, 0)
        with open(private_key, 'r') as pem_in:
            privkey = pem_in.read()
        private_key = load_pem_private_key(privkey.encode(), None, default_backend())
        public_key = private_key.public_key()

        cert_name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Santa Clara"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Couchbase")
        ])

        builder = x509.CertificateBuilder()
        builder = builder.subject_name(cert_name)
        builder = builder.issuer_name(cert_name)
        builder = builder.not_valid_before(datetime.datetime.today() - one_day)
        builder = builder.not_valid_after(datetime.datetime.today() + (one_day * 365 * 10))
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.public_key(public_key)

        host_names = []

        if alt_name is not None:
            for name in alt_name:
                host_names.append(x509.DNSName(name))

        if alt_ip_list is not None:
            for ip in alt_ip_list:
                host_names.append(x509.IPAddress(ipaddress.ip_address(ip)))

        if domain_name is not None:
            host_names.append(x509.DNSName(f"*.{domain_name}"))

        host_names.append(x509.IPAddress(ipaddress.ip_address('127.0.0.1')))

        builder = builder.add_extension(x509.SubjectAlternativeName(host_names), critical=True)
        builder = builder.add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        builder = builder.add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=True)
        builder = builder.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(public_key), critical=True)
        builder = builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=True)
        builder = builder.add_extension(x509.KeyUsage(
            digital_signature=True,
            key_encipherment=True,
            data_encipherment=False,
            content_commitment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False), critical=True)

        certificate = builder.sign(private_key=private_key, algorithm=hashes.SHA256(), backend=default_backend())

        cert = certificate.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        with open(filename, 'w') as f:
            f.write(cert)

    @staticmethod
    def certificate_basic(filename: str, private_key: str):
        one_day = datetime.timedelta(1, 0, 0)
        with open(private_key, 'r') as pem_in:
            privkey = pem_in.read()
        private_key = load_pem_private_key(privkey.encode(), None, default_backend())
        public_key = private_key.public_key()

        cert_name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Santa Clara"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Couchbase")
        ])

        builder = x509.CertificateBuilder()
        builder = builder.subject_name(cert_name)
        builder = builder.issuer_name(cert_name)
        builder = builder.not_valid_before(datetime.datetime.today() - one_day)
        builder = builder.not_valid_after(datetime.datetime.today() + (one_day * 365 * 10))
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.public_key(public_key)

        certificate = builder.sign(private_key=private_key, algorithm=hashes.SHA256(), backend=default_backend())

        cert = certificate.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        with open(filename, 'w') as f:
            f.write(cert)

    @staticmethod
    def certificate_ca(key: str):
        one_day = datetime.timedelta(1, 0, 0)
        private_key = load_pem_private_key(base64.b64decode(key), None, default_backend())
        public_key = private_key.public_key()

        cert_name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Santa Clara"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Couchbase")
        ])

        builder = x509.CertificateBuilder()
        builder = builder.subject_name(cert_name)
        builder = builder.issuer_name(cert_name)
        builder = builder.not_valid_before(datetime.datetime.today() - one_day)
        builder = builder.not_valid_after(datetime.datetime.today() + (one_day * 365 * 10))
        builder = builder.serial_number(x509.random_serial_number())
        builder = builder.public_key(public_key)
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True,
        )
        certificate = builder.sign(
            private_key=private_key, algorithm=hashes.SHA256(),
            backend=default_backend()
        )

        key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )

        cert_bytes = certificate.public_bytes(
            encoding=serialization.Encoding.PEM,
        )

        return base64.b64encode(cert_bytes).decode()
