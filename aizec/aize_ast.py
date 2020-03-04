from __future__ import annotations

from typing import List, Type, TypeVar, Union, Hashable
from pathlib import Path

T = TypeVar('T')


__all__ = [
    'Node', 'PassData',
    'Program',
    'Source', 'FileSource', 'StdinSource', 'StringSource',
    'TopLevel', 'Class', 'Trait',
    'ClassStmt', 'Attr', 'Method', 'MethodImpl', 'Import', 'Function',
    'Stmt', 'IfStmt', 'WhileStmt', 'BlockStmt', 'VarDeclStmt', 'ReturnStmt', 'ExprStmt',
    'Expr',
    'GetVarExpr', 'SetVarExpr', 'GetAttrExpr', 'SetAttrExpr',
    'BinaryExpr', 'LTExpr', 'GTExpr', 'LEExpr', 'GEExpr', 'EQExpr', 'NEExpr',
    'AddExpr', 'SubExpr', 'MulExpr', 'DivExpr', 'ModExpr',
    'UnaryExpr', 'NegExpr', 'NotExpr', 'InvExpr',
    'CallExpr',
    'IntLiteral', 'StrLiteral',
    'Param',
    'TypeAnnotation', 'GetTypeAnnotation'
]


class Node:
    def __init__(self):
        self.pass_data: Union[PassData, None] = None

    def add_data(self, pass_data: PassData):
        pass_data.bound = self
        pass_data.next_data = self.pass_data
        self.pass_data = pass_data
        return self


class PassData:
    def __init__(self, bound: Node = None, next_data: PassData = None):
        self.bound: Union[Node, None] = None
        self.next_data: Union[PassData, None] = next_data

    @classmethod
    def of(cls: Type[T], obj: Node) -> T:
        data = obj.pass_data
        while not isinstance(data, cls) and data is not None:
            data = data.next_data
        if data is None:
            raise TypeError(f"Object {obj} does not have {cls.__name__}")
        return data


class Program(Node):
    def __init__(self, sources: List[Source]):
        super().__init__()
        self.sources = sources


class Source(Node):
    def __init__(self, text: str, is_main: bool, top_levels: List[TopLevel]):
        super().__init__()
        self.text = text
        self.lines = text.splitlines()
        self.is_main = is_main

        self.top_levels = top_levels

    def get_unique(self) -> Hashable:
        """Return a unique (hashable) identifier suitable for ensuring no source is parsed multiple times"""
        raise NotImplementedError()

    def get_name(self) -> str:
        """Return a str that is displayed as the source in error messages"""
        raise NotImplementedError()

    def get_path(self) -> Union[Path, None]:
        """Return a Path if this source has a path, or None if it does not"""
        raise NotImplementedError()

    @property
    def imports(self) -> List[Import]:
        return [top_level for top_level in self.top_levels if isinstance(top_level, Import)]


class FileSource(Source):
    def __init__(self, path: Path, text: str, is_main: bool, top_levels: List[TopLevel]):
        super().__init__(text, is_main, top_levels)
        self.path = path

    def get_unique(self) -> Hashable:
        return self.path

    def get_name(self) -> str:
        return str(self.path)

    def get_path(self) -> Union[Path, None]:
        return self.path


class StringSource(Source):
    def __init__(self, text: str, is_main: bool, top_levels: List[TopLevel]):
        super().__init__(text, is_main, top_levels)

    def get_unique(self) -> Hashable:
        return "<string>"

    def get_name(self) -> str:
        return "<string>"

    def get_path(self) -> Union[Path, None]:
        return None


class StdinSource(Source):
    def __init__(self, text: str, is_main: bool, top_levels: List[TopLevel]):
        super().__init__(text, is_main, top_levels)

    def get_unique(self) -> Hashable:
        return "<stdin>"

    def get_name(self) -> str:
        return "<stdin>"

    def get_path(self) -> Union[Path, None]:
        return None


class TopLevel(Node):
    pass


class Class(TopLevel):
    def __init__(self, name: str, parents: List[TypeAnnotation], body: List[ClassStmt]):
        super().__init__()

        self.name: str = name
        self.parents: List[TypeAnnotation] = parents
        self.body: List[ClassStmt] = body


class Trait(TopLevel):
    def __init__(self, name: str, parents: List[TypeAnnotation], body: List[ClassStmt]):
        super().__init__()

        self.name: str = name
        self.parents: List[TypeAnnotation] = parents
        self.body: List[ClassStmt] = body


class Import(TopLevel):
    def __init__(self, anchor: str, path: Path):
        super().__init__()

        self.anchor: str = anchor
        self.path: Path = path


class Function(TopLevel):
    def __init__(self, name: str, params: List[Param], ret: TypeAnnotation, body: List[Stmt]):
        super().__init__()

        self.name = name
        self.params = params
        self.ret = ret
        self.body = body


class ClassStmt(Node):
    pass


class Attr(ClassStmt):
    def __init__(self, name: str, annotation: TypeAnnotation):
        super().__init__()

        self.name = name
        self.annotation = annotation


class Method(ClassStmt):
    def __init__(self, name: str, params: List[Param], ret: TypeAnnotation):
        super().__init__()

        self.name = name
        self.params = params
        self.ret = ret


class MethodImpl(Method):
    def __init__(self, name: str, params: List[Param], ret: TypeAnnotation, body: List[Stmt]):
        super().__init__(name, params, ret)

        self.body = body


class Stmt(Node):
    pass


class IfStmt(Stmt):
    def __init__(self, cond: Expr, then_do: Stmt, else_do: Stmt):
        super().__init__()

        self.cond = cond
        self.then_do = then_do
        self.else_do = else_do


class WhileStmt(Stmt):
    def __init__(self, cond: Expr, do: Stmt):
        super().__init__()

        self.cond = cond
        self.do = do


class BlockStmt(Stmt):
    def __init__(self, body: List[Stmt]):
        super().__init__()

        self.body = body


class VarDeclStmt(Stmt):
    def __init__(self, name: str, annotation: TypeAnnotation, value: Expr):
        super().__init__()

        self.name = name
        self.annotation = annotation
        self.value = value


class ReturnStmt(Stmt):
    def __init__(self, value: Expr):
        super().__init__()

        self.value = value


class ExprStmt(Stmt):
    def __init__(self, value: Expr):
        super().__init__()

        self.value = value


class Expr(Node):
    pass


class GetVarExpr(Expr):
    def __init__(self, var: str):
        super().__init__()

        self.var = var


class SetVarExpr(Expr):
    def __init__(self, var: str, value: Expr):
        super().__init__()

        self.var = var
        self.value = value


class GetAttrExpr(Expr):
    def __init__(self, obj: Expr, attr: str):
        super().__init__()

        self.obj = obj
        self.attr = attr


class SetAttrExpr(Expr):
    def __init__(self, obj: Expr, attr: str, value: Expr):
        super().__init__()

        self.obj = obj
        self.attr = attr
        self.value = value


# region Binary

class BinaryExpr(Expr):
    def __init__(self, left: Expr, right: Expr):
        super().__init__()

        self.left = left
        self.right = right


class GTExpr(BinaryExpr):
    pass


class LTExpr(BinaryExpr):
    pass


class GEExpr(BinaryExpr):
    pass


class LEExpr(BinaryExpr):
    pass


class EQExpr(BinaryExpr):
    pass


class NEExpr(BinaryExpr):
    pass


class AddExpr(BinaryExpr):
    pass


class SubExpr(BinaryExpr):
    pass


class MulExpr(BinaryExpr):
    pass


class DivExpr(BinaryExpr):
    pass


class ModExpr(BinaryExpr):
    pass

# endregion


# region Unary

class UnaryExpr(Expr):
    def __init__(self, right: Expr):
        super().__init__()

        self.right = right


class InvExpr(UnaryExpr):
    pass


class NegExpr(UnaryExpr):
    pass


class NotExpr(UnaryExpr):
    pass

# endregion


class CallExpr(Expr):
    def __init__(self, left: Expr, args: List[Expr]):
        super().__init__()

        self.left = left
        self.args = args


class IntLiteral(Expr):
    def __init__(self, num: int):
        super().__init__()

        self.num = num


class StrLiteral(Expr):
    def __init__(self, s: str):
        super().__init__()

        self.s = s


class Param(Node):
    def __init__(self, name: str, annotation: TypeAnnotation):
        super().__init__()

        self.name = name
        self.annotation = annotation


class TypeAnnotation(Node):
    pass


class GetTypeAnnotation(TypeAnnotation):
    def __init__(self, type: str):
        super().__init__()

        self.type = type
