from aizec import run_file, Path
from aizec.common.error import AizeError

i = 0
while True:
    path = Path(f"test_{i}.aize")
    if path.exists():
        try:
            run_file(path, catch_errors=False)
        except Exception:
            AizeError.message(f"Your Compiler failed on test_{i}.aize. To see what that means, see test.txt.")
            raise
    else:
        break

