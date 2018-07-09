import argparse
import sys
from .version import __version__

class MyParser(argparse.ArgumentParser):
    def error(self, message):
        print('\n****************************************')
        sys.stderr.write('Error: %s \n' % message)
        print('\n****************************************')
        self.print_help()
        sys.exit(2)


def get_args():
    parser = MyParser(
        description='keepcli is a interactive command line tool for the unofficial Google Keep API')
    parser.add_argument("-v", "--version", action="store_true",
                        help="print version number and exit")
    args = parser.parse_args()

    if args.version:
        print('\nCurrent version: {}'.format(__version__))
        sys.exit()

    return args
