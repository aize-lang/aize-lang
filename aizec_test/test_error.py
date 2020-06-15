import pytest

from aizec.aize_error import MessageHandler, AizeMessage, Reporter, ErrorLevel, FailFlag

from aizec.aize_source import Position, Source, StreamSource

from io import StringIO


@pytest.fixture()
def dummy_source() -> Source:
    dummy = StreamSource("<dummy>", StringIO())
    dummy.add_line("This is a test")
    return dummy


class PositionedError(AizeMessage):
    def __init__(self, type: str, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)

        self.type = type
        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error(self.type, self.msg, self.pos)


class TestErrorMessages:
    @pytest.fixture(autouse=True)
    def reset(self):
        MessageHandler.reset_config()
        MessageHandler.reset_errors()

    @pytest.fixture()
    def cap_err(self):
        err = StringIO()
        MessageHandler.set_config(err_out=err)
        return err

    def test_good_position1(self, dummy_source, cap_err):
        pos = Position.new_text(dummy_source, 1, (1, 5), False)
        with pytest.raises(FailFlag) as exc_info:
            MessageHandler.handle_message(PositionedError("Dummy Error", "Testing a Position", pos))
            MessageHandler.flush_messages()
        cap_err.seek(0)
        err = cap_err.read()
        assert err == 'In <dummy>:\nDummy Error: Testing a Position:\n     1 | This is a test\n         ^^^^\n'

    def test_good_position2(self, dummy_source, cap_err):
        pos = Position.new_text(dummy_source, 1, (1, 15), False)
        with pytest.raises(FailFlag) as exc_info:
            MessageHandler.handle_message(PositionedError("Dummy Error", "Testing a Position", pos))
            MessageHandler.flush_messages()
        cap_err.seek(0)
        err = cap_err.read()
        assert err == 'In <dummy>:\nDummy Error: Testing a Position:\n     1 | This is a test\n         ^^^^^^^^^^^^^^\n'

    def test_bad_position1(self, dummy_source, cap_err):
        pos = Position.new_text(dummy_source, 0, (1, 5), False)
        with pytest.raises(IndexError) as exc_info:
            MessageHandler.handle_message(PositionedError("Dummy Error", "Testing a Position", pos))
            MessageHandler.flush_messages()
        cap_err.seek(0)
        err = cap_err.read()
        assert err == ''

    def test_bad_position2(self, dummy_source, cap_err):
        pos = Position.new_text(dummy_source, 1, (70, 5), False)
        with pytest.raises(IndexError) as exc_info:
            MessageHandler.handle_message(PositionedError("Dummy Error", "Testing a Position", pos))
            MessageHandler.flush_messages()

        cap_err.seek(0)
        err = cap_err.read()
        assert err == ''

    def test_bad_position3(self, dummy_source, cap_err):
        pos = Position.new_text(dummy_source, 1, (1, 16), False)
        with pytest.raises(IndexError) as exc_info:
            MessageHandler.handle_message(PositionedError("Dummy Error", "Testing a Position", pos))
            MessageHandler.flush_messages()
        cap_err.seek(0)
        err = cap_err.read()
        assert err == ''
