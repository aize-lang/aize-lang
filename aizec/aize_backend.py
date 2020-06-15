from __future__ import annotations

import os
import subprocess

from aizec.common import *

from aizec.aize_ir import *


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
        pass

    @classmethod
    def create(cls: Type[T], ir: IR) -> T:
        return cls(ir)

    @abstractmethod
    def run_backend(self):
        pass

    @abstractmethod
    def run_output(self):
        pass


class Linker(ABC):
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
    def get_linker(cls, name: str) -> Type[Linker]:
        available = LinkerRegistry.get_available_linkers()
        if len(available) > 0:
            return available[0]
        else:
            raise Exception("No available linkers")

    @classmethod
    def process_call(cls, args: List[Union[str, Path]], suppress_output=False) -> int:
        return SystemInfo.create_native().process_call(args, suppress_output)

    def link_files(self):
        self._link_files(SystemInfo.create_native())

    @abstractmethod
    def _link_files(self, info: SystemInfo):
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

    def process_call(self, args: List[Union[str, Path]], suppress_output=False):
        kwargs = {}
        if suppress_output:
            kwargs['stdout'] = subprocess.PIPE
            kwargs['stderr'] = subprocess.PIPE
        return_code = subprocess.call(args, **kwargs)
        return return_code


class LinkerRegistry:
    def __init__(self):
        self.linkers: Dict[str, Type[Linker]] = {}

    @classmethod
    def get_available_linkers(cls) -> List[Type[Linker]]:
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
    def register(cls, linker: Type[Linker]) -> Type[Linker]:
        cls.instance().linkers[linker.get_name()] = linker
        return linker


@LinkerRegistry.register
class GCCLinker(Linker):
    @classmethod
    def get_name(cls) -> str:
        return "GCC Linker"

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
        info.process_call(invocation)


@LinkerRegistry.register
class BuiltinWindowsLinker(Linker):
    WINDOWS_LINK = SystemInfo.create_native().aizec_dir / "windows-link"

    @classmethod
    def get_name(cls) -> str:
        return "Windows Bundled Linker"

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
        info.process_call(invocation)
