import argparse

from aizec.common import *
from aizec.aize_run import FrontendManager, IRManager, BackendManager, fail_callback


def make_arg_parser():
    parser = argparse.ArgumentParser(prog="aizec")

    parser.add_argument("file")
    parser.add_argument("-o", "--output", default=None)

    return parser


# class InputError(AizeMessage):
#     def __init__(self, msg: str, pos: Position = None):
#         super().__init__(ErrorLevel.FATAL)
#
#         self.msg = msg
#         self.pos = pos
#
#     def display(self, reporter: Reporter):
#         if self.pos is None:
#             reporter.general_error("Input Error", self.msg)
#         else:
#             reporter.positioned_error("Input Error", self.msg, self.pos)


def main():
    arg_parser = make_arg_parser()
    args = arg_parser.parse_args()

    with fail_callback(lambda: exit(0)):
        frontend = FrontendManager(Path.cwd(), Path(__file__))
        frontend.add_file(Path(args.file))
        frontend.trace_imports()

        ir_manager = IRManager(frontend.get_program_ir())
        ir_manager.schedule_pass('DefaultPasses')
        ir_manager.run_scheduled()


if __name__ == '__main__':
    main()
