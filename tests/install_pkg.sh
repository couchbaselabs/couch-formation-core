#!/bin/bash

echo "Begin container setup."
(
apt-get update
apt-get install -q -y python3 python3-dev python3-venv python3-pip git curl unzip

pip3 install --user git+https://github.com/mminichino/couch-formation-core

echo "export PATH=$(python3 -m site --user-base)/bin:$PATH" >> /root/.bashrc

curl "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "/var/tmp/awscliv2.zip"
cd /var/tmp || exit
unzip awscliv2.zip
./aws/install
) > /var/tmp/setup.log 2>&1
echo "Done."
