import io

from aizec.common import *

from aizec.aize_error import AizeMessage, MessageHandler, Reporter
from aizec.aize_parser import AizeParser
from aizec.aize_semantics import CreateIR
from aizec.aize_source import Source, FileSource, Position, StreamSource

from aizec.aize_ast import ProgramAST, SourceAST
from aizec.aize_ir import ProgramIR


__all__ = ['FrontendManager', 'IRManager', 'BackendManager',
           'AizeFrontendError', 'AizeImportError', 'AizeFileError']


class InputError(AizeMessage):
    def __init__(self, msg: str, pos: Position = None):
        super().__init__(self.FATAL)

        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        if self.pos is None:
            reporter.general_error("Input Error", self.msg)
        else:
            reporter.positioned_error("Input Error", self.msg, self.pos)


class AizeFrontendError(Exception):
    def report(self):
        raise NotImplementedError()


class AizeImportError(AizeFrontendError):
    def __init__(self, msg: str, pos: Position):
        super().__init__(msg)
        self.msg = msg
        self.pos = pos

    def report(self):
        msg = InputError(self.msg, self.pos)
        MessageHandler.handle_message(msg)
        MessageHandler.flush_messages()
        assert False


class AizeFileError(AizeFrontendError):
    def __init__(self, msg: str, pos: Position = None):
        super().__init__(msg)
        self.msg = msg
        self.pos: Optional[Position] = pos

    def report(self):
        msg = InputError(self.msg, self.pos)
        MessageHandler.handle_message(msg)
        MessageHandler.flush_messages()
        assert False


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

    def get_program_ir(self) -> ProgramIR:
        return CreateIR.create_ir(self.get_program_ast())

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
    def __init__(self, program: ProgramIR):
        self.program: ProgramIR = program


class BackendManager:
    def __init__(self):
        # TODO
        pass
