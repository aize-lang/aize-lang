from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from . import *


class TableType(Enum):
    GLOBAL = 0
    FILE = 1
    C_FILE = 2
    SCOPE = 3
    CLASS = 4
    OBJECT = 5


class Table:
    def __init__(self, type: TableType, parent: Table = None):
        self.parent = parent
        self._names: Dict[str, NameDecl] = {}
        self._types: Dict[str, Type] = {}
        self._namespaces: Dict[str, Table] = {}

        self.type = type

        self.block_count = 0

    @classmethod
    def empty(cls, type: TableType):
        return cls.new(type, {}, {}, {})

    @classmethod
    def new(cls, type: TableType, names: Dict[str, NameDecl], types: Dict[str, Type], namespaces: Dict[str, Table]):
        table = cls(type)
        table._names = names
        table._types = types
        table._namespaces = namespaces
        return table

    def add_name(self, name: str, decl: NameDecl):
        # TODO assert that the decl is fully defined?
        self._names[name] = decl
        return decl

    def add_type(self, name: str, type: Type):
        self._types[name] = type

    def add_namespace(self, name: str, namespace: Table):
        self._namespaces[name] = namespace

    def get_name(self, name: str):
        table = self
        while table is not None:
            if name in table._names:
                return table._names[name]
            table = table.parent
        raise KeyError(name)

    def get_type(self, name: str):
        table = self
        while table is not None:
            if name in table._types:
                return table._types[name]
            table = table.parent
        raise KeyError(name)

    def get_attr(self, name: str):
        table = self
        while table is not None:
            if name in table._names:
                return table._names[name]
            if name in table._types:
                return table._types[name]
            if name in table._namespaces:
                return table._namespaces[name]
            table = table.parent
        raise KeyError(name)

    def get_namespace(self, name: str) -> Table:
        table = self
        while table is not None:
            if name in table._namespaces:
                return table._namespaces[name]
            table = table.parent
        raise KeyError(name)

    def child(self, type: TableType):
        return Table(type, self)

    def __repr__(self):
        return f"Table(type={self.type})"


@dataclass()
class Node:
    pos: TextPos = field(init=False, repr=False)

    def place(self, pos: TextPos):
        self.pos = pos
        return self

    def define(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)
        return self


@dataclass()
class TypeNode(Node):
    pass


@dataclass()
class Type:
    pass


@dataclass()
class NameDecl:
    name: str
    type_ref: TypeNode
    type: Type = field(init=False, repr=False)
    unique: str = field(init=False, repr=False)

    @classmethod
    def direct(cls, name: str, unique: str, type: Type):
        # noinspection PyTypeChecker
        return cls(name, None).defined(type, unique)

    def defined(self, type: Type, unique: str):
        self.type = type
        self.unique = unique
        return self


@dataclass()
class Name(TypeNode):
    name: str


@dataclass()
class Expr(Node):
    ret: Type = field(init=False, repr=False)


@dataclass()
class GetVar(Expr):
    name: str
    ref: NameDecl = field(init=False, repr=False)


@dataclass()
class SetVar(Expr):
    name: str
    val: Expr
    ref: NameDecl = field(init=False, repr=False)


@dataclass()
class Add(Expr):
    left: Expr
    right: Expr


@dataclass()
class Sub(Expr):
    left: Expr
    right: Expr


@dataclass()
class Mul(Expr):
    left: Expr
    right: Expr


@dataclass()
class Div(Expr):
    left: Expr
    right: Expr


@dataclass()
class Mod(Expr):
    left: Expr
    right: Expr


@dataclass()
class LT(Expr):
    left: Expr
    right: Expr


@dataclass()
class GT(Expr):
    left: Expr
    right: Expr


@dataclass()
class LE(Expr):
    left: Expr
    right: Expr


@dataclass()
class GE(Expr):
    left: Expr
    right: Expr


@dataclass()
class EQ(Expr):
    left: Expr
    right: Expr


@dataclass()
class NE(Expr):
    left: Expr
    right: Expr


@dataclass()
class Neg(Expr):
    right: Expr


@dataclass()
class Not(Expr):
    right: Expr


@dataclass()
class Inv(Expr):
    right: Expr


@dataclass()
class Call(Expr):
    left: Expr
    args: List[Expr]

    method_call: Union[MethodCall, None] = field(init=False, default=None, repr=False)


@dataclass()
class GetAttr(Expr):
    left: Expr
    attr: str
    pointed: NameDecl = field(init=False, repr=False)


@dataclass()
class SetAttr(Expr):
    left: Expr
    attr: str
    val: Expr
    pointed: NameDecl = field(init=False, repr=False)


@dataclass()
class MethodCall(Expr):
    obj: Expr
    method: str
    args: List[Expr]
    depth: int

    pointed: NameDecl = field(init=False, repr=False)

    @classmethod
    def is_method(cls, obj: Call):
        if isinstance(obj, Call):
            if isinstance(obj.left, GetAttr):
                if isinstance(obj.left.left.ret, ClassType) and obj.left.attr in obj.left.left.ret.methods:
                    return obj.left.left.ret.methods[obj.left.attr]
        else:
            return False

    @classmethod
    def make_method_call(cls, obj: Call, depth: int):
        meth = cls.is_method(obj)
        if meth:
            call = cls(obj.left.left, obj.left.attr, obj.args, depth).place(obj.pos)
            call.pointed = meth
            obj.method_call = call
        else:
            raise Exception()


@dataclass()
class GetNamespaceName(Expr):
    namespace: Expr
    attr: str
    pointed: NameDecl = field(init=False, repr=False)


@dataclass()
class GetNamespace(Expr):
    namespace: str

    table: Table = field(init=False, repr=False)


@dataclass()
class Num(Expr):
    num: int


@dataclass()
class Str(Expr):
    string: str


@dataclass()
class Param(NameDecl):
    pass


@dataclass()
class Lambda(Expr):
    args: List[Param]
    ret: Type
    body: List[Stmt]


@dataclass()
class Stmt(Node):
    pass


@dataclass()
class If(Stmt):
    cond: Expr
    then_stmt: Stmt
    else_stmt: Stmt


@dataclass()
class While(Stmt):
    cond: Expr
    body: Stmt


@dataclass()
class Block(Stmt):
    stmts: List[Stmt]

    table: Table = field(init=False, repr=False)
    block_count: int = field(init=False, repr=False)


@dataclass()
class VarDecl(Stmt, NameDecl):
    val: Expr


@dataclass()
class Return(Stmt):
    val: Expr


@dataclass()
class ExprStmt(Stmt):
    expr: Expr


@dataclass()
class Top(Node):
    pass


@dataclass()
class Class(Top, NameDecl):
    base: Union[TypeNode, None]

    attrs: Dict[str, Attr]
    methods: Dict[str, Method]

    type: ClassType = field(init=False, repr=False)


@dataclass()
class Attr(Node, NameDecl):
    pass


@dataclass()
class Method(Node, NameDecl):
    args: List[Param]
    ret: TypeNode
    body: List[Stmt]

    type: FuncType = field(init=False, repr=False)
    table: Table = field(init=False, repr=False)


@dataclass()
class ClassType(Type):
    base: ClassType
    attrs: Dict[str, Attr]
    methods: Dict[str, Method]

    structs: str = field(init=False, repr=False)

    obj_namespace: Table = field(init=False, repr=False)
    cls_namespace: Table = field(init=False, repr=False)


@dataclass()
class Function(Top, NameDecl):
    args: List[Param]
    ret: TypeNode
    body: List[Stmt]

    type: FuncType = field(init=False, repr=False)
    table: Table = field(init=False, repr=False)

    temp_count: int = field(init=False, default=0, repr=False)


@dataclass()
class Import(Top):
    file: Path
    as_name: str


@dataclass()
class CImport(Top):
    header: Path
    source: Path


@dataclass()
class FuncType(Type):
    args: List[Type]
    ret: Type


@dataclass()
class IntType(Type):
    pass


@dataclass()
class VoidType(Type):
    pass


@dataclass()
class LongType(Type):
    pass


@dataclass()
class BoolType(Type):
    pass


@dataclass()
class FuncTypeNode(TypeNode):
    args: List[TypeNode]
    ret: TypeNode


@dataclass()
class File(Node):
    path: Path
    is_main: bool
    tops: List[Top]
    table: Table = field(init=False, repr=False)


@dataclass()
class Program(Node):
    files: List[File]
    # [(header, source), ...]
    c_files: List[Tuple[Path, Path]] = field(init=False, default_factory=list)

    main: NameDecl = field(init=False, repr=False)
