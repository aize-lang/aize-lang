from __future__ import annotations

from aizec.common import *
from aizec.aize_common import AizeMessage, MessageHandler, ErrorLevel, Source, Position

from .aize_ast import *


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

BASIC_START = list(BASIC_TOKENS.children.keys())

KEYWORDS = ['class', 'struct', 'def', 'method', 'attr', 'var', 'while', 'if', 'return', 'else', 'import', 'new']

BIN = '01'
OCT = BIN + '234567'
DEC = OCT + '89'
HEX = DEC + 'ABCDEF'
IDENT_START = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
IDENT = IDENT_START + DEC

TOKENIZE_ABLE = ''.join(BASIC_START) + IDENT_START + DEC


class ParseError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)

        self.msg = msg
        self.pos = pos

    def display(self, reporter):
        reporter.positioned_error(type="Parsing Error", msg=self.msg, pos=self.pos)

    def __repr__(self):
        return f"ParseError({self.msg!r}, {self.pos!r})"


class Token:
    DECIMAL_TYPE = "decimal-number"
    STRING_TYPE = "string-literal"
    IDENTIFIER_TYPE = "identifier"

    def __init__(self, text: str, type: str, source: Source, line_no: int, columns: Tuple[int, int]):
        self.text = text
        self.type = type

        self.source = source
        self.line_no = line_no
        self.columns = columns

    def pos(self):
        return Position.new_text(self.source, self.line_no, self.columns, False)

    def __repr__(self):
        return f"Token({self.text!r}, {self.type!r})"


class SourceLoader:
    def __init__(self, source: Source):
        self.source = source
        self.stream = source.get_stream()

        self._loaded: str = ""
        self._is_done = False
        self._line: str = ""

    @property
    def _last(self):
        return self._loaded[-1]

    def is_done(self) -> bool:
        return self._is_done

    def advance(self):
        if self._is_done:
            return
        char = self.stream.read(1)
        if char == '':
            self.source.add_line(self._line)
            self._is_done = True
        else:
            if char == '\n':
                self.source.add_line(self._line)
                self._line = ""
            else:
                self._line += char
            self._loaded += char

    def get_char(self, index: int):
        while index >= len(self._loaded) and not self._is_done:
            self.advance()
        if self._is_done:
            return "\0"
        else:
            return self._loaded[index]


class Scanner:
    def __init__(self, source: Source):
        self.source = source

        self.loader = SourceLoader(source)
        self.index = 0
        self.line_no = 1
        self.line_index = 1
        """1-indexed position on the line (1 means self.curr is the first character of the line)"""

        self._building_tokens: List[str] = []

    @classmethod
    def scan_source(cls, source: Source) -> Iterator[Token]:
        scanner = Scanner(source)
        return scanner.iter_tokens()

    # region utility methods
    def is_done(self) -> bool:
        return self.loader.is_done()

    @property
    def curr(self):
        return self.loader.get_char(self.index)

    def advance(self):
        for i in range(len(self._building_tokens)):
            self._building_tokens[i] += self.curr
        self.loader.advance()
        if not self.is_done():
            self.index += 1
            self.line_index += 1

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

    @contextmanager
    def start_token(self, type: Union[str, None] = None):
        self._building_tokens.append("")
        start_line_no = self.line_no
        start_line_index = self.line_index

        token = Token.__new__(Token)
        yield token

        text = self._building_tokens.pop()
        if type is None:
            type = text
        end_line_no = self.line_no
        end_line_index = self.line_index

        token.__init__(text, type, self.source, start_line_no, (start_line_index, end_line_index))
    # endregion

    def iter_tokens(self) -> Iterator[Token]:
        while not self.is_done():
            token = self.match_basic()
            if token:
                yield token
            else:
                if self.curr in "0123456789":
                    with self.start_token(Token.DECIMAL_TYPE) as token:
                        while self.curr in "0123456789":
                            self.advance()
                    yield token
                elif self.curr in IDENT_START:
                    with self.start_token(Token.IDENTIFIER_TYPE) as token:
                        while self.curr in IDENT:
                            self.advance()
                    if token.text in KEYWORDS:
                        token.type = token.text
                    yield token
                elif self.curr == "\"":
                    with self.start_token(Token.STRING_TYPE) as token:
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
                    with self.start_token("<comment>") as token:
                        self.advance()
                        at_line_end = self.curr == '\n'
                        if self.curr in (" ", "\n", "\0"):
                            while self.curr != '\n' and not self.is_done():
                                self.advance()
                            continue
                    MessageHandler.handle_message(ParseError(f"Comment must be followed by a space or newline", token.pos()))
                elif self.curr == '\n':
                    self.advance()
                    self.line_no += 1
                    self.line_index = 1
                    continue
                elif self.curr in ('\t', ' '):
                    self.advance()
                    continue
                elif self.curr == '\0':
                    break
                else:
                    with self.start_token("<unexpected characters>") as token:
                        while self.curr not in TOKENIZE_ABLE and not self.is_done():
                            self.advance()
                    if len(token.text) == 1:
                        MessageHandler.handle_message(ParseError(f"Cannot tokenize character '{token.text!s}'", token.pos()))
                    elif len(token.text) > 1:
                        MessageHandler.handle_message(ParseError(f"Cannot tokenize characters '{token.text!s}'", token.pos()))
                    else:
                        raise ValueError(self.curr)
        while True:
            yield Token('<eof>', '<eof>', self.source, self.line_no, (self.line_index, self.line_index))


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

    def match_any(self, *types: str) -> Union[Token, None]:
        if self.curr.type in types:
            return self.advance()
        else:
            return None

    def match_any_exc(self, *types: str) -> Token:
        match = self.match_any(*types)
        if not match:
            if self.report_error(f"Expected any of {', '.join(types)}, got {self.curr.type}", self.curr):
                self.synchronize()
            else:
                assert False
        return match

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

    @contextmanager
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
                with self.sync_point("class", "struct", "def", "import", "@"):
                    if self.curr_is("class"):
                        top_levels += [self.parse_class()]
                    elif self.curr_is("struct"):
                        top_levels += [self.parse_struct()]
                    elif self.curr_is("def") or self.curr_is("@"):
                        top_levels += [self.parse_function()]
                    elif self.curr_is("import"):
                        top_levels += [self.parse_import()]
                    else:
                        if self.report_error(f"Expected one of 'class', 'struct', 'def', or 'import' (got {self.curr.text!r})", self.curr):
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

        name = self.match_exc(Token.IDENTIFIER_TYPE).text

        if self.match("["):
            type_vars = []
            while not self.match("]"):
                type_var = self.match(Token.IDENTIFIER_TYPE).text
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

    def parse_struct(self) -> StructAST:
        start = self.match("struct")
        name = self.match_exc(Token.IDENTIFIER_TYPE)

        self.match_exc("{")
        attrs = []
        while not (end := self.match("}")):
            with self.sync_point("attr"):
                if self.curr_is("attr"):
                    attr = self.parse_attr()
                    attrs += [attr]
                else:
                    self.report_error("Struct body must consist entirely of attributes", self.curr)
                    self.synchronize()
                    assert False

        return StructAST(name.text, attrs, start.pos())

    def parse_attr(self) -> AttrAST:
        start = self.match("attr")
        name = self.match_exc(Token.IDENTIFIER_TYPE).text
        self.match_exc(":")
        ann = self.parse_ann()
        self.match_exc(";")
        return AttrAST(name, ann, start.pos().to(ann.pos))

    def parse_method_sig(self) -> MethodSigAST:
        start = self.match("method")
        name = self.match_exc(Token.IDENTIFIER_TYPE).text
        self.match_exc("(")
        args = []
        while not self.match(")"):
            param_name = self.match_exc(Token.IDENTIFIER_TYPE)
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

        import_str = self.match_exc(Token.STRING_TYPE)
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

        return ImportAST(anchor, path, start.pos().to(end.pos()))

    def parse_function(self):
        attrs = []
        while attr_start := self.match("@"):
            attr_name = self.match_exc(Token.IDENTIFIER_TYPE)
            attr = FunctionAttributeAST(attr_name.text, Position.combine(attr_start.pos(), attr_name.pos()))
            attrs.append(attr)
        start = self.match("def")
        name = self.match_exc(Token.IDENTIFIER_TYPE)
        self.match_exc("(")
        params = []
        while not self.match(")"):
            param_name = self.match_exc(Token.IDENTIFIER_TYPE)
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

        return FunctionAST(name.text, params, ret, body, attrs, start.pos())

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
        var = self.match_exc(Token.IDENTIFIER_TYPE)
        if self.match(":"):
            type = self.parse_type()
        else:
            type = None
        self.match_exc("=")
        val = self.parse_expr()
        self.match_exc(";")
        return VarDeclStmtAST(var.text, type, val, Position.combine(start.pos(), var.pos(), val.pos))

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
            op = self.match_any_exc("<", ">", "<=", ">=", "==", "!=")
            right = self.parse_add()
            expr = CompareExprAST(op.text, expr, right, Position.combine(expr.pos, right.pos))
        return expr

    def parse_add(self):
        expr = self.parse_mul()
        while self.curr.type in ("+", "-"):
            op = self.match_any_exc("+", "-")
            right = self.parse_mul()
            expr = ArithmeticExprAST(op.text, expr, right, Position.combine(expr.pos, right.pos))
        return expr

    def parse_mul(self):
        expr = self.parse_unary()  # TODO power between this and unary
        while self.curr.type in ("*", "/", "%"):
            op = self.match_any_exc("*", "/", "%")
            right = self.parse_mul()
            expr = ArithmeticExprAST(op.text, expr, right, Position.combine(expr.pos, right.pos))
        return expr

    def parse_unary(self):
        if self.curr.type in ("-", "!", "~"):
            start = self.curr
            if self.match("-"):
                right = self.parse_unary()
                return NegExprAST(right, start.pos().to(right.pos))
            elif self.match("!"):
                right = self.parse_unary()
                return NotExprAST(right, start.pos().to(right.pos))
            elif self.match("~"):
                right = self.parse_unary()
                return InvExprAST(right, start.pos().to(right.pos))
        return self.parse_new()

    def parse_new(self):
        if self.curr.type == 'new':
            start = self.curr
            if self.match("new"):
                type = self.match_exc(Token.IDENTIFIER_TYPE)

                self.match_exc("{")
                args = []
                while not (end := self.match("}")):
                    arg = self.parse_expr()
                    args.append(arg)
                    if not self.match(","):
                        end = self.match_exc("}")
                        break
                return NewExprAST(GetVarExprAST(type.text, type.pos()), args, start.pos().to(end.pos()))
        return self.parse_call()

    def parse_call(self):
        expr = self.parse_intrinsic()
        while True:
            if start := self.match("("):
                args = []
                while not (end := self.match(")")):
                    arg = self.parse_expr()
                    args.append(arg)
                    if not self.match(","):
                        end = self.match_exc(")")
                        break
                expr = CallExprAST(expr, args, expr.pos.to(end.pos()))
            elif start := self.match("."):
                # TODO maybe also match number for tuples?
                attr = self.match_exc(Token.IDENTIFIER_TYPE)
                expr = GetAttrExprAST(expr, attr.text, expr.pos.to(attr.pos()))
            elif start := self.match("::"):
                attr = self.match_exc(Token.IDENTIFIER_TYPE)
                expr = GetStaticAttrExprAST(expr, attr.text, expr.pos.to(attr.pos()))
            else:
                break
        return expr

    def parse_intrinsic(self):
        if self.curr.type == '@':
            start = self.curr
            self.match_exc("@")
            intrinsic = self.match_exc(Token.IDENTIFIER_TYPE)
            self.match_exc("(")
            args = []
            while not (end := self.match(")")):
                arg = self.parse_expr()
                args.append(arg)
                if not self.match(","):
                    end = self.match_exc(")")
                    break
            return IntrinsicExprAST(intrinsic.text, args, Position.combine(start.pos(), end.pos()))
        return self.parse_primary()

    def parse_primary(self):
        if self.match("("):
            expr = self.parse_expr()
            self.match_exc(")")
            return expr
        elif self.curr_is(Token.DECIMAL_TYPE):
            num = self.match(Token.DECIMAL_TYPE)
            return IntLiteralAST(int(num.text), num.pos())
        elif self.curr_is(Token.STRING_TYPE):
            s = self.match(Token.STRING_TYPE)
            s_e = s.text.encode().decode("unicode-escape")
            return StrLiteralAST(s_e, s.pos())
        elif self.curr_is(Token.IDENTIFIER_TYPE):
            var = self.match(Token.IDENTIFIER_TYPE)
            return GetVarExprAST(var.text, var.pos())
        else:
            if self.report_error(f"Cannot parse '{self.curr.type}' token", self.curr):
                self.synchronize()
                assert False
            else:
                assert False
