from __future__ import annotations

import contextlib

from aizec.aize_ast import *
from aizec.common import *
from aizec.aize_source import Source, Position
from aizec.aize_error import AizeMessage, MessageHandler

BASIC_TOKENS = Trie.from_list([
    "+", "+=",
    "-", "-=", "->",
    "/", "//",
    "/=", "//=",
    "*", "**",
    "*=", "**=",
    "%", "%=",
    "^", "^=", "|", "|=", "&", "&=",
    "!", "~",
    "==", "!=", "<", "<=", ">", ">=",
    "(", ")", "[", "]", "{", "}",
    "=", ",", ".", ":", ";",
    "@", "::"
])

KEYWORDS = ['class', 'trait', 'def', 'method', 'attr', 'var', 'while', 'if', 'return', 'else', 'import']

BIN = '01'
OCT = BIN + '234567'
DEC = OCT + '89'
HEX = DEC + 'ABCDEF'
IDENT_START = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
IDENT = IDENT_START + DEC


class ParseError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(self.ERROR)

        self.msg = msg
        self.pos = pos

    def display(self, reporter):
        reporter.positioned_error(type="Parsing Error", msg=self.msg, pos=self.pos)


class Token:
    def __init__(self, text: str, type: str, source: Source, line_no: int, columns: Tuple[int, int]):
        self.text = text
        self.type = type

        self.source = source
        self.line_no = line_no
        self.columns = columns

    def pos(self):
        return Position.new_text(self.source, self.line_no, self.columns)

    def __repr__(self):
        return f"Token({self.text!r}, {self.type!r})"


class TokenTrie:
    def __init__(self, char: str, children: List[TokenTrie]):
        self.char = char
        self.children = children

    @classmethod
    def from_list(cls, li: List[str]):
        pass


class Scanner:
    def __init__(self, source: Source):
        self.source = source

        self._curr_line: str = ""
        self._curr_char: str = "\0"
        self._line_pos: int = 0
        """The index after that of the character currently in self._curr_char"""

        self._line_no: int = 1
        # """Is in fact 1-indexed, but starts at 0 since advance() increments it instantly"""
        self._token: str = ""
        self._token_line_pos: int = 1

        self._is_last_line = False
        self._is_done = False

    @classmethod
    def scan_source(cls, source: Source) -> Iterator[Token]:
        scanner = Scanner(source)
        return scanner.iter_tokens()

    # region utility methods
    def is_done(self) -> bool:
        return self._is_done

    def is_last_line(self) -> bool:
        return self._is_last_line

    def at_line_end(self) -> bool:
        return self._line_pos == len(self._curr_line)

    def load_next_line(self):
        if self.is_last_line():
            self._curr_line = ""
            self._line_pos = 0
            self._token_line_pos = 1
            return
        line = ""
        while (char := self.source.read_char()) not in ("", "\n"):
            line += char
        if char == "":
            self._is_last_line = True
        self.source.add_line(line)
        self._curr_line = line
        self._line_pos = 0
        self._line_no += 1

    def advance(self):
        self._token += self._curr_char
        if self._line_pos == 1:
            self._token_line_pos = 1
        self._token_line_pos += 1

        # Keep loading lines until we reach a line with at least a character or the end
        while not self.is_last_line() and self.at_line_end():
            self.load_next_line()
        if self.at_line_end():
            self._is_done = True
        if self.is_done():
            self._curr_char = "\0"
        else:
            self._curr_char = self._curr_line[self._line_pos]
            self._line_pos += 1

    def init(self):
        self._line_no = 0
        self._token_line_pos = 1

        while not self.is_last_line() and self.at_line_end():
            self.load_next_line()
        if self.at_line_end():
            self._is_done = True
        if self.is_done():
            self._curr_char = "\0"
        else:
            self._curr_char = self._curr_line[self._line_pos]
            self._line_pos += 1

    @property
    def curr(self):
        return self._curr_char

    def match_basic(self) -> Union[Token, None]:
        if self.curr in BASIC_TOKENS.children:
            with self.start_token() as token:
                trie = BASIC_TOKENS.children[self.curr]
                self.advance()
                while self.curr in trie.children:
                    trie = BASIC_TOKENS.children[self.curr]
                    self.advance()
                if not trie.is_leaf:
                    raise Exception("Token is not conclusive")
            return token
        else:
            return None

    @contextlib.contextmanager
    def start_token(self, type: Union[str, None] = None):
        self._token = ""
        line_no = self._line_no
        start_line_pos = self._token_line_pos

        token = Token.__new__(Token)
        yield token

        text = self._token
        if type is None:
            type = text

        token.__init__(text, type, self.source, line_no, (start_line_pos, self._token_line_pos))
    # endregion

    def iter_tokens(self) -> Iterator[Token]:
        self.init()
        while not self.is_done():
            token = self.match_basic()
            if token:
                yield token
            else:
                if self.curr in "0123456789":
                    with self.start_token("dec") as token:
                        while self.curr in "0123456789":
                            self.advance()
                    yield token
                elif self.curr in IDENT_START:
                    with self.start_token("ident") as token:
                        while self.curr in IDENT:
                            self.advance()
                    if token.text in KEYWORDS:
                        token.type = token.text
                    yield token
                elif self.curr == "\"":
                    with self.start_token("str") as token:
                        self.advance()
                        while self.curr != "\"":
                            if self.curr == "\\":
                                self.advance()
                            if self.curr == "\n":
                                # TODO ERROR REPORTING
                                assert False
                            self.advance()
                        if self.is_done():
                            # TODO ERROR REPORTING
                            assert False
                        self.advance()
                    yield token
                elif self.curr == "#":
                    self.advance()
                    if self.curr == " ":
                        while not self.curr == "\n":
                            self.advance()
                    continue
                elif self.curr in ('\t', ' '):
                    self.advance()
                    continue
                else:
                    with self.start_token("<unexpected characters>") as token:
                        self.advance()
                    MessageHandler.handle_message(ParseError(f"Cannot tokenize character '{token.text!s}'", token.pos()))
        while True:
            yield Token('<eof>', '<eof>', self.source, self._line_no, (self._token_line_pos, self._token_line_pos+1))


class SyncFlag(Exception):
    def __init__(self, flag: int):
        self.flag = flag


class SyncPosition:
    def __init__(self):
        self.have_synced = False


class AizeParser:
    def __init__(self, token_stream: Iterator[Token], source: Source):
        self._token_stream: Iterator[Token] = token_stream
        self.curr: Token = Token('<eof>', '<eof>', source, 1, (1, 1))
        self.source = source

        self.sync_targets = []

        self._is_done = False
        self.advance()

    @classmethod
    def parse(cls, source: Source):
        parser = cls(Scanner.scan_source(source), source)
        parsed = parser.parse_source(source)
        return parsed

    # region utility methods
    def is_done(self):
        return self._is_done

    def curr_is(self, type: str):
        return self.curr.type == type

    def match(self, type: str) -> Union[Token, None]:
        if self.curr_is(type):
            return self.advance()
        else:
            return None

    def advance(self) -> Token:
        old, self.curr = self.curr, next(self._token_stream)
        if self.curr.type == '<eof>':
            self._is_done = True
        return old

    def match_exc(self, type: str) -> Token:
        match = self.match(type)
        if not match:
            if self.report_error(f"Expected '{type}', got '{self.curr.type}'", self.curr):
                self.synchronize()
            else:
                assert False
        return match

    def report_error(self, msg: str, pos: Union[Token, TextAST, Position], is_fatal: bool = False):
        if isinstance(pos, Token):
            pos = pos.pos()
        elif isinstance(pos, TextAST):
            # TODO
            pos = pos.pos
        self.source.has_errors = True
        MessageHandler.handle_message(ParseError(msg, pos))
        if is_fatal:
            MessageHandler.flush_messages()
            return False
        else:
            return True

    def synchronize(self):
        while not self.is_done():
            for n, targets in reversed(list(enumerate(self.sync_targets))):
                if self.curr.type in targets:
                    raise SyncFlag(n)
            else:
                self.advance()
        raise SyncFlag(-1)

    @contextlib.contextmanager
    def sync_point(self, *targets: str) -> SyncPosition:
        flag_num = len(self.sync_targets)
        self.sync_targets.append(targets)
        pos = SyncPosition()
        try:
            yield pos
        except SyncFlag as flag:
            if flag.flag == flag_num:
                pos.have_synced = True
            else:
                raise
        self.sync_targets.pop()
    # endregion

    def parse_source(self, source: Source) -> SourceAST:
        top_levels: List[TopLevelAST] = []
        try:
            while not self.is_done():
                with self.sync_point("class", "trait", "def", "import"):
                    if self.curr_is("class"):
                        top_levels += [self.parse_class()]
                    # elif self.curr_is("trait"):
                    #     top_levels += [self.parse_trait()]
                    elif self.curr_is("def"):
                        top_levels += [self.parse_function()]
                    elif self.curr_is("import"):
                        top_levels += [self.parse_import()]
                    else:
                        if self.report_error(f"Expected one of 'class', 'trait', 'def', or 'import' (got {self.curr.text!r})", self.curr):
                            self.synchronize()
                        else:
                            assert False
        except SyncFlag as flag:
            if flag.flag == -1:
                pass
            else:
                raise ValueError(f"flag reached top without being caught {flag.flag}")
        finally:
            MessageHandler.flush_messages()
        return SourceAST(source, top_levels)

    def parse_class(self) -> ClassAST:
        start = self.match_exc("class")

        name = self.match_exc("ident").text

        if self.match("["):
            type_vars = []
            while not self.match("]"):
                type_var = self.match("ident").text
                type_vars.append(type_var)
                if not self.match(","):
                    self.match_exc("]")
                    break
        else:
            type_vars = []

        if self.match(":"):
            traits = []
            while not self.match("{"):
                trait = self.parse_type()
                traits.append(trait)
                if not self.match(","):
                    self.match_exc("{")
                    break
        else:
            traits = []
            self.match_exc("{")

        body = []
        while not self.match("}"):
            with self.sync_point("attr", "method"):
                if self.curr_is("attr"):
                    body.append(self.parse_attr())
                elif self.curr_is("method"):
                    body.append(self.parse_method())
                else:
                    if self.report_error("Class body statements must start with one of 'attr' or 'method'", self.curr):
                        self.synchronize()
                        assert False
                    else:
                        assert False

        return ClassAST(name, traits, body, start.pos())

    # def parse_trait(self):
    #     start = self.match_exc("trait")
    #
    #     name = self.match_exc("ident").text
    #
    #     self.match_exc("{")
    #     body = []
    #     while not self.match("}"):
    #         with self.sync_point("method", "attr"):
    #             if self.curr_is("method"):
    #                 body.append(self.parse_method())
    #             elif self.curr_is("attr"):
    #                 if self.report_error("Traits cannot have attributes", self.curr):
    #                     self.synchronize()
    #                     assert False
    #                 else:
    #                     assert False
    #             else:
    #                 if self.report_error("Trait body statements must start with 'method'", self.curr):
    #                     self.synchronize()
    #                     assert False
    #                 else:
    #                     assert False
    #
    #     return TraitAST(name, [], body).add_data(start.pos())

    def parse_attr(self) -> AttrAST:
        start = self.match("attr")
        name = self.match_exc("ident").text
        self.match_exc(":")
        ann = self.parse_ann()
        self.match_exc(";")
        return AttrAST(name, ann, start.pos())

    def parse_method_sig(self) -> MethodSigAST:
        start = self.match("method")
        name = self.match_exc("ident").text
        self.match_exc("(")
        args = []
        while not self.match(")"):
            param_name = self.match_exc("ident")
            if not self.match(":"):
                if len(args) == 0:  # If this is the first argument (self), which doesn't need an annotation
                    param_ann = None
                else:               # Otherwise we need an annotation
                    if self.report_error("Annotation expected", self.curr):
                        self.synchronize()
                        assert False
                    else:
                        assert False
            else:
                param_ann = self.parse_ann()
            args.append(ParamAST(param_name.text, param_ann, param_name.pos()))
            if not self.match(","):
                self.match_exc(")")
                break
        if self.match("->"):
            ret = self.parse_ann()
        else:
            ret = None
        return MethodSigAST(name, args, ret, start.pos())

    def parse_method(self) -> MethodSigAST:
        sig = self.parse_method_sig()
        if self.match("{"):
            body = []
            while not self.match("}"):
                body.append(self.parse_stmt())
            return MethodImplAST.from_sig(sig, body)
        else:
            self.match_exc(";")
            return sig

    def parse_import(self) -> ImportAST:
        start = self.match("import")

        import_str = self.match_exc("str")
        path = Path(import_str.text[1:-1])
        if len(path.parts) > 0:
            first_part = path.parts[0]
            if first_part.startswith("<") and first_part.endswith(">"):
                anchor = first_part[1:-1]
                if anchor not in ("std", "project", "local"):
                    if self.report_error("Anchor must be one of <std>, <project>, or <local>", import_str.pos()):
                        self.synchronize()
                        assert False
                    else:
                        assert False
                path = Path("").joinpath(*path.parts[1:])
            else:
                anchor = 'project'
        else:
            anchor = 'project'

        end = self.match_exc(";")

        return ImportAST(anchor, path, start.pos() + end.pos())

    def parse_function(self):
        start = self.match("def")
        name = self.match_exc("ident")
        self.match_exc("(")
        params = []
        while not self.match(")"):
            param_name = self.match_exc("ident")
            self.match_exc(":")
            param_ann = self.parse_ann()
            params.append(ParamAST(param_name.text, param_ann, param_name.pos()))
            if not self.match(","):
                self.match_exc(")")
                break
        if self.match("->"):
            ret = self.parse_ann()
        else:
            ret = None
        self.match_exc("{")

        body = []
        with self.sync_point():
            while not self.curr_is("}"):
                body.append(self.parse_stmt())
        self.match_exc("}")

        return FunctionAST(name.text, params, ret, body, start.pos())

    def parse_ann(self) -> ExprAST:
        return self.parse_expr()

    def parse_type(self) -> ExprAST:
        return self.parse_expr(skip_assign=True)

    def parse_stmt(self) -> StmtAST:
        if self.curr_is("return"):
            return self.parse_return()
        elif self.curr_is("if"):
            return self.parse_if()
        elif self.curr_is("while"):
            return self.parse_while()
        elif self.curr_is("{"):
            return self.parse_block()
        elif self.curr_is("var"):
            return self.parse_var()
        else:
            return self.parse_expr_stmt()

    def parse_if(self) -> IfStmtAST:
        start = self.match("if")
        self.match_exc("(")
        cond = self.parse_expr()
        self.match_exc(")")
        body = self.parse_stmt()
        if self.match("else"):
            else_body = self.parse_stmt()
        else:
            else_body = BlockStmtAST([], body.pos)
        return IfStmtAST(cond, body, else_body, start.pos())

    def parse_while(self) -> WhileStmtAST:
        start = self.match("while")
        self.match_exc("(")
        cond = self.parse_expr()
        self.match_exc(")")
        body = self.parse_stmt()
        return WhileStmtAST(cond, body, start.pos())

    def parse_block(self) -> BlockStmtAST:
        start = self.match_exc("{")
        body = []
        while not self.match("}"):
            body.append(self.parse_stmt())
        return BlockStmtAST(body, start.pos())

    def parse_var(self) -> VarDeclStmtAST:
        start = self.match("var")
        var = self.match_exc("ident").text
        if self.match(":"):
            type = self.parse_type()
        else:
            type = None
        self.match_exc("=")
        val = self.parse_expr()
        self.match_exc(";")
        return VarDeclStmtAST(var, type, val, start.pos())

    def parse_return(self) -> ReturnStmtAST:
        start = self.match_exc("return")
        expr = self.parse_expr()
        self.match_exc(";")
        return ReturnStmtAST(expr, start.pos())

    def parse_expr_stmt(self) -> ExprStmtAST:
        start = self.curr
        expr = self.parse_expr()
        self.match_exc(";")
        return ExprStmtAST(expr, start.pos())

    def parse_expr(self, *, skip_assign=False) -> ExprAST:
        if skip_assign:
            return self.parse_logic()
        else:
            return self.parse_assign()

    def parse_assign(self) -> ExprAST:
        expr = self.parse_logic()
        if start := self.match("="):
            right: ExprAST = self.parse_assign()
            if isinstance(expr, GetVarExprAST):
                expr = SetVarExprAST(expr.var, right, start.pos())
            elif isinstance(expr, GetAttrExprAST):
                expr = SetAttrExprAST(expr.obj, expr.attr, right, start.pos())
            else:
                if self.report_error("Assignment targets must be a variable or an attribute", right):
                    self.synchronize()
                    assert False
                else:
                    assert False
        return expr

    def parse_logic(self) -> ExprAST:
        # TODO and/or
        return self.parse_cmp()

    def parse_cmp(self) -> ExprAST:
        expr = self.parse_add()
        while self.curr.type in ("<", ">"):
            start = self.curr
            if self.curr.type == "<":
                self.match("<")
                right = self.parse_add()
                expr = LTExprAST(expr, right, start.pos())
            elif self.curr.type == ">":
                self.match(">")
                right = self.parse_add()
                expr = GTExprAST(expr, right, start.pos())
            elif self.curr.type == "<=":
                self.match("<=")
                right = self.parse_add()
                expr = LEExprAST(expr, right, start.pos())
            elif self.curr.type == ">=":
                self.match(">=")
                right = self.parse_add()
                expr = GEExprAST(expr, right, start.pos())
            elif self.curr.type == "==":
                self.match("==")
                right = self.parse_add()
                expr = EQExprAST(expr, right, start.pos())
            elif self.curr.type == "!=":
                self.match("!=")
                right = self.parse_add()
                expr = NEExprAST(expr, right, start.pos())
        return expr

    def parse_add(self):
        expr = self.parse_mul()
        while self.curr.type in ("+", "-"):
            start = self.curr
            if self.curr.type == "+":
                self.match("+")
                right = self.parse_mul()
                expr = AddExprAST(expr, right, start.pos())
            elif self.curr.type == "-":
                self.match("-")
                right = self.parse_mul()
                expr = SubExprAST(expr, right, start.pos())
        return expr

    def parse_mul(self):
        expr = self.parse_unary()  # TODO power between this and unary
        while self.curr.type in ("*", "/", "%"):
            start = self.curr
            if self.curr.type == "*":
                self.match("*")
                right = self.parse_unary()
                expr = MulExprAST(expr, right, start.pos())
            elif self.curr.type == "/":
                self.match("/")
                right = self.parse_unary()
                expr = DivExprAST(expr, right, start.pos())
            # elif self.curr.type == "//":
            #     self.match("//")
            #     right = self.parse_unary()
            #     expr = FloorDiv(expr, right)
            elif self.curr.type == "%":
                self.match("%")
                right = self.parse_unary()
                expr = ModExprAST(expr, right, start.pos())
        return expr

    def parse_unary(self):
        if self.curr.type in ("-", "!", "~"):
            start = self.curr
            if self.match("-"):
                right = self.parse_unary()
                return NegExprAST(right, start.pos())
            elif self.match("!"):
                right = self.parse_unary()
                return NotExprAST(right, start.pos())
            elif self.match("~"):
                right = self.parse_unary()
                return InvExprAST(right, start.pos())
        return self.parse_call()

    def parse_call(self):
        expr = self.parse_primary()
        while True:
            if start := self.match("("):
                args = []
                while not self.match(")"):
                    arg = self.parse_expr()
                    args.append(arg)
                    if not self.match(","):
                        self.match_exc(")")
                        break
                expr = CallExprAST(expr, args, start.pos())
            elif start := self.match("."):
                # TODO maybe also match number for tuples?
                attr = self.match_exc("ident")
                expr = GetAttrExprAST(expr, attr.text, start.pos())
            # TODO Namespaces
            # elif self.match("::"):
            #     start = self.prev
            #     attr = self.match_exc("ident")
            #     if isinstance(expr, GetVarExpr):
            #         expr = GetNamespaceExpr(GetNamespace(expr.name).place(expr.pos), attr.text).place(start.pos)
            #     else:
            #         raise ParseError("Cannot get an attribute from the left", start)
            else:
                break
        return expr

    def parse_primary(self):
        if self.match("("):
            expr = self.parse_expr()
            self.match_exc(")")
            return expr
        elif self.curr_is("dec"):
            num = self.match("dec")
            return IntLiteralAST(int(num.text), num.pos())
        elif self.curr_is("str"):
            s = self.match("str")
            s_e = s.text.encode().decode("unicode-escape")
            return StrLiteralAST(s_e, s.pos())
        elif self.curr_is("ident"):
            var = self.match("ident")
            return GetVarExprAST(var.text, var.pos())
        else:
            if self.report_error(f"Cannot parse '{self.curr.type}' token", self.curr):
                assert False
            else:
                assert False
