import pytest

from aizec.aize_parser import AizeParser, ParseError
from aizec.aize_error import MessageHandler, ThrownMessage
from aizec.aize_source import Source
from aizec.aize_run import FrontendManager
from aizec.common import Path


@pytest.fixture(autouse=True)
def set_throw():
    MessageHandler.set_throw(True)


class TestClass:
    def load_test_file(self, name: str) -> Source:
        return FrontendManager.make_file_source(Path("parser_test_files") / "class" / name)

    def test_smallest(self):
        test_file = self.load_test_file("smallest_class.az")
        AizeParser.parse(test_file)

    def test_class_attrs(self):
        test_file = self.load_test_file("class_attrs.az")
        AizeParser.parse(test_file)

    def test_class_methods(self):
        test_file = self.load_test_file("class_methods.az")
        AizeParser.parse(test_file)


class TestComments:
    def load_test_file(self, name: str) -> Source:
        return FrontendManager.make_file_source(Path("parser_test_files") / "comment" / name)

    def test_comment(self):
        test_file = self.load_test_file("comment.az")
        AizeParser.parse(test_file)

    def test_comments_ignored(self):
        test_file = self.load_test_file("comments_ignored.az")
        AizeParser.parse(test_file)

    def test_bad_comments(self):
        test_file = self.load_test_file("bad_comment.az")
        with pytest.raises(ThrownMessage) as exc_info:
            AizeParser.parse(test_file)
        assert isinstance(exc_info.value.message, ParseError)


class TestOneLine:
    def load_test_file(self, name: str) -> Source:
        return FrontendManager.make_file_source(Path("parser_test_files") / "one_line" / name)

    def test_empty_source(self):
        test_file = self.load_test_file("empty.az")
        AizeParser.parse(test_file)

    def test_one_line_ok(self):
        test_file = self.load_test_file("one_line_ok.az")
        AizeParser.parse(test_file)

    def test_one_line_bad(self):
        test_file = self.load_test_file("one_line_bad.az")
        with pytest.raises(ThrownMessage) as exc_info:
            AizeParser.parse(test_file)
        assert isinstance(exc_info.value.message, ParseError)
