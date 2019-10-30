from __future__ import annotations

import contextlib

from aizec.common.error import AizeError
from aizec.common.interfaces import AIZE_STD
from ...common.aize_ast import *
from ...common import *

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

KEYWORDS = ['class', 'def', 'method', 'attr', 'var', 'while', 'if', 'return', 'else', 'import', 'cimport']

BIN = '01'
OCT = BIN + '234567'
DEC = OCT + '89'
HEX = DEC + 'ABCDEF'
IDENT_START = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
IDENT = IDENT_START + DEC


class ScanningError(AizeError):
    def __init__(self, msg: str, scanner: Scanner):
        # TODO take a TextPos instead of a Scanner
        self.msg = msg
        self.scanner = scanner

    def display(self, file: IO):
        line_no, line = self.scanner.get_line()
        pos = self.scanner.line_pos
        file.write(f"In {self.scanner.file}:\n")
        file.write(f"Lexing Error: {self.msg}:\n")
        file.write(f"{line_no:>6} | {line}\n")
        file.write(f"         {' '*pos}^")


class ParseError(AizeError):
    def __init__(self, msg: str, token: Token):
        self.msg = msg
        self.token = token

    def display(self, file: IO):
        line_no = self.token.pos.line
        line = self.token.pos.text.splitlines()[line_no-1]
        pos = self.token.pos.pos
        file.write(f"In {self.token.pos.file}:\n")
        file.write(f"Parsing Error: {self.msg}:\n")
        file.write(f"{line_no:>6} | {line}\n")
        file.write(f"         {' ' * pos[0]}{'^'*(pos[1]-pos[0])}")


class Token:
    def __init__(self, text: str, type: str, pos: TextPos):
        self.text = text
        self.type = type
        self.pos = pos

    def __repr__(self):
        return f"Token({self.text!r}, {self.type!r}, {self.pos!r})"


class Scanner:
    def __init__(self, file: Path, text: str):
        self.file = file
        self.text = text

        self.pos = 0
        self.line_pos = 0
        self.line = 1

    @classmethod
    def scan(cls, path: Path):
        text = path.read_text()
        scanner = Scanner(path, text)

        tokens: List[Token] = []

        while not scanner.is_done():
            for basic in BASIC_TOKENS:
                token = scanner.match_token(basic)
                if token:
                    tokens += token
                    break
            else:
                if scanner.next() == "0" and scanner.next(n=1) in "x":
                    if scanner.next(n=1) == "x":
                        raise ScanningError("Cannot parse hex yet", scanner)
                elif scanner.next() in "0123456789":
                    with scanner.start_token("dec") as token:
                        while scanner.next() in "0123456789":
                            scanner.advance()
                    tokens.append(token)
                elif scanner.next() in IDENT_START:
                    with scanner.start_token("ident") as token:
                        while scanner.next() in IDENT:
                            scanner.advance()
                    if token.text in KEYWORDS:
                        token.type = token.text
                    tokens.append(token)
                elif scanner.next() == "\"":
                    with scanner.start_token("str") as token:
                        scanner.advance()
                        while scanner.next() != "\"":
                            if scanner.next() == "\\":
                                scanner.advance()
                            scanner.advance()
                        if scanner.is_done():
                            raise ScanningError("Unterminated String", scanner)
                        scanner.advance()
                    tokens.append(token)
                elif scanner.next() == "#":
                    scanner.advance()
                    if scanner.next() == " ":
                        # Comment
                        while not scanner.next() == "\n":
                            scanner.advance()
                    elif scanner.peek("nativeimport"):
                        tokens += scanner.match_token("nativeimport")
                elif scanner.next() == "\n":
                    scanner.advance_line()
                elif scanner.next() in '\t ':
                    scanner.advance(1)
                else:
                    raise ScanningError(f"Unrecognized character: {scanner.next()}", scanner)
        return tokens

    def is_done(self):
        return self.pos >= len(self.text)

    def get_line(self):
        return self.line, self.text.splitlines()[self.line-1]

    def peek(self, text: str):
        return self.text.startswith(text, self.pos)

    def next(self, n=0):
        return self.text[self.pos+n] if not self.is_done() else "\0"

    def advance(self, n=1):
        self.line_pos += n
        self.pos += n

    def advance_line(self):
        self.line_pos = 0
        self.line += 1
        self.pos += 1

    def match_token(self, text: str):
        if self.text.startswith(text, self.pos):
            start = self.line_pos
            self.advance(len(text))
            return [Token(text, text, TextPos(self.text, self.line, (start, self.line_pos), self.file))]
        return []

    @contextlib.contextmanager
    def start_token(self, type: str):
        start_pos = self.pos
        start_line_pos = self.line_pos

        token = new(Token)
        yield token

        token.text = self.text[start_pos:self.pos]
        token.type = type
        token.pos = TextPos(self.text, self.line, (start_line_pos, self.line_pos), self.file)


class AizeParser:
    def __init__(self, tokens: List[Token], file: Path):
        self.tokens = tokens
        self.file = file

        self.pos = 0

    @classmethod
    def parse(cls, file: Path):
        to_parse = [file]
        visited = set()
        files = []
        while len(to_parse) > 0:
            curr = to_parse.pop()
            if curr in visited:
                continue
            parser = cls(Scanner.scan(curr), curr)
            parsed, imps = parser.parse_file(curr)
            files.append(parsed)
            visited.add(curr)
            to_parse.extend(imp.abs_path for imp in imps)

        files[0].is_main = True

        return Program(files)

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
            raise ParseError(f"Expected '{type}', got '{self.curr.type}'", self.curr)
        return match

    def imp(self) -> FilePath:
        if self.curr_is("str"):
            loc = 'here'
            file = self.file.parent / self.match_exc("str").text[1:-1]
        else:
            loc = self.match_exc("ident").text
            self.match_exc(":")
            if loc == "std":
                file = self.match_exc("str").text[1:-1]
            else:
                raise ParseError("Location can only be 'std' currently", self.prev)
        return FilePath(loc, Path(file))

    def parse_file(self, file: Path):
        tops = []
        imps = []
        while self.pos < len(self.tokens):
            if self.curr_is("class"):
                tops.append(self.parse_class())
            elif self.curr_is("def"):
                tops.append(self.parse_function())
            elif self.curr_is("import"):
                obj, imp = self.parse_import()
                tops.append(obj)
                imps.append(imp)
            elif self.curr_is("nativeimport"):
                tops.append(self.parse_nativeimport())
            else:
                raise ParseError("Not a valid top-level", self.curr)
        return File(file, False, tops), imps

    def parse_class(self):
        start = self.match_exc("class")

        name = self.match_exc("ident").text
        # TODO inheritance, generics
        self.match_exc("{")
        attrs = {}
        methods = {}
        while not self.match("}"):
            if self.curr_is("attr"):
                attr = self.parse_attr()
                attrs[attr.name] = attr
            elif self.curr_is("method"):
                method = self.parse_method()
                methods[method.name] = method
            else:
                raise ParseError("Not a valid class-statement", self.curr)

        return Class(name, Name(name), None, attrs, methods).place(start.pos)

    def parse_attr(self):
        start = self.match("attr")
        name = self.match_exc("ident").text
        self.match_exc(":")
        type = self.parse_type()
        self.match_exc(";")
        return Attr(name, type).place(start.pos)

    def parse_method(self):
        start = self.match("method")
        name = self.match_exc("ident")
        self.match_exc("(")
        args = []
        while not self.match(")"):
            arg_name = self.match_exc("ident")
            self.match_exc(":")
            arg_type = self.parse_type()
            args.append((arg_name, arg_type))
            if not self.match(","):
                self.match_exc(")")
                break
        self.match_exc("->")
        ret = self.parse_type()
        self.match_exc("{")
        body = []
        while not self.match("}"):
            body.append(self.parse_stmt())
        return Method(name.text,
                      FuncTypeNode([arg_type for _, arg_type in args], ret),
                      [Param(arg_name.text, arg_type) for arg_name, arg_type in args], ret, body).place(start.pos)

    def parse_import(self):
        start = self.match("import")

        file = self.imp()

        if file.where == 'std':
            if str(file.rel_path) in ('io',):
                file.abs_path = (AIZE_STD / file.rel_path).with_suffix(".aize")
            else:
                raise ParseError(f"No file in the standard library called \"{file.rel_path}\"", start)
        else:
            for ext in (".aize", ):
                if file.rel_path.with_suffix(ext).exists():
                    file.abs_path = file.rel_path.absolute().with_suffix(ext)
                    break
            else:
                raise ParseError(f"No file with extension '.aize' found for \"{file}\"", start)

        self.match_exc(";")

        return Import(file, file.rel_path.with_suffix("").name).place(start.pos), file

    def parse_nativeimport(self):
        start = self.match("nativeimport")

        file = self.match_exc("ident")

        return NativeImport(file.text).place(start.pos)

    def parse_function(self):
        start = self.match("def")
        name = self.match_exc("ident")
        self.match_exc("(")
        args = []
        while not self.match(")"):
            arg_name = self.match_exc("ident")
            self.match_exc(":")
            arg_type = self.parse_type()
            args.append((arg_name, arg_type))
            if not self.match(","):
                self.match_exc(")")
                break
        self.match_exc("->")
        ret = self.parse_type()
        self.match_exc("{")
        body = []
        while not self.match("}"):
            body.append(self.parse_stmt())
        return Function(name.text,
                        FuncTypeNode([arg_type for _, arg_type in args], ret),
                        [Param(arg_name.text, arg_type) for arg_name, arg_type in args], ret, body).place(start.pos)

    def parse_type(self):
        return self.parse_name()

    def parse_name(self):
        ident = self.match_exc("ident")
        return Name(ident.text).place(ident.pos)

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
            else_body = Block([])
        return If(cond, body, else_body).place(start.pos)

    def parse_while(self):
        start = self.match("while")
        self.match_exc("(")
        cond = self.parse_expr()
        self.match_exc(")")
        body = self.parse_stmt()
        return While(cond, body).place(start.pos)

    def parse_block(self):
        start = self.match_exc("{")
        body = []
        while not self.match("}"):
            body.append(self.parse_stmt())
        return Block(body).place(start.pos)

    def parse_var(self):
        start = self.match("var")
        var = self.match_exc("ident").text
        self.match_exc(":")
        type = self.parse_type()
        self.match_exc("=")
        val = self.parse_expr()
        self.match_exc(";")
        return VarDecl(var, type, val).place(start.pos)

    def parse_return(self):
        start = self.match_exc("return")
        expr = self.parse_expr()
        self.match_exc(";")
        return Return(expr).place(start.pos)

    def parse_expr_stmt(self):
        start = self.curr
        expr = self.parse_expr()
        self.match_exc(";")
        return ExprStmt(expr).place(start.pos)

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
                    expr = GetNamespaceName(GetNamespace(expr.name).place(expr.pos), attr.text).place(start.pos)
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

