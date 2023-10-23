##
##

import logging
import warnings
import argparse
from overrides import override
import couchformation
from couchformation.cli.cli import CLI
from couchformation.project import Project

warnings.filterwarnings("ignore")
logger = logging.getLogger()


class CloudMgrCLI(CLI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override()
    def local_args(self):
        opt_parser = argparse.ArgumentParser(parents=[self.parser], add_help=False)
        opt_parser.add_argument('-b', '--build', action='store', help="Build Type", default="cbs")
        opt_parser.add_argument('-c', '--cloud', action='store', help="Infrastructure", default="aws")
        opt_parser.add_argument('-p', '--project', action='store', help="Project Name", default="resources")
        opt_parser.add_argument('-n', '--name', action='store', help="Deployment Name", default="nodes")
        opt_parser.add_argument('-x', '--connect', action='store', help="Connection Name", default=None)
        opt_parser.add_argument('-g', '--group', action='store', help="Group Number", default=1, type=int)

        command_subparser = self.parser.add_subparsers(dest='command')
        command_subparser.add_parser('create', help="Create", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('add', help="Add Resource Group", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('deploy', help="Deploy", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('destroy', help="Remove Resources", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('list', help="Display Information", parents=[opt_parser], add_help=False)

    def run(self):
        logger.info(f"Couch Formation v{couchformation.__version__}")

        project = Project(self.options, self.remainder)

        if self.options.command == "create":
            project.create()
            # project.save()
        elif self.options.command == "add":
            project.add()
            # project.save()
        elif self.options.command == "deploy":
            project.deploy()
            # project.provision()
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
