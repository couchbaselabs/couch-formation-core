##
##

import logging
import warnings
import json
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
        self.parser.add_argument('-j', '--json', action='store_true', help="Output JSON")

    def run(self):
        for file in self.remainder:
            for doc in kvdb.documents(file):
                if self.options.json:
                    print(json.dumps(doc.as_dict, indent=2))
                else:
                    print(f"Document: {doc.document_id}")
                    for key, value in doc.items():
                        print(f"{key:<12} = {value}")


def main(args=None):
    cli = DBDumpCLI(args)
    cli.run()
