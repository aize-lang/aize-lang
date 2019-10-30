import sys
import argparse

from aizec.common.error import AizeError
from aizec.common import *
from aizec.frontends import apply_frontend
from aizec.backends import apply_backend


def hook_aize_error(exc_type: Cls[T], exc_val: T, exc_tb):
    if isinstance(exc_val, AizeError):
        exc_val.display(sys.stderr)
    else:
        sys.__excepthook__(exc_type, exc_val, exc_tb)


sys.excepthook = hook_aize_error


arg_parser = argparse.ArgumentParser(prog="aizec")
arg_parser.add_argument("file")
arg_parser.add_argument("-o", dest="out", default=None)
arg_parser.add_argument("-f", action='store', dest='frontend', default='aize')
arg_parser.add_argument("-b", action='store', dest='backend', default='c')
arg_parser.add_argument("-c", action='store', dest='compiler', default=None)
# arg_parser.add_argument("-O", action='store', dest='opt', choices=[0, 1, 2, 3], default=0)
arg_parser.add_argument("--keep-c", action='store_false', dest='delete_c')
arg_parser.add_argument("--run", action='store_true')
arg_parser.add_argument("--for", action='store', choices=['debug', 'normal', 'release'], dest='for_', default='normal')
arg_parser.add_argument("--config", action='store', default=None)


if __name__ == '__main__':
    args = arg_parser.parse_args()
    file = Path(args.file).absolute()
    if args.out is None:
        # TODO support other OS's
        args.out = file.with_suffix(".exe")
    if args.config is None:
        args.config = Path(__file__).parent / "aizec_cfg.json"
    with Config(args.config) as args.config:
        ast = apply_frontend(args.frontend, file, args)

        apply_backend(args.backend, ast, args)
