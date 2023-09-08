##
##

import logging
import warnings
import argparse
from overrides import override
import pyformationlib
from pyformationlib.cli.cli import CLI
from pyformationlib.project import Project
import pyformationlib.constants as C

warnings.filterwarnings("ignore")
logger = logging.getLogger()


class CloudMgrCLI(CLI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override()
    def local_args(self):
        opt_parser = argparse.ArgumentParser(parents=[self.parser], add_help=False)
        opt_parser.add_argument('-t', '--type', dest='mode', action='store', default='cbs')

        command_subparser = self.parser.add_subparsers(dest='command')
        command_subparser.add_parser('create', parents=[opt_parser], add_help=False)
        command_subparser.add_parser('add', parents=[opt_parser], add_help=False)
        command_subparser.add_parser('deploy', parents=[opt_parser], add_help=False)
        command_subparser.add_parser('destroy', parents=[opt_parser], add_help=False)
        command_subparser.add_parser('list', parents=[opt_parser], add_help=False)

    def run(self):
        logger.info(f"Couch Formation v{pyformationlib.__version__}")

        project = Project(self.remainder)

        if self.options.command == "create":
            project.create()
            project.save()
        elif self.options.command == "add":
            project.add()
            project.save()
        elif self.options.command == "deploy":
            project.deploy()
            if self.options.mode == "cbs":
                project.provision(C.CBS_PRE_PROVISION, C.CBS_PROVISION, C.CBS_POST_PROVISION)
        elif self.options.command == "destroy":
            project.destroy()
        elif self.options.command == "list":
            nodes = project.list()
            for ip in nodes.provision_list():
                print(ip)
            print(nodes.ip_csv_list())


def main(args=None):
    cli = CloudMgrCLI(args)
    cli.run()
