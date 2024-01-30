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
        self.parser.add_argument('-V', action='store_true', dest='show_version', help="Display version information")

        opt_parser = argparse.ArgumentParser(parents=[self.parser], add_help=False)
        opt_parser.add_argument('-b', '--build', action='store', help="Build Type", default="cbs")
        opt_parser.add_argument('-c', '--cloud', action='store', help="Infrastructure", default="aws")
        opt_parser.add_argument('-p', '--project', action='store', help="Project Name")
        opt_parser.add_argument('-n', '--name', action='store', help="Service Name")
        opt_parser.add_argument('-x', '--connect', action='store', help="Connection Name", default=None)
        opt_parser.add_argument('-g', '--group', action='store', help="Group Number", default=1, type=int)
        opt_parser.add_argument('-P', '--provisioner', action='store', help="Provisioner Name", default="remote")
        opt_parser.add_argument('-R', '--raw', action='store_true', help="Skip provision phase")

        command_subparser = self.parser.add_subparsers(dest='command')
        command_subparser.add_parser('create', help="Create New Service", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('add', help="Add Resource Group", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('deploy', help="Deploy Project", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('destroy', help="Destroy Services", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('remove', help="Remove Services", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('clean', help="Clean Project", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('list', help="Display Information", parents=[opt_parser], add_help=False)

    def run(self):
        logger.info(f"Couch Formation v{couchformation.__version__}")

        if self.options.show_version:
            return

        if self.options.command == "list" and not self.options.project:
            Project(self.options, self.remainder).list_projects()
            return

        if not self.options.command or not self.options.project:
            logger.error("Missing required arguments")
            self.parser.print_help()
            return

        project = Project(self.options, self.remainder)

        if self.options.command == "create":
            if self.options.name is None:
                logger.error("Missing required parameter: name")
                return
            project.create()
        elif self.options.command == "add":
            if self.options.name is None:
                logger.error("Missing required parameter: name")
                return
            project.add()
        elif self.options.command == "deploy":
            project.deploy(self.options.name, self.options.raw)
        elif self.options.command == "destroy":
            project.destroy(self.options.name)
        elif self.options.command == "remove":
            project.remove()
        elif self.options.command == "clean":
            project.clean()
        elif self.options.command == "list":
            project.list()

        loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
        for log in loggers:
            handlers = getattr(log, 'handlers', [])
            for handler in handlers:
                handler.flush()


def main(args=None):
    cli = CloudMgrCLI(args)
    cli.run()
