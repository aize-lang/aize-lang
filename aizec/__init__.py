import aizec.common.error as error
from aizec.common import *

from aizec.frontends import apply_frontend
from aizec.backends import get_backend

import sys


def run_file(path: Path, catch_errors: bool = True):
    if catch_errors:
        error.init_errors(sys.stderr)
    else:
        error.init_errors(sys.stderr, debug=True)

    out_file = path.with_suffix(".exe")

    with Config(Path(__file__).parent / "aizec_cfg.json") as config:
        ast = apply_frontend("aize", path)

        backend = get_backend("c")
        result = backend.generate(ast, out_file, config, "normal")

        result.delete_temp()

        result.run()
