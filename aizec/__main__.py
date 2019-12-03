import os
import sys
import argparse
import time

from aizec.common.error import AizeError
from aizec.common import *
from aizec.common import error
from aizec.frontends import apply_frontend
from aizec.backends import apply_backend


arg_parser = argparse.ArgumentParser(prog="aizec")
arg_parser.add_argument("file")
arg_parser.add_argument("-o", dest="out", default=None)
arg_parser.add_argument("-f", action='store', dest='frontend', default='aize')
arg_parser.add_argument("-b", action='store', dest='backend', default='c')
arg_parser.add_argument("-c", action='store', dest='compiler', default=None)

arg_parser.add_argument("-S", action='store_false', dest='compile')

# arg_parser.add_argument("-O", action='store', dest='opt', choices=[0, 1, 2, 3], default=0)
arg_parser.add_argument("--keep-temp", action='store_false', dest='delete_temp')
arg_parser.add_argument("--run", action='store_true')
arg_parser.add_argument("--time", action='store_true')
arg_parser.add_argument("--for", action='store', choices=['compiler-debug', 'debug', 'normal', 'release'], dest='for_', default='normal')
arg_parser.add_argument("--config", action='store', default=None)


def run(*passed_args):
    if passed_args:
        args = arg_parser.parse_args(passed_args)
    else:
        args = arg_parser.parse_args()

    error.init_errors(sys.stderr, args.for_ == 'compiler-debug')

    file = Path(args.file).absolute()
    if args.out is None:
        # TODO support other OS's
        if os.name == 'nt':
            args.out = file.with_suffix(".exe")
        else:
            args.out = file.with_suffix("")
    if args.config is None:
        args.config = Path(__file__).parent / "aizec_cfg.json"
    if not args.compile:
        args.backend = 'no'

    start_time = time.time()
    start_own_time = time.process_time()

    with Config(args.config) as args.config:
        ast = apply_frontend(args.frontend, file, args)

        apply_backend(args.backend, ast, args)

    if args.time:
        end_time = time.time()
        end_own_time = time.process_time()
        elasped = end_time - start_time
        elasped_own = end_own_time - start_own_time
        AizeError.message(f"Time Elapsed: {elasped:.2f} sec (Own {elasped_own:.2f})")


if __name__ == '__main__':
    run()
