from __future__ import annotations

from aizec.common import *

from aizec.ir import Extension
from aizec.ir.nodes import *

from .symbols import *


class SymbolData(Extension):
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

    class AggFuncData:
        def __init__(self, symbol: VariableSymbol, namespace: NamespaceSymbol):
            self.symbol = symbol
            self.namespace = namespace

    def agg_func(self, node: AggFuncIR, set_to: AggFuncData = None) -> AggFuncData:
        return super().agg_func(node, set_to)

    class UnionData:
        def __init__(self, union_type: UnionTypeSymbol):
            self.union_type = union_type

    def union(self, node: UnionIR, set_to: UnionData = None) -> UnionData:
        return super().union(node, set_to)

    class StructData:
        def __init__(self, struct_type: StructTypeSymbol):
            self.struct_type = struct_type

    def struct(self, node: StructIR, set_to: StructData = None) -> StructData:
        return super().struct(node, set_to)

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

    class IsData:
        def __init__(self, union_type: Optional[UnionTypeSymbol], to_variant: UnionVariantTypeSymbol):
            self.union_type = union_type
            self.variant = to_variant

    def is_(self, node: IsIR, set_to: IsData = None) -> IsData:
        return super().is_(node, set_to)

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

    class MethodCallData:
        def __init__(self, func: VariableSymbol):
            self.func = func

    def method_call(self, node: MethodCallIR, set_to: MethodCallData = None) -> MethodCallData:
        return super().method_call(node, set_to)

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
        def __init__(self, agg_type: Optional[AggTypeSymbol], index: Optional[int], is_method: Optional[bool], func: Optional[VariableSymbol]):
            self.agg_type = agg_type
            self.index = index
            self.is_method = is_method
            self.func = func

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

    class CastIntData:
        def __init__(self, from_bits: int, to_bits: int, is_signed: bool):
            self.from_bits = from_bits
            self.to_bits = to_bits
            self.is_signed = is_signed

    def cast_int(self, node: CastIntIR, set_to: CastIntData = None) -> CastIntData:
        return super().cast_int(node, set_to)

    class CastUnionData:
        def __init__(self, from_variant: UnionVariantTypeSymbol, to_union: UnionTypeSymbol):
            self.from_variant = from_variant
            self.to_union = to_union

    def cast_union(self, node: CastUnionIR, set_to: CastUnionData = None) -> CastUnionData:
        return super().cast_union(node, set_to)

    class LambdaData:
        def __init__(self, value: VariableSymbol, type: FunctionTypeSymbol, namespace: NamespaceSymbol):
            self.value = value
            self.type = type
            self.namespace = namespace

    def lambda_(self, node: LambdaIR, set_to: LambdaData = None) -> LambdaData:
        return super().lambda_(node, set_to)

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
