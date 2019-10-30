from __future__ import annotations

import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Dict, IO, ClassVar, cast, Iterable, Union


class Node(ABC):
    pass


# region expressions
@dataclass()
class Expression(Node, ABC):
    def __str__(self):
        return self.generate()

    @abstractmethod
    def generate(self):
        return self.generate()


@dataclass()
class SetVar(Expression):
    var: str
    val: Expression

    def generate(self):
        return f"({self.var} = {self.val.generate()})"


@dataclass()
class SetArrow(Expression):
    struct_p: Expression
    attr: str
    val: Expression

    def generate(self):
        return f"({self.struct_p.generate()}->{self.attr} = {self.val.generate()})"


@dataclass()
class SetAttr(Expression):
    struct: Expression
    attr: str
    val: Expression

    def generate(self):
        return f"({self.struct.generate()}.{self.attr} = {self.val.generate()})"


@dataclass()
class BinOp(Expression):
    left: Expression
    op: str
    right: Expression

    def generate(self):
        return f"({self.left.generate()} {self.op} {self.right.generate()})"


@dataclass()
class GetVar(Expression):
    var: str

    def generate(self):
        return self.var


@dataclass()
class GetArrow(Expression):
    struct_p: Expression
    attr: str

    def generate(self):
        return f"{self.struct_p.generate()}->{self.attr}"


@dataclass()
class GetItem(Expression):
    array_p: Expression
    item: int

    def generate(self):
        return f"{self.array_p.generate()}[{self.item}]"


@dataclass()
class GetAttr(Expression):
    struct: Expression
    attr: str

    def generate(self):
        return f"{self.struct.generate()}.{self.attr}"


@dataclass()
class Call(Expression):
    func: Expression
    args: List[Expression]

    def generate(self):
        return f"{self.func.generate()}({', '.join(map(Expression.generate, self.args))})"


@dataclass()
class SizeOf(Expression):
    type: Type

    def generate(self):
        return f"sizeof({self.type.as_type()})"


@dataclass()
class Ref(Expression):
    obj: Expression

    def generate(self):
        return f"(&{self.obj.generate()})"


@dataclass()
class Deref(Expression):
    obj_ptr: Expression

    def generate(self):
        return f"(*{self.obj_ptr.generate()})"


@dataclass()
class Cast(Expression):
    obj: Expression
    typ: Type

    def generate(self):
        return f"(({self.typ.as_type()}) {self.obj.generate()})"


@dataclass()
class Constant(Expression):
    val: Any

    def generate(self):
        if isinstance(self.val, int):
            return str(self.val)
        elif isinstance(self.val, str):
            return '"' + str(self.val) + '"'
        elif self.val is None:
            return "NULL"
        else:
            raise Exception(self.val)


@dataclass()
class ArrayInit(Expression):
    items: List[Expression]

    def generate(self):
        return f"{{ {', '.join(item.generate() for item in self.items)} }}"


@dataclass()
class StrExpr(Expression):
    s: str

    def format(self, *args, **kwargs):
        return StrExpr(self.s.format(*args, **kwargs))

    def generate(self):
        return self.s
# endregion


# region types
@dataclass()
class Type(Node, ABC):
    def __str__(self):
        return self.as_type(0)

    @abstractmethod
    def as_type(self, ptrs=0):
        pass

    @abstractmethod
    def as_func_ret(self, name: str, ptrs=0):
        pass

    @abstractmethod
    def as_func_ret_def(self, name: str, func_args: Dict[str, Type], ptrs=0):
        pass

    @abstractmethod
    def with_name(self, name: str, ptrs=0) -> str:
        pass


@dataclass()
class DataType(Type):
    typ: ClassVar[str]

    def as_type(self, ptrs=0):
        return self.typ + "*"*ptrs

    def as_func_ret(self, name: str, ptrs=0):
        if ptrs == 0:
            return self.typ + " " + name
        else:
            return self.typ + " (" + "*"*ptrs + name + ")"

    def as_func_ret_def(self, name: str, func_args: Dict[str, Type], ptrs=0):
        if '' in func_args:
            args = ", ".join(typ.with_name('') for typ in cast(Iterable[Type], func_args['']))
        else:
            args = ", ".join(typ.with_name(arg_name) for arg_name, typ in func_args.items())
        if ptrs == 0:
            return self.typ + " " + name + "(" + args + ")"
        else:
            return self.typ + "*" * ptrs + " " + name + "(" + args + ")"

    def with_name(self, name: str, ptrs=0) -> str:
        return self.typ + "*"*ptrs + " " + name


@dataclass()
class VoidType(DataType):
    typ = "void"


@dataclass()
class IntType(DataType):
    typ = "int32_t"


@dataclass()
class LongType(DataType):
    typ = "int64_t"


@dataclass()
class BoolType(DataType):
    typ = "bool"


@dataclass()
class CharType(DataType):
    typ = "char"


@dataclass()
class PointerType(Type):
    pointee: Type

    def as_type(self, ptrs=0):
        return self.pointee.as_type(ptrs+1)

    def as_func_ret(self, name: str, ptrs=0):
        return self.pointee.as_func_ret(name, ptrs+1)

    def as_func_ret_def(self, name: str, func_args: Dict[str, Type], ptrs=0):
        return self.pointee.as_func_ret_def(name, func_args, ptrs+1)

    def with_name(self, name: str, ptrs=0) -> str:
        return self.pointee.with_name(name, ptrs+1)


@dataclass()
class FunctionType(Type):
    args: List[Type]
    ret: Type

    def as_type(self, ptrs=0):
        return f"{self.ret.as_type(ptrs)} (*)({', '.join(arg.as_type() for arg in self.args)})"

    def as_func_ret(self, name: str, ptrs=0):
        func_args = {'': self.args}
        # noinspection PyTypeChecker
        return f"{self.ret.as_func_ret_def(name, func_args, ptrs)}"

    def as_func_ret_def(self, name: str, func_args: Dict[str, Type], ptrs=0):
        args = ', '.join(arg.as_type() for arg in self.args)
        return f"{self.ret.as_func_ret_def(name, func_args, ptrs)}({args})"

    def with_name(self, name: str, ptrs=0) -> str:
        return f"{self.ret.as_func_ret(name, ptrs)}({', '.join(arg.as_type() for arg in self.args)})"


@dataclass()
class StructType(DataType):
    name: str

    @property
    def typ(self):
        return "struct " + self.name


@dataclass()
class NameType(DataType):
    name: str

    @property
    def typ(self):
        return self.name
# endregion


# region statements
@dataclass()
class Statement(Node):
    @abstractmethod
    def generate(self, indent=0):
        pass


@dataclass()
class Declare(Statement):
    typ: Type
    name: str
    val: Union[Expression, None]

    def generate(self, indent=0):
        if self.val is None:
            return "    "*indent + self.typ.with_name(self.name) + ";"
        else:
            return "    "*indent + self.typ.with_name(self.name) + " = " + self.val.generate() + ";"


@dataclass()
class ExprStmt(Statement):
    expr: Expression

    def generate(self, indent=0):
        return "    "*indent + self.expr.generate() + ";"


@dataclass()
class Comment(Statement):
    msg: str

    def generate(self, indent=0):
        return "    "*indent + "// " + self.msg


@dataclass()
class If(Statement):
    cond: Expression
    then_do: Statement
    else_do: Statement

    def generate(self, indent=0):
        ret = "    " * indent + f"if ({self.cond.generate()}) "
        if isinstance(self.then_do, Block):
            ret += self.then_do.generate(indent).lstrip()
            ret += " else "
        else:
            ret += "\n"
            ret += self.then_do.generate(indent + 1)
            ret += "\n" + "    " * indent + "else "

        if isinstance(self.else_do, Block):
            # ret += " "
            ret += self.else_do.generate(indent).lstrip()
        else:
            ret += "\n"
            ret += self.else_do.generate(indent + 1)

        return ret


@dataclass()
class While(Statement):
    cond: Expression
    do: Statement

    def generate(self, indent=0):
        ret = "    " * indent + f"while ({self.cond.generate()}) "
        if isinstance(self.do, Block):
            ret += self.do.generate(indent).lstrip()
        else:
            ret += "\n"
            ret += self.do.generate(indent + 1)
        return ret


@dataclass()
class Block(Statement):
    stmts: List[Statement]

    def generate(self, indent=0):
        stmts = [''] + [stmt.generate(indent + 1) for stmt in self.stmts] + ['']
        return "    " * indent + "{" + "\n".join(stmts) + "    " * indent + "}"


@dataclass()
class UnscopedBlock(Statement):
    stmts: List[Statement]

    def generate(self, indent=0):
        return "    " * indent + " ".join(stmt.generate(0)
                                          if not isinstance(stmt, UnscopedBlock)
                                          else (stmt.generate(0) + "\n" + "    " * indent)[:-1]
                                          for stmt in self.stmts)


@dataclass()
class Return(Statement):
    expr: Expression

    def generate(self, indent=0):
        if self.expr is None:
            return "    " * indent + "return;"
        else:
            return "    "*indent + "return " + self.expr.generate() + ";"


@dataclass()
class StrStmt(Statement):
    s: str

    def format(self, *args, **kwargs):
        return StrStmt(self.s.format(*args, **kwargs))

    def generate(self, indent=0):
        return "    " * indent + self.s

# endregion


@dataclass()
class TopLevel(Node, ABC):
    @abstractmethod
    def definition(self) -> str:
        pass

    @abstractmethod
    def declaration(self) -> str:
        pass


@dataclass()
class Include(TopLevel):
    name: str
    angled: bool = field(default=False)

    def definition(self):
        if self.angled:
            return "#include <" + str(self.name) + ">"
        else:
            return "#include \"" + str(self.name) + "\""

    def declaration(self):
        return self.definition()


@dataclass()
class Struct(TopLevel):
    name: str
    fields: Dict[str, Type]

    @property
    def struct_type(self):
        return StructType(self.name)

    def declaration(self) -> str:
        # return "struct " + self.name + ";\n"
        decl = f"struct {self.name} {{" + "\n".join(
            [''] + ["    " + typ.with_name(name) + ";" for name, typ in self.fields.items()] + ['']) + "};\n"
        return decl

    def definition(self):
        # decl = f"struct {self.name} {{" + "\n".join(
        #     [''] + ["    " + typ.with_name(name) + ";" for name, typ in self.fields.items()] + ['']) + "};\n"
        # return decl
        return "struct " + self.name + ";\n"


@dataclass()
class Function(TopLevel):
    name: str
    args: Dict[str, Type]
    ret: Type
    body: List[Statement]

    @property
    def func_type(self):
        return FunctionType(list(self.args.values()), self.ret)

    def definition(self):
        def_ = self.ret.as_func_ret_def(self.name, self.args) + " {"
        if len(self.body) == 0:
            def_ += " }"
        else:
            def_ += "\n"
            for stmt in self.body:
                def_ += stmt.generate(1) + "\n"
            def_ += "}\n"
        return def_

    def declaration(self) -> str:
        # print(self.func_type)
        decl = f"{self.func_type.as_func_ret(self.name)};"
        return decl


@dataclass()
class Global(TopLevel):
    name: str
    type: Type
    val: Expression

    def definition(self) -> str:
        return f"extern {self.type.with_name(self.name)};"

    def declaration(self) -> str:
        return f"{self.type.with_name(self.name)} = {self.val.generate()};"


@dataclass()
class GlobalArray(TopLevel):
    name: str
    contained: Type
    num: int
    val: ArrayInit

    def definition(self) -> str:
        return f"{self.contained.with_name(self.name)}[{self.num}] = {self.val.generate()};"

    def declaration(self) -> str:
        return f"extern {self.contained.with_name(self.name)}[{self.num}];"


class Program:
    def __init__(self, top_levels: List[TopLevel], path: pathlib.Path):
        self.top_levels = top_levels
        self.path = path

    def generate(self, name: str, header: IO, source: IO):
        header.write(f"#ifndef {name.upper()}_H\n")
        header.write(f"#define {name.upper()}_H\n")

        source.write(f"#include \"{name}.h\"\n\n")
        for top_level in self.top_levels:
            header.write(top_level.declaration())
            header.write("\n\n")

            source.write(top_level.definition())
            source.write("\n\n")
        header.write(f"#endif  // {name.upper()}_H")


class Unit:
    def __init__(self, programs: List[Program]):
        self.programs = programs


def void_ptr():
    return PointerType(VoidType())


def printf(s: str, end="\\n"):
    return ExprStmt(Call(GetVar("printf"), [Constant(s + end)]))
