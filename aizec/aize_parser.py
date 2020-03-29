from __future__ import annotations

import contextlib

from aizec.aize_ast import *
from aizec.common import *
from aizec.aize_pass_data import PositionData
from aizec.aize_error import AizeMessage, ErrorHandler

BASIC_TOKENS = sorted(["+", "+=",
                       "-", "-=", "->",
                       "/", "//", "/=", "//=",
                       "*", "**", "*=", "**=",
                       "%", "%=",
                       "^", "^=", "|", "|=", "&", "&=",
                       "!", "~",
                       "==", "!=", "<", "<=", ">", ">=",
                       "(", ")", "[", "]", "{", "}",
                       "=", ",", ".", ":", ";",
                       "@", "::"],
                      key=len, reverse=True)

KEYWORDS = ['class', 'trait', 'def', 'method', 'attr', 'var', 'while', 'if', 'return', 'else', 'import']

BIN = '01'
OCT = BIN + '234567'
DEC = OCT + '89'
HEX = DEC + 'ABCDEF'
IDENT_START = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
IDENT = IDENT_START + DEC


class ParseError(AizeMessage):
    def __init__(self, msg: str, pos: PositionData, in_source: Source):
        super().__init__(self.ERROR)

        self.msg = msg
        self.pos = pos
        self.in_source = in_source

    def display(self, reporter):
        reporter.positioned_error(type="Parsing Error", source=self.in_source.get_name(), msg=self.msg, pos=self.pos)


class Token:
    def __init__(self, text: str, type: str, source: Source, line_no: int, columns: Tuple[int, int]):
        self.text = text
        self.type = type

        self.source = source
        self.line_no = line_no
        self.columns = columns

    def pos(self) -> PositionData:
        return PositionData(self.source, self.line_no, self.columns)

    def __repr__(self):
        return f"Token({self.text!r}, {self.type!r})"


class Scanner:
    def __init__(self, source: Source, error_handler: ErrorHandler):
        self.source = source
        self.text = source.text

        self.pos = 0
        self.line_pos = 0
        self.line_no = 1

        self.error_handler = error_handler

    @classmethod
    def scan_source(cls, source: Source, error_handler: ErrorHandler) -> List[Token]:
        return list(Scanner(source, error_handler).iter_tokens())

    def iter_tokens(self) -> Iterator[Token]:
        while not self.is_done():
            next_token = self.scan_next()
            if next_token is not None:
                yield next_token

    def scan_next(self) -> Union[Token, None]:
        for basic in BASIC_TOKENS:
            token = self.match_token(basic)
            if token:
                return token
        else:
            if self.next() == "0" and self.next(plus=1) in "x":
                if self.next(plus=1) == "x":
                    # TODO ERROR REPORTING
                    assert False
            elif self.next() in "0123456789":
                with self.start_token("dec") as token:
                    while self.next() in "0123456789":
                        self.advance()
                return token
            elif self.next() in IDENT_START:
                with self.start_token("ident") as token:
                    while self.next() in IDENT:
                        self.advance()
                if token.text in KEYWORDS:
                    token.type = token.text
                return token
            elif self.next() == "\"":
                with self.start_token("str") as token:
                    self.advance()
                    while self.next() != "\"":
                        if self.next() == "\\":
                            self.advance()
                        if self.next() == "\n":
                            # TODO ERROR REPORTING
                            assert False
                        self.advance()
                    if self.is_done():
                        # TODO ERROR REPORTING
                        assert False
                    self.advance()
                return token
            elif self.next() == "#":
                self.advance()
                if self.next() == " ":
                    while not self.next() == "\n":
                        self.advance()
                return None
            elif self.next() == "\n":
                self.advance_line()
                return None
            elif self.next() in '\t ':
                self.advance(1)
                return None
            else:
                # TODO ERROR REPORTING
                assert False

    # region utility methods
    def is_done(self):
        return self.pos >= len(self.text)

    def get_line(self):
        return self.line_no, self.text.splitlines()[self.line_no - 1]

    def peek(self, text: str):
        return self.text.startswith(text, self.pos)

    def next(self, plus=0):
        return self.text[self.pos + plus] if not self.is_done() else "\0"

    def advance(self, n=1):
        self.line_pos += n
        self.pos += n

    def advance_line(self):
        self.line_pos = 0
        self.line_no += 1
        self.pos += 1

    def match_token(self, text: str) -> Union[Token, None]:
        if self.text.startswith(text, self.pos):
            start = self.line_pos
            self.advance(len(text))
            return Token(text, text, self.source, self.line_no, (start, start+len(text)))
        else:
            return None

    @contextlib.contextmanager
    def start_token(self, type: str):
        start_pos = self.pos
        start_line_no = self.line_no
        start_line_pos = self.line_pos

        token = Token.__new__(Token)
        yield token

        token.__init__(self.text[start_pos:self.pos], type, self.source, start_line_no, (start_line_pos, self.line_pos))
    # endregion


class SyncFlag(Exception):
    def __init__(self, flag: int):
        self.flag = flag


class SyncPosition:
    def __init__(self):
        self.have_synced = False


class AizeParser:
    def __init__(self, tokens: List[Token], source: Source, error_handler: ErrorHandler):
        self.tokens = tokens
        self.source = source

        self.pos = 0

        self.error_handler = error_handler

        self.sync_targets = []

    @classmethod
    def parse(cls, source: Source, error_handler: ErrorHandler):
        parser = cls(Scanner.scan_source(source, error_handler), source, error_handler)
        parsed = parser.parse_source(source)
        return parsed

    # region utility methods
    @property
    def curr(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token('','\0', self.source, -1, (0, 0))

    @property
    def prev(self):
        return self.tokens[self.pos-1]

    def curr_is(self, type: str):
        return self.curr.type == type

    def is_done(self):
        return self.pos >= len(self.tokens)

    def match(self, type: str):
        if self.curr_is(type):
            return self.advance()
        else:
            return None

    def advance(self):
        curr = self.curr
        self.pos += 1
        return curr

    def match_exc(self, type: str):
        match = self.match(type)
        if not match:
            if self.report_error(f"Expected '{type}', got '{self.curr.type}'", self.curr):
                self.synchronize()
            else:
                assert False
        return match

    def report_error(self, msg: str, pos: Union[Token, Node, PositionData], is_fatal: bool = False):
        if isinstance(pos, Token):
            pos = pos.pos()
        elif isinstance(pos, Node):
            pos = PositionData.of(pos)
        self.source.has_errors = True
        self.error_handler.handle_message(ParseError(msg, pos, self.source))
        if is_fatal:
            self.error_handler.flush_errors()
            return False
        else:
            return True

    def synchronize(self):
        while self.pos < len(self.tokens):
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

    def parse_source(self, source: Source) -> Source:
        try:
            while self.pos < len(self.tokens):
                with self.sync_point("class", "trait", "def", "import"):
                    if self.curr_is("class"):
                        source.top_levels.append(self.parse_class())
                    elif self.curr_is("trait"):
                        source.top_levels.append(self.parse_trait())
                    elif self.curr_is("def"):
                        source.top_levels.append(self.parse_function())
                    elif self.curr_is("import"):
                        source.top_levels.append(self.parse_import())
                    else:
                        if self.report_error("Expected one of 'class', 'trait', 'def', or 'import'", self.curr):
                            self.synchronize()
                        else:
                            assert False
        except SyncFlag as flag:
            if flag.flag == -1:
                pass
            else:
                raise ValueError(f"flag reached top without being caught {flag.flag}")
        finally:
            self.error_handler.flush_errors()
        return source

    def parse_class(self):
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

        return Class(name, traits, body).add_data(start.pos())

    def parse_trait(self):
        start = self.match_exc("trait")

        name = self.match_exc("ident").text

        self.match_exc("{")
        body = []
        while not self.match("}"):
            with self.sync_point("method", "attr"):
                if self.curr_is("method"):
                    body.append(self.parse_method())
                elif self.curr_is("attr"):
                    if self.report_error("Traits cannot have attributes", self.curr):
                        self.synchronize()
                        assert False
                    else:
                        assert False
                else:
                    if self.report_error("Trait body statements must start with 'method'", self.curr):
                        self.synchronize()
                        assert False
                    else:
                        assert False

        return Trait(name, [], body).add_data(start.pos())

    def parse_attr(self):
        start = self.match("attr")
        name = self.match_exc("ident").text
        self.match_exc(":")
        type = self.parse_type()
        self.match_exc(";")
        return Attr(name, type).add_data(start.pos())

    def parse_method_sig(self) -> Tuple[Token, str, List[Tuple[Token, TypeAnnotation]], TypeAnnotation]:
        start = self.match("method")
        name = self.match_exc("ident").text
        self.match_exc("(")
        args = []
        while not self.match(")"):
            arg_name = self.match_exc("ident")
            if not self.match(":"):
                if len(args) == 0:
                    arg_type = None
                else:
                    if self.report_error("Type annotation expected", self.curr):
                        self.synchronize()
                        assert False
                    else:
                        assert False
            else:
                arg_type = self.parse_type()
            args.append((arg_name, arg_type))
            if not self.match(","):
                self.match_exc(")")
                break
        if self.match("->"):
            ret = self.parse_type()
        else:
            ret = None
        return start, name, args, ret

    def parse_method(self):
        start, name, args, ret = self.parse_method_sig()
        params = [Param(arg_name.text, arg_type).add_data(arg_name.pos()) for arg_name, arg_type in args]
        if self.match("{"):
            body = []
            while not self.match("}"):
                body.append(self.parse_stmt())
            return MethodImpl(name, params, ret, body).add_data(start.pos())
        else:
            self.match_exc(";")
            return Method(name, params, ret).add_data(start.pos())

    def parse_import(self) -> Import:
        start = self.match("import")

        import_str = self.match_exc("str")
        path = Path(import_str.text[1:-1])
        if len(path.parts) > 0:
            first_part = path.parts[0]
            if first_part.startswith("<") and first_part.endswith(">"):
                anchor = first_part[1:-1]
                if anchor not in ("std", "project", "local"):
                    if self.report_error("Anchor must be one of <std>, <project>, or <local>", import_str.pos().subpos(1, 3+len(anchor))):
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

        return Import(anchor, path).add_data(start.pos().to(end.pos()))

    def parse_function(self):
        start = self.match("def")
        name = self.match_exc("ident")
        self.match_exc("(")
        params = []
        while not self.match(")"):
            arg_name = self.match_exc("ident")
            self.match_exc(":")
            arg_type = self.parse_type()
            params.append(Param(arg_name.text, arg_type).add_data(arg_name.pos()))
            if not self.match(","):
                self.match_exc(")")
                break
        if self.match("->"):
            ret = self.parse_type()
        else:
            ret = None
        self.match_exc("{")

        body = []
        with self.sync_point():
            while not self.curr_is("}") and not self.is_done():
                body.append(self.parse_stmt())
        self.match_exc("}")

        return Function(name.text, params, ret, body).add_data(start.pos())

    def parse_type(self) -> TypeAnnotation:
        return self.parse_name()

    def parse_name(self) -> GetTypeAnnotation:
        ident = self.match_exc("ident")
        return GetTypeAnnotation(ident.text).add_data(ident.pos())

    def parse_stmt(self):
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

    def parse_if(self):
        start = self.match("if")
        self.match_exc("(")
        cond = self.parse_expr()
        self.match_exc(")")
        body = self.parse_stmt()
        if self.match("else"):
            else_body = self.parse_stmt()
        else:
            else_body = BlockStmt([])
        return IfStmt(cond, body, else_body).add_data(start.pos())

    def parse_while(self):
        start = self.match("while")
        self.match_exc("(")
        cond = self.parse_expr()
        self.match_exc(")")
        body = self.parse_stmt()
        return WhileStmt(cond, body).add_data(start.pos())

    def parse_block(self):
        start = self.match_exc("{")
        body = []
        while not self.match("}"):
            body.append(self.parse_stmt())
        return BlockStmt(body).add_data(start.pos())

    def parse_var(self):
        start = self.match("var")
        var = self.match_exc("ident").text
        if self.match(":"):
            type = self.parse_type()
        else:
            type = None
        self.match_exc("=")
        val = self.parse_expr()
        self.match_exc(";")
        return VarDeclStmt(var, type, val).add_data(start.pos())

    def parse_return(self):
        start = self.match_exc("return")
        expr = self.parse_expr()
        self.match_exc(";")
        return ReturnStmt(expr).add_data(start.pos())

    def parse_expr_stmt(self):
        start = self.curr
        expr = self.parse_expr()
        self.match_exc(";")
        return ExprStmt(expr).add_data(start.pos())

    def parse_expr(self):
        return self.parse_assign()

    def parse_assign(self):
        expr = self.parse_logic()
        if self.match("="):
            start = self.prev
            right: Expr = self.parse_assign()
            if isinstance(expr, GetVarExpr):
                expr = SetVarExpr(expr.var, right).add_data(start.pos())
            elif isinstance(expr, GetAttrExpr):
                expr = SetAttrExpr(expr.obj, expr.attr, right).add_data(start.pos())
            else:
                if self.report_error("Assignment targets must be a variable or attribute", right):
                    self.synchronize()
                    assert False
                else:
                    assert False
        return expr

    def parse_logic(self):
        # TODO and/or
        return self.parse_cmp()

    def parse_cmp(self):
        expr = self.parse_add()
        while self.curr.type in ("<", ">"):
            start = self.curr
            if self.curr.type == "<":
                self.match("<")
                right = self.parse_add()
                expr = LTExpr(expr, right).add_data(start.pos())
            elif self.curr.type == ">":
                self.match(">")
                right = self.parse_add()
                expr = GTExpr(expr, right).add_data(start.pos())
            elif self.curr.type == "<=":
                self.match("<=")
                right = self.parse_add()
                expr = LEExpr(expr, right).add_data(start.pos())
            elif self.curr.type == ">=":
                self.match(">=")
                right = self.parse_add()
                expr = GEExpr(expr, right).add_data(start.pos())
            elif self.curr.type == "==":
                self.match("==")
                right = self.parse_add()
                expr = EQExpr(expr, right).add_data(start.pos())
            elif self.curr.type == "!=":
                self.match("!=")
                right = self.parse_add()
                expr = NEExpr(expr, right).add_data(start.pos())
        return expr

    def parse_add(self):
        expr = self.parse_mul()
        while self.curr.type in ("+", "-"):
            start = self.curr
            if self.curr.type == "+":
                self.match("+")
                right = self.parse_mul()
                expr = AddExpr(expr, right).add_data(start.pos())
            elif self.curr.type == "-":
                self.match("-")
                right = self.parse_mul()
                expr = SubExpr(expr, right).add_data(start.pos())
        return expr

    def parse_mul(self):
        expr = self.parse_unary()  # TODO power between this and unary
        while self.curr.type in ("*", "/", "%"):
            start = self.curr
            if self.curr.type == "*":
                self.match("*")
                right = self.parse_unary()
                expr = MulExpr(expr, right).add_data(start.pos())
            elif self.curr.type == "/":
                self.match("/")
                right = self.parse_unary()
                expr = DivExpr(expr, right).add_data(start.pos())
            # elif self.curr.type == "//":
            #     self.match("//")
            #     right = self.parse_unary()
            #     expr = FloorDiv(expr, right)
            elif self.curr.type == "%":
                self.match("%")
                right = self.parse_unary()
                expr = ModExpr(expr, right).add_data(start.pos())
        return expr

    def parse_unary(self):
        if self.curr.type in ("-", "!", "~"):
            start = self.curr
            if self.match("-"):
                right = self.parse_unary()
                return NegExpr(right).add_data(start.pos())
            elif self.match("!"):
                right = self.parse_unary()
                return NotExpr(right).add_data(start.pos())
            elif self.match("~"):
                right = self.parse_unary()
                return InvExpr(right).add_data(start.pos())
        return self.parse_call()

    def parse_call(self):
        expr = self.parse_primary()
        while True:
            if self.match("("):
                start = self.prev
                args = []
                while not self.match(")"):
                    arg = self.parse_expr()
                    args.append(arg)
                    if not self.match(","):
                        self.match_exc(")")
                        break
                expr = CallExpr(expr, args).add_data(start.pos())
            elif self.match("."):
                start = self.prev
                # TODO maybe also match number for tuples?
                attr = self.match_exc("ident")
                expr = GetAttrExpr(expr, attr.text).add_data(start.pos())
            # TODO Namespaces (generic)
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
            return IntLiteral(int(num.text)).add_data(num.pos())
        elif self.curr_is("str"):
            s = self.match("str")
            s_e = s.text.encode().decode("unicode-escape")
            return StrLiteral(s_e).add_data(s.pos())
        elif self.curr_is("ident"):
            var = self.match("ident")
            return GetVarExpr(var.text).add_data(var.pos())
        else:
            if self.report_error(f"Cannot parse '{self.curr.type}' token", self.curr):
                assert False
            else:
                assert False
