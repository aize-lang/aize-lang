import argparse

from aizec.common import *
from aizec.aize_run import FrontendManager, IRManager, BackendManager, AizeFrontendError
from aizec.aize_error import MessageHandler


def make_arg_parser():
    parser = argparse.ArgumentParser(prog="aizec")

    parser.add_argument("file")
    parser.add_argument("-o", "--output", default=None)

    return parser


def main():
    MessageHandler.set_io('stderr')

    arg_parser = make_arg_parser()
    args = arg_parser.parse_args()

    frontend = FrontendManager(Path.cwd(), Path(__file__))

    frontend.trace_imports([frontend.make_file_source(Path(args.file))])

    ir_manager = IRManager(frontend.get_program_ast())


if __name__ == '__main__':
    main()
