import io

from aizec.common import *

from aizec.aize_error import AizeMessage, MessageHandler, Reporter
from aizec.aize_parser import AizeParser
# from aizec.aize_semantics import AizeAnalyzer
# from aizec.aize_backend import IRToLLVM
from aizec.aize_source import Source, FileSource, Position, StreamSource
from aizec.aize_ast import ProgramAST, SourceAST


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

        self._sources: List[Source] = []
        self._source_asts: List[SourceAST] = []

    @staticmethod
    def _parse_source(source: Source) -> SourceAST:
        return AizeParser.parse(source)

    def _fatal_error(self, msg: AizeMessage):
        MessageHandler.handle_message(msg)
        MessageHandler.flush_messages()
        assert False

    @staticmethod
    def make_file_source(path: Path, pos: Position = None) -> FileSource:
        try:
            path = path.resolve()
        except FileNotFoundError:
            raise AizeFileError(f"Cannot open file {path!s}", pos) from None

        file_stream = path.open("r")
        return FileSource(path, file_stream)

    @staticmethod
    def make_text_source(text: str, pos: Position = None) -> StreamSource:
        text_stream = io.StringIO(text)

        return StreamSource("<string>", text_stream)

    def get_program_ast(self) -> ProgramAST:
        return ProgramAST(self._source_asts.copy())

    def add_source(self, source: Source):
        self._sources.append(source)
        self._source_asts.append(self._parse_source(source))

    def trace_imports(self, from_sources: List[Source] = None):
        to_visit: List[Source] = self._sources.copy() + ([] if from_sources is None else from_sources)
        visited: Set = set()
        source_asts: List[SourceAST] = []
        sources: List[Source] = []

        while to_visit:
            source = to_visit.pop()
            if source.get_unique() in visited:
                continue

            source_ast = self._parse_source(source)
            sources.append(source)
            source_asts.append(source_ast)

            visited.add(source.get_unique())

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

                imported_source = self.make_file_source(abs_path, pos=import_node.pos)
                to_visit.append(imported_source)

        self._sources = sources
        self._source_asts = source_asts


class IRManager:
    def __init__(self, program_ast: ProgramAST):
        self.program_ast = program_ast

    def get_program_ir(self):
        # TODO
        pass


class BackendManager:
    def __init__(self):
        # TODO
        pass
