from __future__ import annotations

from typing import List, Type, TypeVar, Union, Hashable
from pathlib import Path

T = TypeVar('T')


__all__ = ['Node', 'PassData',
           'Program',
           'Source', 'FileSource', 'StdinSource',
           'TopLevel', 'Class', 'Trait',
           'ClassStmt', 'Attr', 'Method', 'MethodImpl', 'Import', 'Function',
           'Statement', 'IfStatement', 'WhileStatement', 'BlockStatement', 'VarDeclStatement', 'ReturnStatement', 'ExpressionStatement',
           'Param',
           'TypeAnnotation', 'GetTypeAnnotation']


class Node:
    def __init__(self):
        self.pass_data: PassData = EmptyPassData()

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


class EmptyPassData(PassData):
    def __init__(self):
        super().__init__()


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


class StdinSource(Source):
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
    def __init__(self, name: str, params: List[Param], ret: TypeAnnotation, body: List[Statement]):
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
    def __init__(self, name: str, params: List[Param], ret: TypeAnnotation, body: List[Statement]):
        super().__init__(name, params, ret)

        self.body = body


class Statement(Node):
    pass


class IfStatement(Statement):
    def __init__(self, cond: Expression, then_do: Statement, else_do: Statement):
        super().__init__()

        self.cond = cond
        self.then_do = then_do
        self.else_do = else_do


class WhileStatement(Statement):
    def __init__(self, cond: Expression, do: Statement):
        super().__init__()

        self.cond = cond
        self.do = do


class BlockStatement(Statement):
    def __init__(self, body: List[Statement]):
        super().__init__()

        self.body = body


class VarDeclStatement(Statement):
    def __init__(self, name: str, annotation: TypeAnnotation, value: Expression):
        super().__init__()

        self.name = name
        self.annotation = annotation
        self.value = value


class ReturnStatement(Statement):
    def __init__(self, value: Expression):
        super().__init__()

        self.value = value


class ExpressionStatement(Statement):
    def __init__(self, value: Expression):
        super().__init__()

        self.value = value


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
