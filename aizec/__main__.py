from aizec.parse.parser import AizeParser
from aizec.aize_common import *
from aizec.common import *


def main():
    with fail_callback(lambda e: exit(0)):
        source = FileSource(Path("test.az"), open("test.az", "r"))

        info = AizeParser.parse(source)

    breakpoint()


if __name__ == '__main__':
    main()
