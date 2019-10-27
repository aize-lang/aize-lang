import sys
import argparse

from .common import *
from .frontends.aize import parser, sematics
from .backends.c import gen


def hook_aize_error(exc_type: Cls[T], exc_val: T, exc_tb):
    if isinstance(exc_val, AizeError):
        exc_val.display(sys.stderr)
    else:
        sys.__excepthook__(exc_type, exc_val, exc_tb)


sys.excepthook = hook_aize_error


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("file")
arg_parser.add_argument("-o", dest="out", default=None)
arg_parser.add_argument("--keep-c", action='store_false', dest='delete_c')
arg_parser.add_argument("--run", action='store_true')
arg_parser.add_argument("--debug", action='store_true')


if __name__ == '__main__':
    args = arg_parser.parse_args()
    file = Path(args.file).absolute()
    if args.out is None:
        # TODO support other OS's
        args.out = file.with_suffix(".exe")
    tree = parser.Parser.parse(file)
    sematics.SemanticAnalysis(tree).visit(tree)
    gen.CGenerator.compile(tree, args)
