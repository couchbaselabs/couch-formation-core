##
##

import re
import logging
import warnings
import argparse
import json
from overrides import override
import couchformation
from couchformation.cli.cli import CLI
from couchformation.project import Project
from couchformation.resources.config_manager import ConfigurationManager
from couchformation.support.debug import CreateDebugPackage
from couchformation.ssh import SSHUtil

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
        opt_parser.add_argument('-t', '--to', action='store', help="Copy target")
        opt_parser.add_argument('-E', '--extended', action='store_true', help="Extended output")
        opt_parser.add_argument('--json', action='store_true', help="List output in JSON")

        command_subparser = self.parser.add_subparsers(dest='command')
        command_subparser.add_parser('create', help="Create New Service", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('add', help="Add Resource Group", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('copy', help="Copy Project", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('deploy', help="Deploy Project", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('destroy', help="Destroy Services", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('remove', help="Remove Services", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('clean', help="Clean Project", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('list', help="List Projects", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('show', help="Project Information", parents=[opt_parser], add_help=False, aliases=['info'])
        command_subparser.add_parser('parameters', help="Show Project Parameters", parents=[opt_parser], add_help=False, aliases=['param', 'parm'])
        command_subparser.add_parser('dump', help="Create Debug Bundle", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('cli', help="Get Project Create CLI", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('update', help="Edit Service Settings", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('peer', help="Network Peering", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('login', help="Cloud Login", parents=[opt_parser], add_help=False)
        command_subparser.add_parser('help', help="Show Supported Options", parents=[opt_parser], add_help=False)

        config_cmd = command_subparser.add_parser('config', help="Configuration Manager", add_help=False)
        config_parser = config_cmd.add_subparsers(dest='config_command')
        config_parser.add_parser('get', help="Get Config Elements", add_help=False)
        config_parser.add_parser('set', help="Get Config Elements", add_help=False)
        config_parser.add_parser('unset', help="Get Config Elements", add_help=False)

        ssh_opt_parser = argparse.ArgumentParser(add_help=False)
        ssh_opt_parser.add_argument('-n', '--name', action='store', help="Key Name", default="cf-key-pair")
        ssh_opt_parser.add_argument('-r', '--replace', action='store_true', help="Replace existing key")

        ssh_cmd = command_subparser.add_parser('ssh', help="SSH Key Manager", add_help=False)
        ssh_parser = ssh_cmd.add_subparsers(dest='ssh_command')
        ssh_parser.add_parser('create', help="Create SSH Key Pair", parents=[ssh_opt_parser], add_help=False)

    @staticmethod
    def check_name(value) -> bool:
        if not bool(re.match(r"^[a-z]([-a-z0-9]*[a-z0-9])?$", value)) or len(value) > 63:
            return False
        return True

    def run(self):
        if not hasattr(self.options, 'json'):
            logger.info(f"Couch Formation v{couchformation.__version__}")

        if self.options.show_version:
            return

        if self.options.command == "config":
            self.config_mgr(self.options.config_command)
            return

        if self.options.command == "ssh":
            self.ssh_mgr(self.options)
            return

        if self.options.command == "dump":
            CreateDebugPackage().create_snapshot()
            return

        if self.options.command == "list" and not self.options.project:
            Project(self.options, self.remainder).list_projects()
            return

        if self.options.command == "login" and self.options.cloud:
            Project(self.options, self.remainder).login(self.options.cloud)
            return

        if self.options.command == "help":
            logger.info("General parameters:\n")
            self.parser.print_help()
            print("")
            Project(self.options, self.remainder).show_help()
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
            if not self.check_name(self.options.name):
                logger.error(f"Invalid service name (name should conform to RFC1035): {self.options.name}")
                return
            if not self.check_name(self.options.project):
                logger.error(f"Invalid project name (name should conform to RFC1035): {self.options.project}")
                return
            project.create()
        elif self.options.command == "add":
            if self.options.name is None:
                logger.error("Missing required parameter: name")
                return
            if not self.check_name(self.options.name):
                logger.error(f"Invalid service name (name should conform to RFC1035): {self.options.name}")
                return
            if not self.check_name(self.options.project):
                logger.error(f"Invalid project name (name should conform to RFC1035): {self.options.project}")
                return
            project.add()
        elif self.options.command == "copy":
            if self.options.to is None:
                logger.error("Missing required parameter: to")
            project.copy()
        elif self.options.command == "deploy":
            project.deploy(self.options.name, self.options.raw)
        elif self.options.command == "destroy":
            project.destroy(self.options.name)
        elif self.options.command == "remove":
            project.remove()
        elif self.options.command == "clean":
            project.clean()
        elif self.options.command == "show" or self.options.command == "list" or self.options.command == "info":
            results = project.list(api=self.options.json)
            if self.options.json:
                print(json.dumps(results, indent=2))
        elif self.options.command == "param" or self.options.command == "parameters" or self.options.command == "parm":
            project.project_show()
        elif self.options.command == "cli":
            project.project_cli()
        elif self.options.command == "update":
            if self.options.name is None:
                logger.error("Missing required parameter: name")
                return
            project.service_edit()
        elif self.options.command == "peer":
            project.accept_peering(self.options.name)
        elif self.options.command == "login":
            project.login()

        loggers = [logging.getLogger()] + list(logging.Logger.manager.loggerDict.values())
        for log in loggers:
            handlers = getattr(log, 'handlers', [])
            for handler in handlers:
                handler.flush()

    def config_mgr(self, command: str):
        cm = ConfigurationManager()
        if command == "get":
            if len(self.remainder) == 0:
                contents = cm.list()
                for key in contents:
                    print(f"{key} = {contents[key]}")
                return
            elif len(self.remainder) == 1:
                value = cm.get(self.remainder[0])
                if value is not None:
                    print(f"{self.remainder[0]} = {value}")
            else:
                logger.error(f"Usage: get [key_name]")
        elif command == "set":
            if len(self.remainder) == 2:
                cm.set(self.remainder[0], self.remainder[1])
            else:
                logger.error(f"Usage: set key_name value")
        elif command == "unset":
            if len(self.remainder) == 1:
                cm.delete(self.remainder[0])
            else:
                logger.error(f"Usage: unset key_name")
        else:
            logger.error(f"Unknown config command: {command}")

    @staticmethod
    def ssh_mgr(options: argparse.Namespace):
        cm = ConfigurationManager()
        if options.ssh_command == "create":
            _, private_file = SSHUtil.create_key_pair(options.name, options.replace)
            cm.set('ssh.key', private_file)
        else:
            logger.error(f"Unknown ssh command")


def main(args=None):
    cli = CloudMgrCLI(args)
    cli.run()
