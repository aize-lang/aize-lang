from __future__ import annotations

from typing import List, Type, TypeVar, Union, Hashable
from pathlib import Path

T = TypeVar('T')


__all__ = [
    'NodeIR',
    'ProgramIR',
    'SourceIR',
    'TopLevelIR'
]


class NodeIR:
    pass


class ProgramIR(NodeIR):
    def __init__(self, sources: List[SourceIR]):
        self.sources = sources


class SourceIR(NodeIR):
    def __init__(self, top_levels: List[TopLevelIR]):
        self.top_levels = top_levels


class TopLevelIR(NodeIR):
