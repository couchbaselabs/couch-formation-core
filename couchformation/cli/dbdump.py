##
##

import logging
import warnings
import json
from overrides import override
from couchformation.cli.cli import CLI
from couchformation.kvdb import KeyValueStore

warnings.filterwarnings("ignore")
logger = logging.getLogger()


class DBDumpCLI(CLI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @override()
    def local_args(self):
        self.parser.add_argument('-j', '--json', action='store_true', help="Output JSON")
        self.parser.add_argument('-R', '--regexp', action='store', help="Regexp filter", default=".*")
        self.parser.add_argument('-K', '--keyexp', action='store', help="Key regexp filter")

    def run(self):
        for file in self.remainder:
            db = KeyValueStore(file)
            for doc in db.doc_id_match(self.options.regexp):
                document = KeyValueStore(db.file_name, doc)
                if len(document) == 0:
                    continue
                if self.options.json:
                    print(json.dumps(document.as_dict, indent=2))
                elif self.options.keyexp:
                    for value in document.key_match(self.options.keyexp):
                        print(value)
                else:
                    print(f"Document: {doc}")
                    for key, value in document.items():
                        if not key:
                            key = ""
                        print(f"{key:<12} = {value}")


def main(args=None):
    cli = DBDumpCLI(args)
    cli.run()
