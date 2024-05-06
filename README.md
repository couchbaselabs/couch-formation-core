![](https://raw.githubusercontent.com/mminichino/couch-formation-core/main/doc/couch-formation-1.png)
# Couch Formation 4.0.0a320
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
### Install directly from GitHub repo:
````
pip3 install --user git+https://github.com/couchbaselabs/couch-formation-core
````

## Basic example
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

## Capella example
For Capella the Couch Formation project aligns with the Capella project.
```
cloudmgr create --build capella --cloud capella --project test-project --name test-cluster --region us-east-2 --quantity 3 --provider aws --machine_type 4x16
```
Optionally create an app service (Sync Gateway in Capella) and attach it to a Capella database.
```
cloudmgr create --build capella --cloud capella --project test-project --name test-app-svc --quantity 2 --machine_type 4x8 --type mobile --connect test-cluster
```

## Additional commands
### Destroy a project:
```
cloudmgr destroy --project dev01
```

### List node details (including IP addresses and generated passwords):
```
cloudmgr list --project dev01
```

### Operate on only one service in a project:
```
cloudmgr deploy --project dev01 --name source01
```

### List all projects and services:
```
cloudmgr list
```

### Display detailed information about configured services in a project:
```
cloudmgr show --project dev01
```

### Recall the CLI commands that were used to add services to a project (you can use this to copy and paste to create a new project):
```
cloudmgr cli --project dev01
```

### Change the values for parameters in a previously created service:
```
cloudmgr update --project dev01 --name node --machine_type 8x32
```

### Change the values for parameters for a service node group:
```
cloudmgr update --project dev01 --name testdb --group 2 --machine_type 4x16
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

## AWS Default Authentication
Configure the AWS CLI via an appropriate method based on your IAM settings. For example use ```aws configure``` to configure long term credentials, or manually set the access parameters in ```.aws/credentials``` or with environment variables. Couch Formation accepts an optional ```--profile``` service configuration parameter to use a specific auth profile. Check [here](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html#getting-started-quickstart-new) for more information.

## GCP Default Authentication
For Google Cloud use ```gcloud auth application-default login``` to configure CLI access.  Check [here](https://cloud.google.com/sdk/gcloud/reference/auth) for more information.

## Azure Default Authentication
For Azure use ```az login``` to configure CLI access. Check [here](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli-interactively) for more information.

## Capella Support
### Credentials Directory
The automation for Capella uses the v4 public API. To use the automation, create an API key in the Capella UI and save it to a file named ```default-api-key-token.txt``` in a directory named ```.capella``` in your home directory.
```
.capella
├── credentials
├── default-api-key-token.txt
├── project-api-key-token.txt
└── test-api-key-token.txt
```
Credentials file format:
```
[default]
api_host = cloudapi.cloud.couchbase.com
token_file = default-api-key-token.txt
account_email = john.doe@example.com

[project]
token_file = project-api-key-token.txt
```
## Windows
Download and install a 64-bit version of Python 3.8+ from [here](https://www.python.org/downloads/windows/). Use the ```Run as Administrator``` option to start PowerShell and then install Couch Formation with ```pip```. Once the installation is complete, it will be available for all users (launch a PowerShell window as your login user to use Couch Formation). You should install the ```wheel``` pacakge before you install Couch Formation.
```
pip3 install wheel
```
```
pip3 install couchformation
```
## Operating System Information

| ID            | Operating System         | Versions     | AWS User      | GCP User  | Azure User |
|---------------|--------------------------|--------------|---------------|-----------|------------|
| amzn          | Amazon Linux             | 2, 2023      | ec2-user      | N/A       | N/A        |
| rhel          | Red Hat Enterprise Linux | 8, 9         | ec2-user      | admin     | rhel       |
| centos        | CentOS                   | 8            | centos        | centos    | centos     |
| ol            | Oracle Linux             | 8, 9         | ec2-user      | N/A       | N/A        |
| rocky         | Rocky Linux              | 8, 9         | rocky         | rocky     | N/A        |
| fedora        | Fedora                   | 34           | core          | fedora    | N/A        |
| sles          | SUSE Linux               | 12, 15       | ec2-user      | admin     | sles       |
| opensuse-leap | openSUSE                 | 15           | ec2-user      | admin     | sles       |
| ubuntu        | Ubuntu Linux             | 20.04, 22.04 | ubuntu        | ubuntu    | ubuntu     |
| debian        | Debian Linux             | 10, 11       | admin         | admin     | debian     |
| windows       | Windows Server           | 2019, 2022   | Administrator | adminuser | adminuser  |
| macos         | macOS                    | 13, 14       | ec2-user      | N/A       | N/A        |

## Build Types

| Build Type | Description                     |
|------------|---------------------------------|
| cbs        | Couchbase Server                |
| sgw        | Sync Gateway                    |
| capella    | Capella Database                |
| generic    | Base configured node from image |
| database   | Generic database node           |
| windev     | Windows development host        |

## Troubleshooting
Log files are written to ```.config/couch-formation/log```.
<br><br>
To create a support bundle with diagnostic information, use the ```dump``` command.
```
cloudmgr dump
```
