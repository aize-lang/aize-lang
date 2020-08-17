from __future__ import annotations

from enum import Enum
from typing import List, Optional

from aizec.aize_common import Position


class Program:
    def __init__(self, block: BlockData):
        self.block = block


class BlockData:
    def __init__(self, static_stmts: List[StaticStmt], dyn_stmts: List[DynStmt]):
        self.static_stmts = static_stmts
        self.dyn_stmts = dyn_stmts


class StaticStmt:
    pass


class StaticAssign(StaticStmt):
    def __init__(self, name: str, static_expr: StaticExpr, pos: Position):
        self.name = name
        self.static_expr = static_expr
        self.pos = pos


class StaticModule(StaticStmt):
    def __init__(self, name: str, block: BlockData, pos: Position):
        self.name = name
        self.block = block

        self.pos = Position


class StaticParamType(Enum):
    TYPE = 0
    VALUE = 1


class StaticParam:
    def __init__(self, name: str, type: StaticParamType, pos: Position):
        self.name = name
        self.type = type

        self.pos = pos


class StaticFunction(StaticStmt):
    def __init__(self, name: str, params: List[StaticParam], body: List[StaticStmt], pos: Position):
        self.name = name
        self.params = params
        self.body = body

        self.pos = pos


class StaticExpr:
    pass


class StructAttr:
    def __init__(self, name: str, type: StaticExpr):
        self.name = name
        self.type = type


class StaticStruct(StaticExpr):
    def __init__(self, attrs: List[StructAttr]):
        self.attrs = attrs


class StaticImport(StaticExpr):
    def __init__(self, source: str, is_std: bool):
        self.source = source
        self.is_std = is_std

        self.block: Optional[BlockData] = None
