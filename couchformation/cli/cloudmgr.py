##
##

import logging
import warnings
from overrides import override
import couchformation
from couchformation.cli.cli import CLI
from couchformation.project import Project
import couchformation.constants as C

warnings.filterwarnings("ignore")
logger = logging.getLogger()


class CloudMgrCLI(CLI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override()
    def local_args(self):
        command_subparser = self.parser.add_subparsers(dest='command')
        command_subparser.add_parser('create', add_help=False)
        command_subparser.add_parser('add', add_help=False)
        command_subparser.add_parser('deploy', add_help=False)
        command_subparser.add_parser('destroy', add_help=False)
        command_subparser.add_parser('list', add_help=False)

    def run(self):
        logger.info(f"Couch Formation v{couchformation.__version__}")

        project = Project(self.remainder)

        if self.options.command == "create":
            project.create()
            project.save()
        elif self.options.command == "add":
            project.add()
            project.save()
        elif self.options.command == "deploy":
            project.deploy()
            project.provision()
        elif self.options.command == "destroy":
            project.destroy()
        elif self.options.command == "list":
            services = project.list()
            for name, node_list in services.items():
                print(f"Service: {name}")
                print("Private IPs")
                for ip in node_list.list_private_ip():
                    print(f" - {ip}")
                print("Public IPs")
                for ip in node_list.list_public_ip():
                    print(f" - {ip}")


def main(args=None):
    cli = CloudMgrCLI(args)
    cli.run()
