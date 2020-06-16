from __future__ import annotations

import os
import subprocess

from aizec.common import *
from aizec.aize_error import AizeMessage, MessageHandler, Reporter, ErrorLevel

from aizec.aize_ir import *


class LinkingError(AizeMessage):
    def __init__(self, msg: str):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg

    def display(self, reporter: Reporter):
        reporter.general_error("Linking Error", self.msg)


class LinkingWarning(AizeMessage):
    def __init__(self, msg: str):
        super().__init__(ErrorLevel.WARNING)
        self.msg = msg

    def display(self, reporter: Reporter):
        reporter.general_error("Linking Warning", self.msg)


T = TypeVar('T')


# TODO Reuse `Source`s somehow so it can be used for both input and output
class Backend(ABC):
    def __init__(self, ir: IR):
        self.ir = ir
        self.output_path: Optional[Path] = None
        self.opt_level: Literal[0, 1] = 1

    def set_output(self, path: Optional[Path]):
        self.output_path = path

    def set_opt_level(self, level: int):
        assert level in (0, 1)
        self.opt_level = level

    @abstractmethod
    def handle_option(self, option: str) -> bool:
        return False

    @classmethod
    def create(cls: Type[T], ir: IR) -> T:
        return cls(ir)

    @abstractmethod
    def run_backend(self):
        pass

    @abstractmethod
    def run_output(self):
        pass


class CBackend(Backend, ABC):
    def __init__(self, ir: IR):
        super().__init__(ir)
        self.linker_cls: Type[CLinker] = CLinker.get_linker()

    @abstractmethod
    def handle_option(self, option: str) -> bool:
        if option.startswith('linker='):
            linker_name = option[7:]
            try:
                self.linker_cls = CLinker.get_linker(linker_name)
            except KeyError:
                msg = LinkingWarning(f"No linker found called '{linker_name}', not setting it as the linker")
                MessageHandler.handle_message(msg)
            return True
        else:
            return False


class CLinker(ABC):
    def __init__(self, to_link: List[Path], out_path: Path):
        self.to_link = to_link
        self.out_path = out_path

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def is_available(cls, info: SystemInfo) -> bool:
        pass

    @classmethod
    @abstractmethod
    def is_preferred(cls) -> bool:
        pass

    @classmethod
    def get_linker(cls, name: str = None) -> Type[CLinker]:
        available = CLinkerRegistry.get_available_linkers()
        if name is not None:
            available = [linker_cls for linker_cls in available if linker_cls.get_name() == name]
        if len(available) > 0:
            return available[0]
        else:
            raise KeyError("No available linkers")

    @classmethod
    def process_call(cls, args: List[Union[str, Path]], suppress_output=False) -> subprocess.CompletedProcess:
        return SystemInfo.create_native().process_call(args, suppress_output)

    def link_files(self):
        success = self._link_files(SystemInfo.create_native())
        if not success:
            msg = LinkingError("Error during linking")
            MessageHandler.handle_message(msg)

    @abstractmethod
    def _link_files(self, info: SystemInfo) -> bool:
        pass


class SystemInfo:
    def __init__(self, os_name: str):
        self._os_name = os_name

    @classmethod
    def create_native(cls) -> SystemInfo:
        if os.name == 'nt':
            os_name = 'windows'
        else:
            os_name = '<unknown>'
        return cls(os_name)

    @property
    def aizec_dir(self):
        return Path(__file__).parent

    def is_windows(self):
        return self._os_name == 'windows'

    def all_exist(self, *paths: Union[str, Path]) -> str:
        all_pass = True
        any_pass = False
        for p in paths:
            if p.exists():
                any_pass = True
            else:
                all_pass = False
        if all_pass:
            return 'all'
        elif any_pass:
            return 'some'
        else:
            return 'none'

    def all_sub_exist(self, *paths: Union[str, Path], in_dir: Path) -> str:
        return self.all_exist(*(in_dir / p for p in paths))

    def process_exists(self, name: str):
        try:
            subprocess.call([name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            return False
        else:
            return True

    def process_call(self, args: List[Union[str, Path]], suppress_output=False) -> subprocess.CompletedProcess:
        kwargs = {}
        if suppress_output:
            kwargs['stdout'] = subprocess.PIPE
            kwargs['stderr'] = subprocess.PIPE
        result = subprocess.run(args, **kwargs)
        return result


class CLinkerRegistry:
    def __init__(self):
        self.linkers: Dict[str, Type[CLinker]] = {}

    @classmethod
    def get_available_linkers(cls) -> List[Type[CLinker]]:
        available = []
        sys_info = SystemInfo.create_native()
        for linker in cls.instance().linkers.values():
            if linker.is_available(sys_info):
                available.append(linker)
        available.sort(key=lambda l: l.is_preferred(), reverse=True)
        return available

    @classmethod
    def instance(cls):
        try:
            return cls._instance_
        except AttributeError:
            cls._instance_ = cls()
            return cls._instance_

    @classmethod
    def register(cls, linker: Type[CLinker]) -> Type[CLinker]:
        cls.instance().linkers[linker.get_name()] = linker
        return linker


@CLinkerRegistry.register
class GCCCLinker(CLinker):
    @classmethod
    def get_name(cls) -> str:
        return "gcc"

    @classmethod
    def is_available(cls, info: SystemInfo) -> bool:
        return info.process_exists("gcc")

    @classmethod
    def is_preferred(cls) -> bool:
        return True

    def _link_files(self, info: SystemInfo):
        invocation = ["gcc"]
        invocation += self.to_link
        invocation += [f"-o{self.out_path}"]
        result = info.process_call(invocation)
        return result.returncode == 0


@CLinkerRegistry.register
class BuiltinWindowsCLinker(CLinker):
    WINDOWS_LINK = SystemInfo.create_native().aizec_dir / "windows-link"

    @classmethod
    def get_name(cls) -> str:
        return "windows-bundled"

    @classmethod
    def is_available(cls, info: SystemInfo) -> bool:
        if info.is_windows():
            check = info.all_sub_exist("lld-link.exe", "x64", in_dir=cls.WINDOWS_LINK) == 'all' and \
                    info.all_sub_exist("kernel32.Lib", "libcmt.lib", "libucrt.lib", "libvcruntime.lib", "Uuid.Lib", in_dir=cls.WINDOWS_LINK / "x64")
            return check
        else:
            return False

    @classmethod
    def is_preferred(cls) -> bool:
        return False

    def _link_files(self, info: SystemInfo):
        lld_link = self.WINDOWS_LINK / "lld-link.exe"
        link_to = self.WINDOWS_LINK / "x64"

        invocation = [f"{lld_link}"]
        invocation += self.to_link
        invocation += [f"-out:{self.out_path}"]
        invocation += [f"-libpath:{link_to}", "-defaultlib:libcmt"]
        result = info.process_call(invocation)
        return result.returncode == 0
