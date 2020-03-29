from aizec.common import *
from aizec.aize_error import AizeMessage, ErrorHandler, Reporter
from aizec.aize_parser import AizeParser
from aizec.aize_pass_data import PositionData
from aizec.aize_semantics import SemanticAnalyzer
from aizec.aize_ast import Program, Source, FileSource, StdinSource, StringSource


class ImportNote(AizeMessage):
    def __init__(self, source_name: str, pos: PositionData):
        super().__init__(self.NOTE)

        self.source = source_name
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error("Note", self.source, self.pos, f"Imported here")


class InputError(AizeMessage):
    def __init__(self, errored_source: str, msg: str, note: AizeMessage = None):
        super().__init__(self.FATAL)
        self.errored_source = errored_source
        self.msg = msg

        self.note = note

    def display(self, reporter: Reporter):
        reporter.source_error("Input Error", self.errored_source, self.msg)
        if self.note is not None:
            reporter.separate()
            with reporter.indent():
                self.note.display(reporter)


def make_source(text: str, text_source: Union[Path, str]):
    if isinstance(text_source, Path):
        source = FileSource(text_source, text, True, [])
    else:
        if text_source == '<stdin>':
            source = StdinSource(text, True, [])
        elif text_source == '<string>':
            source = StringSource(text, True, [])
        else:
            raise ValueError("source must be a string or a Path object.")
    return source


class CompilerOptions:
    def __init__(self, file: Path, out_file: Path):
        self.file = file
        self.out_file = out_file


class AizeCompiler:
    def __init__(self, std_dir: Path, project_dir: Path, error_handler: ErrorHandler):
        self.std_dir: Path = std_dir
        self.project_dir: Path = project_dir
        self.error_handler: ErrorHandler = error_handler

        self._sources: List[Source] = []

    def add_file(self, path: Union[Path, str], is_main: bool = False, import_note: ImportNote = None) -> Source:
        source = self.create_source(path, is_main, import_note)
        return self.add_source(source)

    def add_source(self, source: Source) -> Source:
        self._sources.append(source)
        return source

    def create_source(self, path: Union[Path, str], is_main: bool = False, import_note: ImportNote = None) -> Source:
        if isinstance(path, str):
            path = Path(path)
        try:
            if path.is_absolute():
                input_file = path
            else:
                input_file = self.project_dir / path
            input_file = path.absolute().resolve()
        except OSError:
            self.error(InputError(path, "File does not exist", import_note))
        else:
            if not input_file.exists():
                self.error(InputError(input_file, "File does not exist", import_note))
            # TODO .read_text() can ValueError, catch that and make it an InputError(FATAL)
            source = FileSource(input_file, input_file.read_text(), is_main, [])
            return source
        finally:
            self.flush_errors()
        assert False

    def parse_source(self, source: Source) -> Source:
        return AizeParser.parse(source, self.error_handler)

    def trace_imports(self, *, reload: bool = False):
        to_parse: List[Source] = self._sources.copy()
        if reload:
            self._sources = []
            visited: Set = set()
        else:
            self._sources = [source for source in self._sources if len(source.top_levels) != 0]
            visited: Set = set(source.get_unique() for source in self._sources)

        while len(to_parse) > 0:
            source: Source = to_parse.pop()
            if source.get_unique() not in visited:
                self.parse_source(source)
                self.add_source(source)

                visited.add(source.get_unique())

                for import_node in source.imports:
                    if import_node.anchor == 'std':
                        abs_path = self.std_dir / import_node.path
                    elif import_node.anchor == 'project':
                        abs_path = self.project_dir / import_node.path
                    elif import_node.anchor == 'local':
                        parsed_file = source.get_path()
                        if parsed_file is None:
                            self.fatal_error(InputError(source.get_name(), "Cannot do a local import on a non-file source"))  # , NodePosition.of(import_node)))
                            assert False
                        else:
                            abs_path = parsed_file.parent / import_node.path
                    else:
                        raise ValueError(f"Invalid anchor: {import_node.anchor!r}")

                    if abs_path == source.get_path():
                        self.error(InputError(source.get_name(), "Files cannot import themselves", ImportNote(source.get_name(), PositionData.of(import_node))))
                    new_source = self.create_source(abs_path, False, ImportNote(source.get_name(), PositionData.of(import_node)))
                    to_parse.append(new_source)
        self.flush_errors()

    def get_program(self):
        return Program(self._sources)

    def analyze(self):
        SemanticAnalyzer.analyze(self.get_program(), self.error_handler)

    def error(self, msg: AizeMessage):
        self.error_handler.handle_message(msg)

    def fatal_error(self, msg: AizeMessage):
        self.error_handler.handle_message(msg)
        self.error_handler.flush_errors()
        assert False

    def flush_errors(self):
        self.error_handler.flush_errors()
