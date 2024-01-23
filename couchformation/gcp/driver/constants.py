##
##

import attr
import os
from pathlib import Path

CLOUD_KEY = "gcp"


def get_auth_directory():
    if os.name == 'nt':
        return os.path.join(os.environ['APPDATA'], 'gcloud')
    else:
        return os.path.join(Path.home(), '.config', 'gcloud')


def get_default_credentials():
    if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
        return os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    else:
        return os.path.join(get_auth_directory(), 'application_default_credentials.json')


@attr.s
class GCPDiskTypes(object):
    disk_type_list = [
        {
            "type": 'pd-standard'
        },
        {
            "type": 'pd-balanced'
        },
        {
            "type": 'pd-ssd'
        }
    ]


@attr.s
class GCPImageProjects(object):
    projects = [
        {
            "project": 'centos-cloud',
            "description": "CentOS Linux",
            "os_id": "centos",
            "user": "centos",
            "pattern": "centos-stream-(.+?)-v*"
        },
        {
            "project": 'debian-cloud',
            "description": "Debian Linux",
            "os_id": "debian",
            "user": "admin",
            "pattern": "debian-(.+?)-*-v*"
        },
        {
            "project": 'fedora-cloud',
            "description": "Fedora Linux",
            "os_id": "fedora",
            "user": "fedora",
            "pattern": "fedora-cloud-base-gcp-(.+?)-1-2-x86-64"
        },
        {
            "project": 'opensuse-cloud',
            "description": "OpenSUSE Linux",
            "os_id": "opensuse-leap",
            "user": "admin",
            "pattern": "opensuse-leap-(.+?)-*-v*"
        },
        {
            "project": 'rhel-cloud',
            "description": "Red Hat Enterprise Linux",
            "os_id": "rhel",
            "user": "admin",
            "pattern": "rhel-(.+?)-v*"
        },
        {
            "project": 'rocky-linux-cloud',
            "description": "Rocky Linux",
            "os_id": "rocky",
            "user": "rocky",
            "pattern": "rocky-linux-(.+?)-v*"
        },
        {
            "project": 'suse-cloud',
            "description": "SUSE Linux Enterprise Server",
            "os_id": "sles",
            "user": "admin",
            "pattern": "sles-(.+?)-*-v*"
        },
        {
            "project": 'ubuntu-os-cloud',
            "description": "Ubuntu Linux",
            "os_id": "ubuntu",
            "user": "ubuntu",
            "pattern": r"ubuntu-(.+?)-*-v*"
        },
        {
            "project": 'ubuntu-os-pro-cloud',
            "description": "Ubuntu Pro Linux",
            "os_id": "ubuntu",
            "user": "ubuntu",
            "pattern": r"ubuntu-pro-(.+?)-*-v*"
        },
        {
            "project": 'windows-cloud',
            "description": "Windows Server",
            "os_id": "windows",
            "user": "adminuser",
            "pattern": r"windows-server-(.+?)-dc-v*"
        }
    ]


@attr.s
class ComputeTypes(object):
    general_purpose = ['n2', 't2a', 'n2d']
    compute_optimized = ['c2', 'c2d']
    memory_optimized = ['m2', 'm3']

    def as_list(self) -> list:
        flat_list = []
        for element in [self.general_purpose, self.compute_optimized, self.memory_optimized]:
            flat_list.extend(element)
        return flat_list
