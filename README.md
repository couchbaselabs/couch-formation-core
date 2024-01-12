# Couch Formation 4.0.0a23

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
### Install (pip user local method):
````
pip3 install --user couchformation
````
````
export PATH=$(python3 -m site --user-base)/bin:$PATH
````
### Install (virtual environment method):
````
python3 -m venv couchformation
````
````
cd couchformation
````
````
. bin/activate
````
````
pip3 install couchformation
````

### Configure and deploy a Couchbase Server cluster:
````
cloudmgr create --build cbs --cloud gcp --project test-gcp --name test-cluster --region us-central1 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 4x16
````
### Deploy the project:
````
cloudmgr deploy --project test-gcp
````

## MDS example
### Create the initial service group:
```
cloudmgr create --build cbs --cloud aws --project dev01 --name testdb01 --region us-east-2 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32
```
### Add a second service group:
```
cloudmgr add --build cbs --cloud aws --project dev01 --name testdb01 --region us-east-2 --quantity 2 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32 --services analytics
```

## Multiservice project example
Configure a 3 node Couchbase Server cluster in US Ease, another 3 node Couchbase Server cluster in US West, plus a Linux generic node and a Windows generic node to run an application.
```
cloudmgr create --build cbs --cloud aws --project dev01 --name source01 --region us-east-2 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32
```
```
cloudmgr create --build cbs --cloud aws --project dev01 --name target01 --region us-west-2 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32
```
```
cloudmgr create --build generic --cloud aws --project dev01 --name app01 --region us-east-2 --quantity 1 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32
```
```
cloudmgr create --build generic --cloud aws --project dev01 --name app02 --region us-east-2 --quantity 1 --os_id windows --os_version 2022 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32
```

## Custom services example
```
cloudmgr create --build cbs --cloud aws --project eventing --name eventing01 --region us-east-2 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32 --services data,index,query,eventing
```

## Sync Gateway example
### Create the Couchbase Server cluster:
```
cloudmgr create --build cbs --cloud aws --project sgw-dev01 --name devdb01 --region us-east-2 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 4x16
```
### Create a Sync Gateway and connect to the cluster:
```
cloudmgr create --build sgw --cloud aws --project sgw-dev01 --name gateway --region us-east-2 --quantity 1 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 4x16 --connect devdb01
```

## Additional CLI examples
### Destroy a project:
```
cloudmgr destroy --project dev01
```

### List node IP addresses:
```
cloudmgr list --project dev01
```

### Operate on only one service in a project:
```
cloudmgr deploy --project dev01 --name source01
```

## AWS SSO Support
### Setup AWS CLI SSO:
```
aws configure sso
```
### SSO Integration:
Use the auth_mode option to enable SSO integration. Couch Formation will open a browser for you to complete the SSO process, or you will have to paste the link provided into a browser to continue.
```
cloudmgr create --build cbs --cloud aws --project dev01 --name testdb01 --auth_mode sso --region us-east-2 --quantity 3 --os_id ubuntu --os_version 22.04 --ssh_key /Users/jdoe/.ssh/jdoe-default-key-pair.pem --machine_type 8x32
```
