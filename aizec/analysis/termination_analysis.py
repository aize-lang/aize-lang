from __future__ import annotations

from aizec.common import *
from aizec.aize_common import AizeMessage, Reporter, MessageHandler, ErrorLevel, Position

from aizec.ir import *
from aizec.ir_pass import IRTreePass, IRPassSequence, PassesRegister, PassAlias

from .symbol_data import SymbolData
from .symbols import *
from .default_analysis import DefaultPasses


class MangleNames(IRTreePass):
    def __init__(self, ir: IR):
        super().__init__(ir)

        self.symbols = self.get_ext(SymbolData)

        self.source_nums: Dict[Path, int] = {}

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {DefaultPasses}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {SymbolData}

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True

    def mangle_symbol(self, symbol: Symbol) -> str:
        if isinstance(symbol, TypeSymbol):
            return f"{self.mangle_symbol(symbol.namespace)}_T{len(symbol.name)}{symbol.name}"
        elif isinstance(symbol, VariableSymbol):
            return f"{self.mangle_symbol(symbol.namespace)}_V{len(symbol.name)}{symbol.name}"
        elif isinstance(symbol, NamespaceSymbol):
            if symbol.name.startswith("program"):
                return f"aize"
            elif symbol.name.startswith("source"):
                path = Path(symbol.name[6:].lstrip())
                if path in self.source_nums:
                    num = self.source_nums[path]
                else:
                    num = self.source_nums[path] = len(self.source_nums)
                return f"{self.mangle_symbol(symbol.namespace)}_S{num}"
            elif symbol.name.startswith("function"):
                func_name = symbol.name[6:].lstrip()
                return f"{self.mangle_symbol(symbol.namespace)}_F{len(func_name)}{func_name}"
            else:
                raise Exception(symbol)
        else:
            raise Exception(symbol)

    def visit_program(self, program: ProgramIR):
        for source in program.sources:
            self.visit_source(source)

    def visit_source(self, source: SourceIR):
        for top_level in source.top_levels:
            self.visit_top_level(top_level)

    def visit_function(self, func: FunctionIR):
        symbol = self.symbols.function(func).symbol
        mangled = self.mangle_symbol(symbol)
        func.name = mangled
