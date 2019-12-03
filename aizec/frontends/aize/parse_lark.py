from lark import Tree, Lark, Token as LarkToken

from aizec.common.aize_ast import *
from aizec.common.interfaces import *
from aizec.common.error import *
from aizec.common import *

GRAMMAR = """
?start: file

file: top_level*

?top_level: native_import
    | import
    | func
    | class

native_import: "#nativeimport" "(" IDENT ")" IDENT ";"

import: "import" IDENT ("::" IDENT)* ";"

class: "class" type_vars IDENT parent_traits class_body
type_vars: ["<" type_var ("," type_var)* ">"]
type_var: IDENT
parent_traits: [":" type ("," type)*]
class_body: "{" class_stmt* "}"
class_stmt: attr
    | method
    
attr: "attr" IDENT ":" type ";"

method: "method"

func: "def" IDENT func_args func_ret func_body 
func_args: "(" [func_arg ("," func_arg)*] ")"
func_arg: IDENT ":" type
func_ret: "->" type
func_body: "{" stmt* "}"

?stmt: var_stmt
    | ret_stmt
    | expr_stmt
    | if_stmt
    | while_stmt
    | block_stmt

var_stmt: "var" IDENT ":" type "=" expr ";"

ret_stmt: "return" expr ";"

expr_stmt: expr ";"

if_stmt: "if" "(" expr ")" stmt ["else" stmt]

while_stmt: "while" "(" expr ")" stmt

block_stmt: "{" stmt* "}"

?expr: assign

?assign: cond
    | name "=" expr -> set_var
    | expr "." IDENT "=" expr -> set_attr

?cond: sum
    | sum "<" sum -> lt
    | sum ">" sum -> gt
    | sum "<=" sum -> le
    | sum ">=" sum -> ge
    | sum "==" sum -> eq
    | sum "!=" sum -> ne

?sum: call
    | sum "+" call -> add
    | sum "-" call -> sub

?call: primary
    | call call_args -> func_call
    | call "." IDENT -> get_attr
    
call_args: "(" [expr ("," expr)*] ")"

?primary: name -> get_var
    | DEC -> dec

?type: name -> get_type
    | type "<" type ("," type)* ">" -> generic 

?name: IDENT -> get_name
    | name "::" IDENT -> get_attr_name

IDENT: /[_a-zA-Z][_a-zA-Z0-9]*/
DEC: /[0-9]+/ 

COMMENT: /#[^\\n]*/

%import common.WS
%ignore WS
%ignore COMMENT
"""
# TODO do not require a type hint in the grammar for var_stmt
# TODO use /=/ to track location of the key tokens, so the .place points to the right place


class ParseError(AizeError):
    def __init__(self, msg: str, text: str, token: LarkToken):
        self.msg = msg
        self.token = token
        self.text = text

    def display(self, file: IO):
        line_no = self.token.line
        line = self.text.splitlines()[line_no-1]
        pos = self.token.column, self.token.end_column
        file.write(f"In {self.token.pos.file}:\n")
        file.write(f"Parsing Error: {self.msg}:\n")
        file.write(f"{line_no:>6} | {line}\n")
        file.write(f"         {' ' * pos[0]}{'^'*(pos[1]-pos[0])}")


def bin_op(op_name: str, op_cls: Cls):
    def op(self, left: Tree, right: Tree):
        return op_cls(self.visit(left), self.visit(right))
    op.__name__ = "visit_" + op_name
    return op


class ToAizeAst:
    def __init__(self, file: Path, text: str):
        self.file = file
        self.text = text
        self.imps: List[Path] = []

    @classmethod
    def convert(cls, file: Path, text: str) -> Tuple[File, List[Path]]:
        parsed = parser_lark.parse(text)
        converter = cls(file, text)
        ast = converter.visit(parsed)
        return ast, converter.imps

    def visit(self, obj: Tree):
        ret = getattr(self, "visit_" + obj.data)(*obj.children)
        if isinstance(ret, Node):
            # place it
            ret.place(self.get_place(obj))
        return ret

    def get_place(self, obj: Union[Tree, LarkToken]):
        if isinstance(obj, Tree):
            if len(obj.data) > 0:
                return self.get_place(obj.children[0])
            else:
                raise Exception()
        else:
            return TextPos(self.text, obj.line, (obj.column-1, obj.end_column-1), self.file)

    def visit_file(self, *top_levels):
        ast = []
        for top_level in top_levels:
            ast.append(self.visit(top_level))
        return File(self.file, False, ast)

    def visit_native_import(self, lang: LarkToken, mod: LarkToken):
        # TODO use 'lang'
        return NativeImport(mod.value)

    def visit_import(self, *path: LarkToken):
        if path[0] == "std":
            abs_path = (AIZE_STD / path[1]).with_suffix(".aize")
        else:
            raise Exception("Relative imports not supported yet")
        self.imps.append(abs_path)
        file_path = FilePath(path[0].value, abs_path)
        file_path.abs_path = abs_path
        return Import(file_path, path[-1])

    def visit_func(self, name: LarkToken, args: Tree, ret: Tree, body: Tree):
        ast_name = name.value
        ast_args = self.visit(args)
        ast_ret = self.visit(ret)
        ast_body = self.visit(body)
        return Function(ast_name, FuncTypeNode([ast_arg.type_ref for ast_arg in ast_args], ast_ret),
                        ast_args, ast_ret, ast_body)

    def visit_func_args(self, *args: Tree):
        return [self.visit(arg) for arg in args]

    def visit_func_arg(self, name: LarkToken, type: Tree):
        return Param(name.value, self.visit(type))

    def visit_func_ret(self, type: Tree):
        return self.visit(type)

    def visit_func_body(self, *stmts: Tree):
        return [self.visit(stmt) for stmt in stmts]

    def visit_if_stmt(self, cond: Tree, then_do: Tree, else_do: Tree = None):
        return If(self.visit(cond), self.visit(then_do), Block([]) if else_do is None else self.visit(else_do))

    def visit_while_stmt(self, cond: Tree, do: Tree):
        return While(self.visit(cond), self.visit(do))

    def visit_block_stmt(self, *stmts: Tree):
        return Block([self.visit(stmt) for stmt in stmts])

    def visit_var_stmt(self, name: LarkToken, type: Tree, expr: Tree):
        return VarDecl(name.value, self.visit(type), self.visit(expr))

    def visit_ret_stmt(self, ret: Tree):
        return Return(self.visit(ret))

    def visit_expr_stmt(self, expr: Tree):
        return ExprStmt(self.visit(expr))

    visit_lt = bin_op("lt", LT)
    visit_gt = bin_op("gt", GT)
    visit_le = bin_op("le", LE)
    visit_ge = bin_op("ge", GE)

    visit_add = bin_op("add", Add)
    visit_sub = bin_op("sub", Sub)

    def visit_func_call(self, func: Tree, call: Tree):
        return Call(self.visit(func), self.visit(call))

    def visit_call_args(self, *exprs: Tree):
        return [self.visit(expr) for expr in exprs]

    def visit_set_var(self, name: Tree, expr: Tree):
        if name.data == 'get_name':
            return SetVar(name.children[0].value, self.visit(expr))
        # elif name.data == 'get_attr_name':
        #     return GetNamespaceName(self.visit(name.children[0]), name.children[1].value)
        else:
            raise Exception(name)

    def visit_get_var(self, name: Tree):
        if name.data == 'get_name':
            return GetVar(name.children[0].value)
        elif name.data == 'get_attr_name':
            return GetNamespaceName(self.visit(name.children[0]), name.children[1].value)
        else:
            raise Exception(name)

    def visit_dec(self, num: LarkToken):
        return Num(int(num.value))

    def visit_get_type(self, name: Tree):
        if name.data == 'get_name':
            return Name(name.children[0].value)
        else:
            raise Exception(name)

    def visit_get_name(self, name: LarkToken):
        return GetNamespace(name.value)


parser_lark = Lark(GRAMMAR, parser='lalr')


class AizeLarkParser:
    def __init__(self, ast: Tree, file: Path):
        self.ast = ast
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
            text = curr.read_text()
            parsed, imps = ToAizeAst.convert(curr, text)
            files.append(parsed)
            visited.add(curr)

            to_parse.extend(imps)

        files[0].is_main = True

        return Program(files)
