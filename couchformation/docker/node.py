##
##

import logging
from couchformation.docker.driver.container import Container
from couchformation.config import get_state_file, get_state_dir, PortSettingSet, PortSettings, State
from couchformation.docker.network import DockerNetwork
from couchformation.exception import FatalError
from couchformation.kvdb import KeyValueStore
from couchformation.util import FileManager, Synchronize
from couchformation.network import NetworkUtil

logger = logging.getLogger('couchformation.docker.node')
logger.addHandler(logging.NullHandler())
logging.getLogger("docker").setLevel(logging.WARNING)


class DockerNodeError(FatalError):
    pass


class DockerDeployment(object):

    def __init__(self, parameters: dict):
        self.parameters = parameters
        self.name = parameters.get('name')
        self.project = parameters.get('project')
        self.build = parameters.get('build')
        self.image = self.build if Container(self.parameters).map(self.build) else parameters.get('image')
        self.number = parameters.get('number')
        self.services = parameters.get('services') if parameters.get('services') else "default"
        self.node_name = f"{self.name}-node-{self.number:02d}"

        filename = get_state_file(self.project, self.name)

        with Synchronize():
            try:
                state_dir = get_state_dir(self.project, self.name)
                FileManager().make_dir(state_dir)
            except Exception as err:
                raise DockerNodeError(f"can not create state dir: {err}")

        document = self.node_name
        self.state = KeyValueStore(filename, document)

        self.docker_network = DockerNetwork(self.parameters)

    def check_state(self):
        if self.state.get('instance_id'):
            result = Container(self.parameters).get_container(self.state.get('instance_id'))
            if result is None:
                logger.warning(f"Removing stale state entry for container {self.state.get('instance_id')}")
                del self.state['instance_id']
        else:
            container_id = Container(self.parameters).get_container_id(self.node_name)
            if container_id:
                logger.warning(f"Importing orphaned container {self.node_name}")
                self.state['instance_id'] = container_id

    def deploy(self):
        self.check_state()
        if self.state.get('instance_id'):
            logger.info(f"Node {self.node_name} already exists")
            return self.state.as_dict

        self.state['state'] = State.DEPLOYING.value

        net_name = self.docker_network.network
        services = self.services

        build_ports = PortSettingSet().create().get(self.build)
        if build_ports:
            port_cfg = PortSettings().create(self.name, build_ports.tcp_ports)
            ports = ','.join(list(port_cfg.tcp_as_ranges()))
        else:
            ports = None

        logger.info(f"Creating container {self.node_name}")
        container = Container(self.parameters).run(self.image, self.node_name, network=net_name, ports=ports)

        public_ip = NetworkUtil().local_ip_address()
        private_ip = Container(self.parameters).get_container_ip(self.node_name)
        self.state['service'] = self.name
        self.state['instance_id'] = container.id
        self.state['name'] = self.node_name
        self.state['services'] = services
        self.state['public_ip'] = public_ip if public_ip else private_ip
        self.state['private_ip'] = private_ip
        self.docker_network.add_service(self.node_name)

        logger.info(f"Created container {self.node_name}")
        self.state['state'] = State.DEPLOYED.value
        return self.state.as_dict

    def destroy(self):
        self.state['state'] = State.DESTROYING.value
        if self.state.get('instance_id'):
            Container(self.parameters).terminate(self.node_name)
            self.state.clear()
            self.docker_network.remove_service(self.node_name)
            logger.info(f"Removed container {self.node_name}")
        self.state['state'] = State.IDLE.value

    def info(self):
        return self.state.as_dict
