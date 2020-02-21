from __future__ import annotations

import contextlib

from aizec.aize_ast import *
from aizec.common import *
from aizec.aize_error import AizeError


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


class ParseError(AizeError):
    def __init__(self, msg: str, token: Token, in_source: Source):
        self.msg = msg
        self.token = token
        self.in_source = in_source

    def display(self, file: IO):
        file.write(f"In {self.in_source.get_name()}:\n")
        file.write(f"Parsing Error: {self.msg}:\n")
        file.write(self.token.in_context())


class Token:
    def __init__(self, text: str, type: str, source: Source, line_no: int, columns: Tuple[int, int]):
        self.text = text
        self.type = type

        self.source = source
        self.line_no = line_no
        self.columns = columns

    def in_context(self) -> str:
        return f"{self.line_no:>6} | {self.source.lines[self.line_no-1]}\n" \
               f"         {' ' * self.columns[0]}{'^'*(self.columns[1]-self.columns[0])}"

    def __repr__(self):
        return f"Token({self.text!r}, {self.type!r})"


class Scanner:
    def __init__(self, source: Source):
        self.source = source
        self.text = source.text

        self.pos = 0
        self.line_pos = 0
        self.line_no = 1

    @classmethod
    def scan_source(cls, source: Source) -> List[Token]:
        return list(Scanner(source).iter_tokens())

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

    def match_token(self, text: str) -> Token:
        if self.text.startswith(text, self.pos):
            start = self.line_pos
            self.advance(len(text))
            return Token(text, text, self.source, self.line_no, (start, start+len(text)))
        else:
            # TODO ERROR REPORTING
            assert False

    @contextlib.contextmanager
    def start_token(self, type: str):
        start_pos = self.pos
        start_line_no = self.line_no
        start_line_pos = self.line_pos

        token = Token.__new__(Token)
        yield token

        token.__init__(self.text[start_pos:self.pos], type, self.source, start_line_no, (start_line_pos, self.line_pos))
    # endregion


class NodePosition(PassData):
    def __init__(self, token: Token):
        super().__init__()
        self.token = token


class AizeParser:
    def __init__(self, tokens: List[Token], source: Source):
        self.tokens = tokens
        self.source = source

        self.pos = 0

    @classmethod
    def parse(cls, sources: List[Source], project_dir: Path, std_dir: Path, recurse=True):
        to_parse: List[Source] = sources.copy()
        visited: Set = set()
        parsed_sources: List[Source] = []

        while len(to_parse) > 0:
            curr_source: Source = to_parse.pop()
            if curr_source.get_unique() in visited:
                continue

            parser = cls(Scanner.scan_source(curr_source), curr_source)
            parsed = parser.parse_source(curr_source)

            parsed_sources.append(parsed)
            visited.add(parsed.get_unique())

            if recurse:
                for import_node in parsed.imports:
                    if import_node.anchor == 'std':
                        abs_path = std_dir / import_node.path
                    elif import_node.anchor == 'project':
                        abs_path = project_dir / import_node.path
                    elif import_node.anchor == 'local':
                        parsed_file = parsed.get_path()
                        if parsed_file is None:
                            raise ParseError("Cannot do a local import on a non-file source.",
                                             NodePosition.of(import_node).token, parsed)
                        else:
                            abs_path = parsed_file.parent / import_node.path
                    else:
                        raise Exception("Invalid anchor")
                    to_parse.append(FileSource(abs_path, abs_path.read_text(), False, []))

        return Program(parsed_sources)

    # region utility methods
    @property
    def curr(self):
        return self.tokens[self.pos]

    @property
    def prev(self):
        return self.tokens[self.pos-1]

    def curr_is(self, type: str):
        return self.curr.type == type

    def match(self, type: str):
        if self.curr_is(type):
            curr = self.curr
            self.pos += 1
            return curr
        else:
            return None

    def match_exc(self, type: str):
        match = self.match(type)
        if not match:
            raise ParseError(f"Expected '{type}', got '{self.curr.type}'", self.curr, self.source)
        return match
    # endregion

    def parse_source(self, source: Source) -> Source:
        while self.pos < len(self.tokens):
            if self.curr_is("class"):
                source.top_levels.append(self.parse_class())
            elif self.curr_is("trait"):
                source.top_levels.append(self.parse_trait())
            elif self.curr_is("def"):
                source.top_levels.append(self.parse_function())
            elif self.curr_is("import"):
                source.top_levels.append(self.parse_import())
            else:
                # TODO ERROR HANDLING
                raise ParseError("Not a valid top-level", self.curr, self.source)
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
            if self.curr_is("attr"):
                body.append(self.parse_attr())
            elif self.curr_is("method"):
                body.append(self.parse_method())
            else:
                raise ParseError("Not a valid class-statement", self.curr, self.source)

        return Class(name, traits, body).add_data(NodePosition(start))

    def parse_trait(self):
        start = self.match_exc("trait")

        name = self.match_exc("ident").text

        self.match_exc("{")
        body = []
        while not self.match("}"):
            if self.curr_is("method"):
                body.append(self.parse_method())
            elif self.curr_is("attr"):
                raise ParseError("Traits cannot have attributes", self.curr, self.source)
            else:
                raise ParseError("Not a valid trait-statement", self.curr, self.source)

        return Trait(name, [], body).add_data(NodePosition(start))

    def parse_attr(self):
        start = self.match("attr")
        name = self.match_exc("ident").text
        self.match_exc(":")
        type = self.parse_type()
        self.match_exc(";")
        return Attr(name, type).add_data(NodePosition(start))

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
                    raise ParseError("Only the first argument to a method does not require a type annotation", self.curr, self.source)
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
        params = [Param(arg_name.text, arg_type).add_data(NodePosition(arg_name)) for arg_name, arg_type in args]
        if self.match("{"):
            body = []
            while not self.match("}"):
                body.append(self.parse_stmt())
            return MethodImpl(name, params, ret, body).add_data(NodePosition(start))
        else:
            self.match_exc(";")
            return Method(name, params, ret).add_data(NodePosition(start))

    def parse_import(self) -> Import:
        start = self.match("import")

        path = Path(self.match_exc("str").text)
        if len(path.parts) > 0:
            first_part = path.parts[0]
            if first_part.startswith("<") and first_part.endswith(">"):
                anchor = first_part[1:-1]
                if anchor not in ("std", "anchor", "local"):
                    raise ParseError("Anchor must be one of std, anchor, or local", start, self.source)
                path = Path("").joinpath(*path.parts[1:])
            else:
                anchor = '<project>'
        else:
            anchor = '<project>'

        self.match_exc(";")

        return Import(anchor, path).add_data(NodePosition(start))

    def parse_function(self):
        start = self.match("def")
        name = self.match_exc("ident")
        self.match_exc("(")
        params = []
        while not self.match(")"):
            arg_name = self.match_exc("ident")
            self.match_exc(":")
            arg_type = self.parse_type()
            params.append(Param(arg_name.text, arg_type).add_data(NodePosition(arg_name)))
            if not self.match(","):
                self.match_exc(")")
                break
        self.match_exc("->")
        ret = self.parse_type()
        self.match_exc("{")
        body = []
        while not self.match("}"):
            body.append(self.parse_stmt())

        return Function(name.text, params, ret, body).add_data(NodePosition(start))

    def parse_type(self) -> TypeAnnotation:
        return self.parse_name()

    def parse_name(self) -> GetTypeAnnotation:
        ident = self.match_exc("ident")
        return GetTypeAnnotation(ident.text).add_data(NodePosition(ident))

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
            else_body = BlockStatement([])
        return IfStatement(cond, body, else_body).add_data(NodePosition(start))

    def parse_while(self):
        start = self.match("while")
        self.match_exc("(")
        cond = self.parse_expr()
        self.match_exc(")")
        body = self.parse_stmt()
        return WhileStatement(cond, body).add_data(NodePosition(start))

    def parse_block(self):
        start = self.match_exc("{")
        body = []
        while not self.match("}"):
            body.append(self.parse_stmt())
        return BlockStatement(body).add_data(NodePosition(start))

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
        return VarDeclStatement(var, type, val).add_data(NodePosition(start))

    def parse_return(self):
        start = self.match_exc("return")
        expr = self.parse_expr()
        self.match_exc(";")
        return ReturnStatement(expr).add_data(NodePosition(start))

    def parse_expr_stmt(self):
        start = self.curr
        expr = self.parse_expr()
        self.match_exc(";")
        return ExpressionStatement(expr).add_data(NodePosition(start))

    def parse_expr(self):
        return self.parse_assign()

    def parse_assign(self):
        expr = self.parse_logic()
        if self.match("="):
            start = self.prev
            right = self.parse_assign()
            if isinstance(expr, GetVar):
                expr = SetVar(expr.name, right).place(start.pos)
            elif isinstance(expr, GetAttr):
                expr = SetAttr(expr.left, expr.attr, right).place(start.pos)
            else:
                raise ParseError("Not a valid assignment target", start)
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
                expr = LT(expr, right).place(start.pos)
            elif self.curr.type == ">":
                self.match(">")
                right = self.parse_add()
                expr = GT(expr, right).place(start.pos)
            elif self.curr.type == "<=":
                self.match("<=")
                right = self.parse_add()
                expr = LE(expr, right).place(start.pos)
            elif self.curr.type == ">=":
                self.match(">=")
                right = self.parse_add()
                expr = GE(expr, right).place(start.pos)
            elif self.curr.type == "==":
                self.match("==")
                right = self.parse_add()
                expr = EQ(expr, right).place(start.pos)
            elif self.curr.type == "!=":
                self.match("!=")
                right = self.parse_add()
                expr = NE(expr, right).place(start.pos)
        return expr

    def parse_add(self):
        expr = self.parse_mult()
        while self.curr.type in ("+", "-"):
            start = self.curr
            if self.curr.type == "+":
                self.match("+")
                right = self.parse_mult()
                expr = Add(expr, right).place(start.pos)
            elif self.curr.type == "-":
                self.match("-")
                right = self.parse_mult()
                expr = Sub(expr, right).place(start.pos)
        return expr

    def parse_mult(self):
        expr = self.parse_unary()  # TODO power between this and unary
        while self.curr.type in ("*", "/", "%"):
            start = self.curr
            if self.curr.type == "*":
                self.match("*")
                right = self.parse_unary()
                expr = Mul(expr, right).place(start.pos)
            elif self.curr.type == "/":
                self.match("/")
                right = self.parse_unary()
                expr = Div(expr, right).place(start.pos)
            # elif self.curr.type == "//":
            #     self.match("//")
            #     right = self.parse_unary()
            #     expr = FloorDiv(expr, right)
            elif self.curr.type == "%":
                self.match("%")
                right = self.parse_unary()
                expr = Mod(expr, right).place(start.pos)
        return expr

    def parse_unary(self):
        if self.curr.type in ("-", "!", "~"):
            start = self.curr
            if self.match("-"):
                right = self.parse_unary()
                return Neg(right).place(start.pos)
            elif self.match("!"):
                right = self.parse_unary()
                return Not(right).place(start.pos)
            elif self.match("~"):
                right = self.parse_unary()
                return Inv(right).place(start.pos)
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
                expr = Call(expr, args).place(start.pos)
            elif self.match("."):
                start = self.prev
                # TODO maybe also match number for tuples?
                attr = self.match_exc("ident")
                expr = GetAttr(expr, attr.text).place(start.pos)
            elif self.match("::"):
                start = self.prev
                attr = self.match_exc("ident")
                if isinstance(expr, GetVar):
                    expr = GetNamespaceExpr(GetNamespace(expr.name).place(expr.pos), attr.text).place(start.pos)
                else:
                    raise ParseError("Cannot get an attribute from the left", start)
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
            return Num(int(num.text)).place(self.prev.pos)
        elif self.curr_is("str"):
            s = self.match("str")
            s_e = s.text.encode().decode("unicode-escape")
            return Str(s_e).place(self.prev.pos)
        elif self.curr_is("ident"):
            var = self.match("ident")
            return GetVar(var.text).place(self.prev.pos)
        else:
            raise ParseError(f"Cannot parse '{self.curr.type}' token", self.curr)
