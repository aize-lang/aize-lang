from __future__ import annotations

import io

from aizec.common import *

from aizec.aize_error import AizeMessage, MessageHandler, Reporter, ErrorLevel, FailFlag
from aizec.aize_source import Source, FileSource, Position, StreamSource

from aizec.aize_ast import ProgramAST, SourceAST
from aizec.aize_parser import AizeParser

from aizec.aize_ir import IR
from aizec.aize_ir_pass import PassScheduler, PassAlias
from aizec.aize_semantics import DefaultPasses

from aizec.aize_backend import Backend
from aizec.aize_llvm_backend import LLVMBackend


__all__ = ['FrontendManager', 'IRManager', 'BackendManager',
           'AizeFrontendError', 'AizeImportError', 'AizeFileError', 'fail_callback']


class AizeFrontendError(Exception):
    pass


class AizeImportError(AizeFrontendError):
    def __init__(self, msg: str, pos: Position):
        super().__init__(msg)
        self.msg = msg
        self.pos = pos


class AizeFileError(AizeFrontendError):
    def __init__(self, msg: str, pos: Position = None):
        super().__init__(msg)
        self.msg = msg
        self.pos: Optional[Position] = pos


@contextmanager
def fail_callback(callback: Callable[[List[AizeMessage]], None]):
    try:
        yield
    except FailFlag as fail:
        callback(fail.fail_msgs)


class FrontendManager:
    def __init__(self, project_dir: Path, std_dir: Path):
        self.project_dir = project_dir
        self.std_dir = std_dir

        self._sources: Dict[Source, SourceAST] = {}

    @staticmethod
    def _parse_source(source: Source) -> SourceAST:
        return AizeParser.parse(source)

    def _fatal_error(self, msg: AizeMessage):
        MessageHandler.handle_message(msg)
        MessageHandler.flush_messages()
        assert False

    @staticmethod
    def _make_file_source(path: Path, pos: Position = None) -> FileSource:
        try:
            path = path.resolve()
            file_stream = path.open("r")
        except FileNotFoundError:
            raise AizeFileError(f"Cannot open '{str(path)}'", pos) from None

        return FileSource(path, file_stream)

    @staticmethod
    def _make_text_source(text: str, pos: Position = None) -> StreamSource:
        text_stream = io.StringIO(text)

        return StreamSource("<string>", text_stream)

    def get_program_ast(self) -> ProgramAST:
        return ProgramAST([ast for ast in self._sources.values()])

    def get_ir(self) -> IR:
        return IR.from_ast(self.get_program_ast())

    def add_source(self, source: Source):
        if source in self._sources:
            raise ValueError(f"Source {source} already added")
        self._sources[source] = self._parse_source(source)

    def add_file(self, path: Path):
        self.add_source(self._make_file_source(path))

    def trace_imports(self):
        to_visit: List[Source] = [source for source in self._sources]
        visited: Set[Source] = set()

        sources: Dict[Source, SourceAST] = self._sources.copy()

        while to_visit:
            source = to_visit.pop()
            if source in visited:
                continue

            if source not in sources:
                source_ast = sources[source] = self._parse_source(source)
            else:
                source_ast = sources[source]

            visited.add(source)

            for import_node in source_ast.imports:
                if import_node.anchor == 'std':
                    abs_path = self.std_dir / import_node.path
                elif import_node.anchor == 'project':
                    abs_path = self.project_dir / import_node.path
                elif import_node.anchor == 'local':
                    parsed_file = source.get_path()
                    if parsed_file is None:
                        raise AizeImportError("Cannot use a local import from a non-file source", import_node.pos)
                    else:
                        abs_path = parsed_file.parent / import_node.path
                else:
                    raise ValueError(f"Invalid anchor: {import_node.anchor}")

                try:
                    abs_path = abs_path.resolve()
                except FileNotFoundError:
                    raise AizeFileError(f"Cannot open file {abs_path!s}", pos=import_node.pos)

                if source.get_path() and abs_path != source.get_path().resolve():
                    raise AizeImportError(f"A file cannot import itself", pos=import_node.pos)

                imported_source = self._make_file_source(abs_path, pos=import_node.pos)
                to_visit.append(imported_source)

        self._sources = sources


class IRManager:
    def __init__(self, ir: IR):
        self.ir: IR = ir

        self.scheduler = PassScheduler(self.ir, [])

    def schedule_default_passes(self):
        self.scheduler.schedule(DefaultPasses)

    def schedule_pass(self, ir_pass: PassAlias) -> bool:
        return self.scheduler.schedule(ir_pass)

    def run_scheduled(self):
        self.scheduler.run_scheduled()


T = TypeVar('T', bound=Backend)


class BackendManager(Generic[T]):
    def __init__(self, ir: IR, backend_type: Type[T]):
        self.ir: IR = ir
        self.backend: T = backend_type.create(ir)

    @classmethod
    def create_llvm(cls, ir: IR) -> BackendManager[LLVMBackend]:
        return cls(ir, LLVMBackend)

    def set_output(self, output: Optional[Path]):
        self.backend.set_output(output)

    def set_option(self, option: str):
        if not self.backend.handle_option(option):
            # TODO signal message handler
            pass

    def run_backend(self):
        self.backend.run_backend()

    def run_output(self):
        self.backend.run_output()
