from aizec.common import *

from aizec.aize_ir import *


T = TypeVar('T')


class Backend(ABC):
    def __init__(self, ir: IR):
        self.ir = ir
        self.output_path: Optional[Path] = None

    def set_output(self, path: Optional[Path]):
        self.output_path = path

    @classmethod
    def create(cls: Type[T], ir: IR) -> T:
        return cls(ir)

    @abstractmethod
    def run(self):
        pass
