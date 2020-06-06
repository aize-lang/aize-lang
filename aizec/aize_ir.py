from __future__ import annotations

from aizec.common import *

from aizec.aize_source import *
from aizec.aize_symbols import *

T = TypeVar('T')


__all__ = ['NodeIR', 'TopLevelIR', 'UnresolvedTypeIR', 'AnnotationIR', 'ProgramIR', 'StmtIR', 'ExprIR', 'ReturnIR',
           'MethodDeclIR', 'IntIR', 'MalformedTypeIR', 'FieldIR', 'TypeIR', 'FunctionIR', 'GetTypeIR', 'SourceIR',
           'MethodDefIR', 'ParamIR', 'TextIR', 'ClassIR', 'WithNamespace']


class NodeIR:
    pass


class WithNamespace(Protocol):
    namespace: NamespaceSymbol


class ProgramIR(NodeIR):
    def __init__(self, sources: List[SourceIR], namespace: NamespaceSymbol):
        self.sources = sources
        self.namespace = namespace


class SourceIR(NodeIR):
    def __init__(self, top_levels: List[TopLevelIR], source_name: str, namespace: NamespaceSymbol):
        self.top_levels = top_levels
        self.source_name = source_name
        self.namespace = namespace


class TextIR(Positioned, NodeIR):
    def __init__(self, pos: Position):
        super().__init__(pos)


class TopLevelIR(TextIR):
    pass


class FunctionIR(TopLevelIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, body: List[StmtIR], pos: Position):
        super().__init__(pos)
        self.name = name
        self.params = params
        self.ret = ret
        self.body = body


class ClassIR(TopLevelIR):
    def __init__(self, name: str, fields: Dict[str, FieldIR], methods: Dict[str, MethodDefIR], pos: Position):
        super().__init__(pos)
        self.name = name
        self.fields = fields
        self.methods = methods


class FieldIR(TextIR):
    def __init__(self, name: str, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.name = name
        self.type = type


class MethodDeclIR(TextIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, pos: Position):
        super().__init__(pos)
        self.params = params
        self.ret = ret


class MethodDefIR(TextIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, body: List[StmtIR], pos: Position):
        super().__init__(pos)
        self.params = params
        self.ret = ret
        self.body = body


class ParamIR(TextIR):
    def __init__(self, name: str, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.name = name
        self.type = type


class StmtIR(TextIR):
    pass


class ReturnIR(StmtIR):
    def __init__(self, expr: ExprIR, pos: Position):
        super().__init__(pos)
        self.expr = expr


class ExprIR(TextIR):
    pass


class IntIR(ExprIR):
    def __init__(self, num: int, pos: Position):
        super().__init__(pos)
        self.num = num


class AnnotationIR(TextIR):
    def __init__(self, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.type = type


class TypeIR(NodeIR):
    RESOLVED: bool


class MalformedTypeIR(TextIR, TypeIR):
    RESOLVED = False

    def __init__(self, pos: Position):
        super().__init__(pos)


class UnresolvedTypeIR(TextIR, TypeIR):
    RESOLVED = False

    def __init__(self, pos: Position):
        super().__init__(pos)


class GetTypeIR(UnresolvedTypeIR):
    def __init__(self, name: str, pos: Position):
        super().__init__(pos)
        self.name = name


# if __name__ == '__main__':
#     __all__ = ['NodeIR', 'WithBody'] + [child.__name__ for child in all_subclasses(NodeIR)]
#     print(__all__)
