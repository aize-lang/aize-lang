from __future__ import annotations

from aizec.common import *

from aizec.ir import Extension
from aizec.ir.nodes import *

from .symbols import NamespaceSymbol, VariableSymbol, TypeSymbol, StructTypeSymbol


class SymbolData(Extension):
    def general(self, set_to=None):
        raise NotImplementedError()

    class ProgramData:
        def __init__(self, builtins: NamespaceSymbol):
            self.builtins = builtins

    def program(self, node: ProgramIR, set_to: ProgramData = None) -> ProgramData:
        return super().program(node, set_to)

    class SourceData:
        def __init__(self, globals: NamespaceSymbol):
            self.globals = globals

    def source(self, node: SourceIR, set_to: SourceData = None) -> SourceData:
        return super().source(node, set_to)

    class FunctionData:
        def __init__(self, symbol: VariableSymbol, namespace: NamespaceSymbol, attrs: List[str]):
            self.symbol = symbol
            self.namespace = namespace
            self.attrs = attrs

    def function(self, node: FunctionIR, set_to: FunctionData = None) -> FunctionData:
        return super().function(node, set_to)

    class ParamData:
        def __init__(self, symbol: VariableSymbol):
            self.symbol = symbol

    def param(self, node: ParamIR, set_to: ParamData = None) -> ParamData:
        return super().param(node, set_to)

    class StmtData:
        def __init__(self, is_terminal: bool):
            self.is_terminal = is_terminal

    def stmt(self, node: StmtIR, set_to: StmtData = None) -> StmtData:
        return super().stmt(node, set_to)

    class ExprData:
        def __init__(self, return_type: TypeSymbol, is_lval: bool):
            self.return_type: TypeSymbol = return_type
            self.is_lval = is_lval

    def expr(self, node: ExprIR, set_to: ExprData = None) -> ExprData:
        return super().expr(node, set_to)

    class CompareData:
        def __init__(self, is_signed: bool):
            self.is_signed = is_signed

    def compare(self, node: CompareIR, set_to: CompareData = None) -> CompareData:
        return super().compare(node, set_to)

    class ArithmeticData:
        def __init__(self, is_signed: bool):
            self.is_signed = is_signed

    def arithmetic(self, node: ArithmeticIR, set_to: ArithmeticData = None) -> ArithmeticData:
        return super().arithmetic(node, set_to)

    class GetVarData:
        def __init__(self, symbol: VariableSymbol, is_function: bool):
            self.symbol = symbol
            self.is_function = is_function

    def get_var(self, node: GetVarIR, set_to: GetVarData = None) -> GetVarData:
        return super().get_var(node, set_to)

    class SetVarData:
        def __init__(self, symbol: VariableSymbol):
            self.symbol = symbol

    def set_var(self, node: SetVarIR, set_to: SetVarData = None) -> SetVarData:
        return super().set_var(node, set_to)

    class GetAttrData:
        def __init__(self, struct_type: Optional[StructTypeSymbol], index: Optional[int]):
            self.struct_type = struct_type
            self.index = index

    def get_attr(self, node: GetAttrIR, set_to: GetAttrData = None) -> GetAttrData:
        return super().get_attr(node, set_to)

    class SetAttrData:
        def __init__(self, struct_type: Optional[StructTypeSymbol], index: Optional[int]):
            self.struct_type = struct_type
            self.index = index

    def set_attr(self, node: SetAttrIR, set_to: SetAttrData = None) -> SetAttrData:
        return super().set_attr(node, set_to)

    class IntrinsicData:
        class IntrinsicType:
            pass

        class IntConversionIntrinsic(IntrinsicType):
            def __init__(self, from_bits: int, to_bits: int):
                self.from_bits = from_bits
                self.to_bits = to_bits

        def __init__(self, type: IntrinsicType):
            self.type = type

    def intrinsic(self, node: IntrinsicIR, set_to: IntrinsicData = None) -> IntrinsicData:
        return super().intrinsic(node, set_to)

    class GetStaticAttrExprData:
        def __init__(self, resolved_value: VariableSymbol):
            self.resolved_value = resolved_value

    def get_static_attr_expr(self, node: GetStaticAttrExprIR, set_to: GetStaticAttrExprData = None) -> GetStaticAttrExprData:
        return super().get_static_attr_expr(node, set_to)

    class TypeData:
        def __init__(self, resolved_type: TypeSymbol):
            self.resolved_type: TypeSymbol = resolved_type

    def type(self, node: TypeIR, set_to: TypeData = None) -> TypeData:
        return super().type(node, set_to)

    class NamespaceData:
        def __init__(self, resolved_namespace: NamespaceSymbol):
            self.resolved_namespace = resolved_namespace

    def namespace(self, node: NamespaceIR, set_to: NamespaceData = None) -> NamespaceData:
        return super().namespace(node, set_to)

    # region Extension Extensions
    class DeclData:
        def __init__(self, declarer: NodeIR, declares: VariableSymbol, type: TypeSymbol):
            self.declarer = declarer
            self.declares = declares
            self.type = type

    def decl(self, node: NodeIR, set_to: DeclData = None) -> DeclData:
        return super().ext(node, 'decl', set_to)
    # endregion
