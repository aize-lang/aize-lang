import argparse

from aizec.common import *
from aizec.aize_run import AizeCompiler
from aizec.aize_error import MessageHandler


def make_arg_parser():
    parser = argparse.ArgumentParser(prog="aizec")

    parser.add_argument("file")
    parser.add_argument("-o", "--output", default=None)

    return parser


# class ArgumentError(AizeMessage):
#     def __init__(self):
#         super().__init__(self.FATAL)
#
#     def display(self) -> str:
#         return ""


def main():
    MessageHandler.set_io('stderr')
    compiler = AizeCompiler(Path(""), Path.cwd())

    arg_parser = make_arg_parser()
    args = arg_parser.parse_args()

    compiler.add_file(args.file, True)
    compiler.trace_imports()
    compiler.analyze()


if __name__ == '__main__':
    main()
