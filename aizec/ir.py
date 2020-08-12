from __future__ import annotations

from enum import Enum
from typing import List

from aizec.aize_common import Position


class Program:
    def __init__(self, modules: List[Module]):
        self.modules = modules


class Module:
    def __init__(self, namespace: NamespaceData):
        self.namespace = namespace


class NamespaceData:
    def __init__(self, static_values, dyn_values):
        self.static_values = static_values
        self.dyn_values = dyn_values


class StaticStmt:
    pass


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

