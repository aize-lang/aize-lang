from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple, ClassVar, Iterable

from aizec.common import *


# region Table
class TableType(Enum):
    GLOBAL = 0
    FILE = 1
    C_FILE = 2
    SCOPE = 3
    CLASS = 4
    TRAIT = 5
    OBJECT = 6


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
# endregion


# region Node
@dataclass()
class Node:
    pos: TextPos = field(init=False, repr=False)

    def place(self, pos: TextPos):
        self.pos = pos
        return self

    def define(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self


class TextPos:
    def __init__(self, text: str, line: int, pos: Tuple[int, int], file: Path):
        self.text = text
        self.line = line
        self.pos = pos
        self.file = file

    def get_line(self):
        return self.text.splitlines()[self.line-1]

    def __repr__(self):
        return f"TextPos({self.text!r}, {self.line}, {self.pos})"
# endregion


# region Name Declaration
@dataclass()
class NameDecl:
    name: str
    unique: str = field(init=False, repr=False)

    type_ref: TypeNode
    type: Type = field(init=False, repr=False)

    @classmethod
    def direct(cls, name: str, unique: str, type: Type):
        # noinspection PyTypeChecker
        return cls(name, None).defined(type, unique)

    def defined(self, type: Type, unique: str):
        self.type = type
        self.unique = unique
        return self


@dataclass()
class Param(NameDecl):
    pass
# endregion


# region AST Types
@dataclass()
class TypeNode(Node):
    pass


@dataclass()
class GetType(TypeNode):
    name: str


@dataclass()
class FuncTypeNode(TypeNode):
    args: List[TypeNode]
    ret: TypeNode

# endregion


# region Actual Types
@dataclass()
class Type:
    def __le__(self, other: Type):
        """t1 <= t2 means that t1 is t2 or a subclass"""
        raise NotImplementedError()

    def __eq__(self, other: Type):
        raise NotImplementedError()

    def __str__(self):
        raise NotImplementedError()


# region Interfaced Types
@dataclass()
class InterfacedType(Type):
    name: str
    unique: str = field(init=False, repr=False)
    parents: List[InterfacedType]

    ttable: str = field(init=False, repr=False)
    interface: Dict[str, Method]

    obj_namespace: Table = field(init=False, repr=False, default_factory=lambda: Table(TableType.OBJECT))
    cls_namespace: Table = field(init=False, repr=False, default_factory=lambda: Table(TableType.CLASS))

    def define(self, unique: str, ttable: str):
        self.unique = unique
        self.ttable = ttable
        return self

    def get_owner(self, meth: str):
        for parent in self.parents:
            try:
                return parent.get_owner(meth)
            except KeyError:
                pass
        else:
            if meth in self.interface:
                return self
            else:
                raise KeyError(meth)

    def get_method(self, meth: str):
        if meth in self.interface:
            return self.interface[meth]
        for parent in self.parents:
            try:
                return parent.get_method(meth)
            except KeyError:
                pass
        else:
            raise KeyError(meth)

    def get_index(self, meth: str):
        return list(self.interface.keys()).index(meth)

    def __le__(self, other: Type):
        """t1 <= t2 means that t1 is t2 or a subclass"""
        if self == other:
            return True
        elif isinstance(other, InterfacedType):
            for parent in other.parents:
                if self <= parent:
                    return True
        return False

    def __eq__(self, other: Type):
        return other is self

    def __str__(self):
        raise NotImplementedError()


@dataclass()
class TraitType(InterfacedType):
    children: List[InterfacedType] = field(init=False, repr=False, default_factory=list)

    def iter_children(self) -> Iterable[ClassType]:
        for child in self.children:
            if isinstance(child, ClassType):
                yield child
            elif isinstance(child, TraitType):
                yield from child.iter_children()

    def __str__(self):
        return f"{self.name}"


@dataclass()
class ClassType(InterfacedType):
    attrs: Dict[str, Attr]

    def add_method(self, name: str, unique: str, args: List[Type], ret: Type):
        meth = Method.fake(self, name, unique, args, ret)
        self.obj_namespace.add_name(name, meth)
        self.interface[name] = meth

    def add_clsmethod(self, name: str, unique: str, args: List[Type], ret: Type):
        cls_meth = NameDecl.direct(name, unique, FuncType(args, ret))
        self.cls_namespace.add_name(name, cls_meth)

    def calculate(self):
        obj_dict = self.attrs.copy()
        obj_dict.update({key: value for key, value in self.interface.items()})
        for key, value in obj_dict.items():
            self.obj_namespace.add_name(key, value)

    def __str__(self):
        return f"{self.name}"
# endregion


@dataclass()
class FuncType(Type):
    args: List[Type]
    ret: Type

    def __le__(self, other):
        if isinstance(other, FuncType):
            if len(self.args) == len(other.args) and self.ret <= other.ret:
                for arg, other_arg in zip(self.args, other.args):
                    if not arg >= other_arg:
                        break
                else:
                    return True
        return False

    def __eq__(self, other):
        if isinstance(other, FuncType):
            if len(self.args) == len(other.args) and self.ret == other.ret:
                for arg in self.args:
                    if not arg == other:
                        break
                else:
                    return True
        return False

    def __str__(self):
        return f"({', '.join(str(arg) for arg in self.args)}) -> {self.ret}"


# region Data Types
@dataclass()
class DataType(Type):
    name: ClassVar[str]

    def __le__(self, other):
        return type(self) == type(other)

    def __eq__(self, other):
        return type(self) == type(other)

    def __str__(self):
        return self.name


@dataclass()
class IntType(DataType):
    name = "int"


@dataclass()
class VoidType(DataType):
    name = "void"


@dataclass()
class LongType(DataType):
    name = "long"


@dataclass()
class BoolType(DataType):
    name = "bool"
# endregion
# endregion


# region Namespace
@dataclass()
class Namespace(Node):
    pass


@dataclass()
class GetNamespace(Namespace):
    namespace: str


@dataclass()
class GetNamespaceName(Namespace):
    namespace: Namespace
    name: str
# endregion


# region Top Level
@dataclass()
class Top(Node):
    pass


@dataclass()
class Trait(Top, NameDecl):
    name: str
    methods: Dict[str, Method]

    type: TraitType = field(init=False, repr=False)


@dataclass()
class Class(Top, NameDecl):
    traits: List[Type]

    attrs: Dict[str, Attr]
    methods: Dict[str, ConcreteMethod]

    type: ClassType = field(init=False, repr=False)


@dataclass()
class Function(Top, NameDecl):
    args: List[Param]
    ret: TypeNode
    body: List[Stmt]

    table: Table = field(init=False, repr=False)

    temp_count: int = field(init=False, default=0, repr=False)


@dataclass()
class FilePath:
    where: str
    rel_path: Path

    abs_path: Path = field(init=False, repr=False)

    def __hash__(self):
        return hash((self.where, self.rel_path))


@dataclass()
class Import(Top):
    file: FilePath
    as_name: str


@dataclass()
class NativeImport(Top):
    name: str
# endregion


# region Class Body
@dataclass()
class Attr(Node, NameDecl):
    pass


@dataclass()
class Method(Node, NameDecl):
    args: List[Param]
    ret: TypeNode

    owner: InterfacedType = field(init=False, repr=False)
    type: FuncType = field(init=False, repr=False)

    @classmethod
    def fake(cls, meth_cls: InterfacedType, name: str, unique: str, args: List[Type], ret: Type):
        # noinspection PyTypeChecker
        meth = cls(name, None, None, None)
        meth = meth.defined(FuncType([meth_cls] + args, ret), unique)
        meth.owner = meth_cls
        return meth


@dataclass()
class ConcreteMethod(Method):
    body: List[Stmt]

    temp_count: int = field(init=False, repr=False)
    table: Table = field(init=False, repr=False)
# endregion


# region Statement
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
# endregion


# region Expression
@dataclass()
class Expr(Node):
    ret: Type = field(init=False, repr=False)


@dataclass()
class Lambda(Expr):
    args: List[Param]
    ret: Type
    body: List[Stmt]


# region Arithmetic
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
# endregion


# region Compare
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
# endregion


# region Unary
@dataclass()
class Neg(Expr):
    right: Expr


@dataclass()
class Not(Expr):
    right: Expr


@dataclass()
class Inv(Expr):
    right: Expr
# endregion


# region Call / Item Access / Attribute Access
@dataclass()
class Call(Expr):
    left: Expr
    args: List[Expr]

    method_data: Union[MethodData, None] = field(init=False, default=None)

    def convert(self, depth: int):
        if isinstance(self.left, GetAttr):
            if isinstance(self.left.left.ret, InterfacedType):
                cls_type = self.left.left.ret
                try:
                    method = cls_type.get_method(self.left.attr)
                except KeyError:
                    pass
                else:
                    # if obj.left.attr in obj.left.left.ret.methods:
                    self.method_data = MethodData(self.left.left, self.left.attr, depth)
                    self.method_data.pointed = method
                    self.method_data.pointed_cls = cls_type
                    return True
        return False


@dataclass()
class MethodData:
    obj: Expr
    method: str
    depth: int

    pointed: Method = field(init=False, repr=False)
    pointed_cls: InterfacedType = field(init=False, repr=False)

    @property
    def index(self):
        return self.pointed_cls.get_index(self.method)


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
class GetNamespaceExpr(Expr):
    namespace: Namespace
    attr: str

    pointed: NameDecl = field(init=False, repr=False)

# endregion


# region Variable Access
@dataclass()
class GetVar(Expr):
    name: str
    ref: NameDecl = field(init=False, repr=False)


@dataclass()
class SetVar(Expr):
    name: str
    val: Expr
    ref: NameDecl = field(init=False, repr=False)
# endregion


# region Constants
@dataclass()
class Num(Expr):
    num: int


@dataclass()
class Str(Expr):
    string: str
# endregion
# endregion


# region Programs / Files
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
    needed_std: List[str] = field(init=False, repr=False, default_factory=list)
    classes: List[ClassType] = field(init=False, repr=False, default_factory=list)

    main: NameDecl = field(init=False, repr=False)
# endregion
