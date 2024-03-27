#!/usr/bin/env python3

import sys
import argparse
import tempfile
import jinja2
import os
from common import start_container, stop_container, get_container_ip, run_in_container


sync_gateway_config = """{
  "bootstrap": {
   "group_id": "group1",
   "server": "couchbases://{{ COUCHBASE_SERVER }}",
   "username": "{{ USERNAME }}",
   "password": "{{ PASSWORD }}",
   "server_tls_skip_verify": true,
   "use_tls_server": true
  },
  "api": {
    "admin_interface": ":4985"
  },
  "logging": {
    "log_file_path": "{{ ROOT_DIRECTORY }}/logs",
    "redaction_level": "partial",
    "console": {
      "log_level": "debug",
      "log_keys": ["*"]
      },
    "error": {
      "enabled": true,
      "rotation": {
        "max_size": 20,
        "max_age": 180
        }
      },
    "warn": {
      "enabled": true,
      "rotation": {
        "max_size": 20,
        "max_age": 90
        }
      },
    "info": {
      "enabled": true,
      "rotation": {
        "max_size": 20,
        "max_age": 90
        }
      },
    "debug": {
      "enabled": false
      }
  }
}
"""


class Params(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--start', action='store_true', help="Start Container")
        parser.add_argument('--stop', action='store_true', help="Stop Container")
        self.args = parser.parse_args()

    @property
    def parameters(self):
        return self.args


def copy_config_file(connect_ip: str = "127.0.0.1",
                     username: str = "Administrator",
                     password: str = "password",
                     bucket: str = "default",
                     root_path: str = "/home/sync_gateway"):
    dest = os.path.join(root_path, 'sync_gateway.json')
    env = jinja2.Environment(undefined=jinja2.DebugUndefined)
    raw_template = env.from_string(sync_gateway_config)
    formatted_value = raw_template.render(
        COUCHBASE_SERVER=connect_ip,
        USERNAME=username,
        PASSWORD=password,
        BUCKET=bucket,
        ROOT_DIRECTORY=root_path
    )
    with open(dest, 'w') as out_file:
        out_file.write(formatted_value)
        out_file.close()


def container_start():
    dir_name = tempfile.mkdtemp(dir='/tmp')
    start_container("couchbase/server", "cbs", "/opt/couchbase/var", ports="8091-8097,18091-18097,9102,11207,11210")
    run_in_container("cbs",
                     [
                      'sh',
                      '-c',
                      'curl -sfL https://raw.githubusercontent.com/mminichino/host-prep-lib/main/bin/setup.sh | bash -s - -s -g https://github.com/mminichino/host-prep-lib'
                     ])
    run_in_container("cbs", 'swmgr cluster create -n testdb')
    ip_address = get_container_ip("cbs")
    copy_config_file(connect_ip=ip_address, root_path=dir_name)
    command = "/tmp/config/sync_gateway.json"
    start_container("couchbase/sync-gateway", "sgw", dir_mount=dir_name, volume_mount="/tmp/config", ports="4984-4985", command=command)


def container_stop():
    stop_container("sgw")
    stop_container("cbs")


p = Params()
options = p.parameters

if options.start:
    container_start()
    sys.exit(0)

if options.stop:
    container_stop()
    sys.exit(0)
