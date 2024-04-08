#!/bin/bash

pip3 install --user git+https://github.com/mminichino/couch-formation-core

echo "export PATH=$(python3 -m site --user-base)/bin:$PATH" >> /root/.bashrc
