##
##

import logging
import warnings
import argparse
from overrides import override
from couchformation.cli.cli import CLI
import couchformation.kvdb as kvdb

warnings.filterwarnings("ignore")
logger = logging.getLogger()


class DBDumpCLI(CLI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override()
    def local_args(self):
        opt_parser = argparse.ArgumentParser(parents=[self.parser], add_help=False)
        opt_parser.add_argument('-t', '--table', action='store', help="Table Name")

    def run(self):
        for file in self.remainder:
            for doc in kvdb.documents(file):
                print(f"Document: {doc.document_id}")
                for key, value in doc.items():
                    print(f"{key:<12} = {value}")


def main(args=None):
    cli = DBDumpCLI(args)
    cli.run()
