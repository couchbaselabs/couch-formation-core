# Couch Formation 4.0.0a15

![Logo](https://raw.githubusercontent.com/mminichino/couch-formation-core/main/doc/couch-formation-1.png)

Toolset for running and managing Couchbase assets in the cloud.

## Disclaimer

> This package is **NOT SUPPORTED BY COUCHBASE**. The toolset is under active development, therefore features and functionality can change.

## Prerequisites
- Python 3.8+
- Cloud CLI/SDKs
  - [AWS CLI](https://aws.amazon.com/cli/)
  - [Google Cloud CLI](https://cloud.google.com/sdk/docs/quickstart)
  - [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- Homebrew (for macOS)

## Quick Start
Install:
````
$ pip install couchformation
````

## Configure and deploy a Couchbase Server cluster:
````
$ cloudmgr create --build cbs --cloud gcp --project test-gcp --name test-cluster --region us-central1 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 4x16
````
````
$ cloudmgr deploy --project test-gcp
````
