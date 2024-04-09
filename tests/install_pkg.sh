#!/bin/bash

apt-get update
apt-get install -q -y python3 python3-dev python3-venv python3-pip git

pip3 install --user git+https://github.com/mminichino/couch-formation-core

echo "export PATH=$(python3 -m site --user-base)/bin:$PATH" >> /root/.bashrc
