##
##

import base64
import logging
import re
import time
import botocore.exceptions
from datetime import datetime, timezone
from typing import Union, List
from couchformation.aws.driver.base import CloudBase, AWSDriverError
from couchformation.aws.driver.constants import AWSEbsDisk, AWSTagStruct, EbsVolume, AWSTag, PlacementType
from couchformation.ssh import SSHUtil

logger = logging.getLogger('couchformation.aws.driver.instance')
logger.addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

WIN_USER_DATA = """<powershell>
winrm quickconfig -q -force
winrm set winrm/config/service/auth '@{Basic="true"}'
$hostname = $env:computername
$certificateThumbprint = (New-SelfSignedCertificate -DnsName "${hostname}" -CertStoreLocation Cert:\LocalMachine\My).Thumbprint
winrm create winrm/config/Listener?Address=*+Transport=HTTPS "@{Hostname=`"${hostname}`"; CertificateThumbprint=`"${certificateThumbprint}`"}"
netsh advfirewall firewall add rule name="Windows Remote Management (HTTPS-In)" dir=in action=allow protocol=TCP localport=5986
</powershell>
"""


class Instance(CloudBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self,
            name: str,
            ami: str,
            ssh_key: str,
            sg_list: Union[str, List[str]],
            subnet: str,
            zone: str,
            root_size=256,
            swap_size=16,
            swap_iops=3000,
            data_size=256,
            data_iops=3000,
            instance_type="t2.micro",
            placement: PlacementType = PlacementType.ZONE,
            host_id: str = None,
            enable_winrm: bool = False):
        volume_type = "gp3"
        kwargs = {}
        try:
            ami_details = self.image_details(ami)
        except Exception as err:
            raise AWSDriverError(f"error getting AMI {ami} details: {err}")
        if 'BlockDeviceMappings' not in ami_details:
            raise AWSDriverError(f"can not get details for AMI {ami}")

        root_dev = ami_details['BlockDeviceMappings'][0]['DeviceName']
        match = re.search(r"/dev/(.+?)a[0-9]*", root_dev)
        root_disk_prefix = f"/dev/{match.group(1)}"
        disk_list = [
            AWSEbsDisk.build(root_dev, EbsVolume(volume_type, root_size, 3000)).as_dict,
            AWSEbsDisk.build(f"{root_disk_prefix}b", EbsVolume(volume_type, swap_size, swap_iops)).as_dict,
            AWSEbsDisk.build(f"{root_disk_prefix}c", EbsVolume(volume_type, data_size, data_iops)).as_dict,
        ]
        instance_tag = [AWSTagStruct.build("instance").add(AWSTag("Name", name)).as_dict]

        if placement == PlacementType.ZONE:
            placement = {"AvailabilityZone": zone}
        else:
            placement = {"Tenancy": "host"}
            if host_id:
                placement.update({"HostId": host_id})

        if enable_winrm:
            kwargs['UserData'] = WIN_USER_DATA

        if type(sg_list) is str:
            security_groups = [sg_list]
        else:
            security_groups = sg_list

        try:
            result = self.ec2_client.run_instances(BlockDeviceMappings=disk_list,
                                                   ImageId=ami,
                                                   InstanceType=instance_type,
                                                   KeyName=ssh_key,
                                                   MaxCount=1,
                                                   MinCount=1,
                                                   SecurityGroupIds=security_groups,
                                                   SubnetId=subnet,
                                                   Placement=placement,
                                                   TagSpecifications=instance_tag,
                                                   **kwargs)
        except Exception as err:
            raise AWSDriverError(f"error running instance: {err}")

        instance_id = result['Instances'][0]['InstanceId']
        waiter = self.ec2_client.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])

        return instance_id

    def list(self):
        instances = []
        extra_args = {}

        try:
            while True:
                result = self.ec2_client.describe_instances(**extra_args)
                for reservation in result.get('Reservations', []):
                    instances.extend(reservation.get('Instances', []))
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting instance list: {err}")

        return instances

    def allocate_host(self, name: str, zone: str, instance_type: str):
        host_tag = [AWSTagStruct.build("dedicated-host").add(AWSTag("Name", name)).as_dict]

        try:
            result = self.ec2_client.allocate_hosts(AvailabilityZone=zone,
                                                    InstanceType=instance_type,
                                                    AutoPlacement='on',
                                                    Quantity=1,
                                                    TagSpecifications=host_tag)
            return result['HostIds'][0]
        except Exception as err:
            raise AWSDriverError(f"error getting instance details: {err}")

    def list_hosts(self, instance_type: str = None):
        hosts = []
        host_list = []
        extra_args = {}
        machine_filter = []

        if instance_type:
            machine_filter = [
                {
                    'Name': 'instance-type',
                    'Values': [
                        instance_type,
                    ]
                }
            ]

        try:
            while True:
                result = self.ec2_client.describe_hosts(**extra_args, Filters=machine_filter)
                hosts.extend(result['Hosts'])
                if 'NextToken' not in result:
                    break
                extra_args['NextToken'] = result['NextToken']
        except Exception as err:
            raise AWSDriverError(f"error getting instance details: {err}")

        for host in hosts:
            difference = datetime.now(timezone.utc) - host['AllocationTime']
            age = int(difference.total_seconds() / 3600)
            host_block = {'id': host['HostId'],
                          'state': host['State'],
                          'created': host['AllocationTime'],
                          'age': age,
                          'zone': host['AvailabilityZone'],
                          'capacity': host.get('AvailableCapacity', {}).get('AvailableVCpus', 0),
                          'instances': [i['InstanceId'] for i in host['Instances']],
                          'machine': host['HostProperties']['InstanceType']}
            host_list.append(host_block)

        return host_list

    def get_host_by_instance(self, instance_id: str):
        host_list = self.list_hosts()
        return next((h for h in host_list if instance_id in h['instances']), None)

    def get_host_by_id(self, host_id: str):
        host_list = self.list_hosts()
        return next((h for h in host_list if h['id'] == host_id), None)

    def release_host(self, host_id: str):
        try:
            result = self.ec2_client.release_hosts(HostIds=[host_id])
            if 'Unsuccessful' in result and len(result['Unsuccessful']) > 0:
                raise AWSDriverError(f"Can not release host {host_id}: {result['Unsuccessful'][0]['Error']['Message']}")
        except Exception as err:
            raise AWSDriverError(f"error getting instance details: {err}")

    def details(self, instance_id: str) -> Union[dict, None]:
        try:
            result = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            return result['Reservations'][0]['Instances'][0]
        except IndexError:
            return None
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'].endswith('NotFound'):
                return None
            raise AWSDriverError(f"ClientError: {err}")
        except Exception as err:
            raise AWSDriverError(f"error getting instance details: {err}")

    def terminate(self, instance_id: str) -> None:
        instance = self.details(instance_id)
        if not instance:
            return
        try:
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            waiter = self.ec2_client.get_waiter('instance_terminated')
            waiter.wait(InstanceIds=[instance_id])
        except Exception as err:
            raise AWSDriverError(f"error terminating instance: {err}")

    def image_details(self, ami_id: str) -> dict:
        ami_filter = {
            'Name': 'image-id',
            'Values': [
                ami_id,
            ]
        }
        try:
            result = self.ec2_client.describe_images(Filters=[ami_filter])
        except Exception as err:
            raise AWSDriverError(f"error getting AMI details: {err}")

        return result['Images'][0]

    def get_password(self, instance_id: str, ssh_key: str) -> str:
        try:
            logger.info(f"Waiting for instance {instance_id} password")
            while True:
                result = self.ec2_client.get_password_data(InstanceId=instance_id)
                encrypted_password = result.get('PasswordData')
                if not encrypted_password:
                    time.sleep(5)
                    continue
                password_data = base64.b64decode(encrypted_password)
                return SSHUtil().decrypt_with_key(password_data, ssh_key)
        except Exception as err:
            raise AWSDriverError(f"error getting instance password: {err}")
