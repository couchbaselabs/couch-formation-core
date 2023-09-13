##
##

import attr
from attr.validators import instance_of as io


@attr.s
class TerraformElement(object):
    terraform = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, element: dict):
        return cls(
            [
                element
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class RequiredProvider(object):
    required_providers = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, element: dict):
        return cls(
           [
                element
           ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AzureTerraformProvider(object):
    azurerm = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, source: str):
        return cls(
            {"source": source}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class ImageData(object):
    azurerm_image = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, image: str, resource_group: str):
        return cls(
            {"cb_image": [
                {
                    "name": image,
                    "resource_group_name": resource_group
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class ImageReference(object):
    publisher = attr.ib(validator=io(str))
    offer = attr.ib(validator=io(str))
    sku = attr.ib(validator=io(str))
    version = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, publisher: str, offer: str, sku: str):
        return cls(
            publisher,
            offer,
            sku,
            "latest"
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SourceImageReference(object):
    source_image_reference = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, publisher: str, offer: str, sku: str):
        return cls(
            [
                ImageReference.construct(publisher, offer, sku).as_dict
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['source_image_reference']


@attr.s
class NSGData(object):
    azurerm_network_security_group = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, name: str, resource_group: str):
        return cls(
            {"cluster_nsg": [
                {
                    "name": name,
                    "resource_group_name": resource_group
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class SubnetData(object):
    azurerm_subnet = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls, resource_group: str, vpc_name: str):
        return cls(
            {"cb_subnet": [
                {
                    "name": f"{vpc_name}-subnet-1",
                    "resource_group_name": resource_group,
                    "virtual_network_name": vpc_name
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AzureProviderBlock(object):
    provider = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls):
        return cls(
            {"azurerm": [
                {
                    "features": [
                        {}
                    ]
                }
            ]}
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AzureInstance(object):
    azurerm_linux_virtual_machine = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.azurerm_linux_virtual_machine.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AdminSSHKey(object):
    admin_ssh_key = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, ssh_key: str, user: str):
        return cls(
            [
                {
                    "public_key": ssh_key,
                    "username": user
                }
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['admin_ssh_key']


@attr.s
class NetworkInterface(object):
    network_interface_ids = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, name: str):
        return cls(
            [
                f"${{azurerm_network_interface.{name}.id}}"
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['network_interface_ids']


@attr.s
class OSDisk(object):
    os_disk = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, vol_size: str, vol_type: str):
        return cls(
            [
                {
                    "caching": "ReadWrite",
                    "disk_size_gb": vol_size,
                    "storage_account_type": vol_type
                }
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['os_disk']


@attr.s
class NodeConfiguration(object):
    admin_ssh_key = attr.ib(validator=io(list))
    admin_username = attr.ib(validator=io(str))
    location = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    network_interface_ids = attr.ib(validator=io(list))
    os_disk = attr.ib(validator=io(list))
    resource_group_name = attr.ib(validator=io(str))
    size = attr.ib(validator=io(str))
    zone = attr.ib(validator=io(str))
    source_image_reference = attr.ib(validator=io(list))
    tags = attr.ib(validator=io(dict))

    @classmethod
    def construct(cls,
                  name: str,
                  root_size: str,
                  root_type: str,
                  machine_type: str,
                  user: str,
                  ssh_key: str,
                  location: str,
                  resource_group: str,
                  nic_name: str,
                  zone: str,
                  services,
                  publisher: str,
                  offer: str,
                  sku: str):
        return cls(
            AdminSSHKey.construct(ssh_key, user).as_dict,
            user,
            location,
            name,
            NetworkInterface.construct(nic_name).as_dict,
            OSDisk.construct(root_size, root_type).as_dict,
            resource_group,
            machine_type,
            zone,
            SourceImageReference.construct(publisher, offer, sku).as_dict,
            {"name": name, "services": services}
        )

    @property
    def as_dict(self):
        block = {k: v for k, v in self.__dict__.items() if v is not None}
        return block


@attr.s
class AzureManagedDisk(object):
    azurerm_managed_disk = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.azurerm_managed_disk.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class DiskConfiguration(object):
    create_option = attr.ib(validator=io(str))
    disk_size_gb = attr.ib(validator=io(str))
    location = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    resource_group_name = attr.ib(validator=io(str))
    storage_account_type = attr.ib(validator=io(str))
    zone = attr.ib(validator=io(str))
    tier = attr.ib(validator=io(str))

    @classmethod
    def construct(cls,
                  name: str,
                  disk_size: str,
                  location: str,
                  resource_group: str,
                  disk_type: str,
                  zone: str,
                  tier: str):
        return cls(
            "Empty",
            disk_size,
            location,
            name,
            resource_group,
            disk_type,
            zone,
            tier
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AzureNetworkInterface(object):
    azurerm_network_interface = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.azurerm_network_interface.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class IPConfiguration(object):
    ip_configuration = attr.ib(validator=io(list))

    @classmethod
    def construct(cls, public_ip_name: str):
        return cls(
            [
                {
                    "name": "internal",
                    "private_ip_address_allocation": "Dynamic",
                    "public_ip_address_id": f"${{azurerm_public_ip.{public_ip_name}.id}}",
                    "subnet_id": "${data.azurerm_subnet.cb_subnet.id}"
                }
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__['ip_configuration']


@attr.s
class NICConfiguration(object):
    ip_configuration = attr.ib(validator=io(list))
    location = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    resource_group_name = attr.ib(validator=io(str))

    @classmethod
    def construct(cls,
                  name: str,
                  public_ip_name: str,
                  location: str,
                  resource_group: str):
        return cls(
            IPConfiguration.construct(public_ip_name).as_dict,
            location,
            name,
            resource_group
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AzureNetworkInterfaceNSG(object):
    azurerm_network_interface_security_group_association = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.azurerm_network_interface_security_group_association.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class NICNSGConfiguration(object):
    network_interface_id = attr.ib(validator=io(str))
    network_security_group_id = attr.ib(validator=io(str))

    @classmethod
    def construct(cls, nic_name: str):
        return cls(
            f"${{azurerm_network_interface.{nic_name}.id}}",
            "${data.azurerm_network_security_group.cluster_nsg.id}"
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AzurePublicIP(object):
    azurerm_public_ip = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.azurerm_public_ip.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class PublicIPConfiguration(object):
    allocation_method = attr.ib(validator=io(str))
    location = attr.ib(validator=io(str))
    name = attr.ib(validator=io(str))
    resource_group_name = attr.ib(validator=io(str))
    sku = attr.ib(validator=io(str))
    zones = attr.ib(validator=io(list))

    @classmethod
    def construct(cls,
                  name: str,
                  location: str,
                  resource_group: str,
                  zone: str):
        return cls(
            "Static",
            location,
            name,
            resource_group,
            "Standard",
            [
                zone
            ]
        )

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AzureDiskAttachment(object):
    azurerm_virtual_machine_data_disk_attachment = attr.ib(validator=io(dict))

    @classmethod
    def build(cls):
        return cls(
            {}
        )

    def add(self, resource: dict):
        self.azurerm_virtual_machine_data_disk_attachment.update(resource)
        return self

    @property
    def as_dict(self):
        return self.__dict__


@attr.s
class AttachedDiskConfiguration(object):
    caching = attr.ib(validator=io(str))
    lun = attr.ib(validator=io(str))
    managed_disk_id = attr.ib(validator=io(str))
    virtual_machine_id = attr.ib(validator=io(str))

    @classmethod
    def construct(cls,
                  caching: str,
                  lun: str,
                  disk_name: str,
                  node_name: str):
        return cls(
            caching,
            lun,
            f"${{azurerm_managed_disk.{disk_name}.id}}",
            f"${{azurerm_linux_virtual_machine.{node_name}.id}}",
        )

    @property
    def as_dict(self):
        return self.__dict__
