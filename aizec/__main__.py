import argparse

from aizec.common import *

from aizec.aize_run import FrontendManager, IRManager, BackendManager, fail_callback
from aizec.analysis import DefaultPasses


def make_arg_parser():
    parser = argparse.ArgumentParser(prog="aizec")

    parser.add_argument("file")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-O", choices=[0, 1], type=int, default=1, dest="opt_level")
    parser.add_argument("--backend-opt", action='append')

    return parser


def main():
    arg_parser = make_arg_parser()
    args = arg_parser.parse_args()

    input_file = Path(args.file)
    if args.output is None:
        output_file = None
    else:
        output_file = Path(args.output)
    opt_level: int = args.opt_level
    backend_options: List[str] = args.backend_opt

    with fail_callback(lambda c: exit(0)):
        frontend = FrontendManager(Path.cwd(), Path(__file__))
        frontend.add_file(input_file)
        frontend.trace_imports()

        ir_manager = IRManager(frontend.get_ir())
        ir_manager.schedule_pass(DefaultPasses)
        ir_manager.run_scheduled()

        backend = BackendManager.create_llvm(ir_manager.ir)
        backend.set_output(output_file)
        backend.set_opt_level(opt_level)
        for opt in backend_options:
            backend.set_option(opt)
        backend.run_backend()
        backend.run_output()


if __name__ == '__main__':
    main()
