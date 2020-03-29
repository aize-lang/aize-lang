from __future__ import annotations

import contextlib
from typing import Union, Dict, List, TypeVar, Type, Literal, Any

from aizec.aize_ast import Node, PassData, Source
from aizec.aize_pass_data import PositionData
from aizec.aize_error import AizeMessage, ErrorHandler


class SymbolError(Exception):
    def __init__(self, arg):
        self.arg = arg


class Symbol:
    """
    An object which describes the attributes of anything which can be referred to by a identifier
    Meant to be used with SymbolTables during Semantic Analysis to find out what refers to what

    Has 3 subclasses for each of the types of symbols:
        - `VariableSymbol` for variables
        - `TypeSymbol` for types
        - `NamespaceSymbol` for namespaces
    """

    def __init__(self, name: str, node: Node):
        self.name: str = name
        """The name of this symbol, typically what it is called in its parent namespace"""

        self.namespace: Union[NamespaceSymbol, None] = None
        """The namespace this symbol is defined in, or None if it is the top-level namespace or unassigned"""

        self.node: Node = node
        """The node which defines/declares this symbol"""


class VariableSymbol(Symbol):
    def __init__(self, name: str, type: TypeSymbol, node: Node):
        super().__init__(name, node)

        self.type: TypeSymbol = type
        """A reference to the symbol of the type of this variable"""


class TypeSymbol(Symbol):
    def __init__(self, name: str, node: Node):
        super().__init__(name, node)


S = TypeVar('S', bound=Symbol)


class NameSymbols:
    def __init__(self, var: VariableSymbol = None, type: TypeSymbol = None, namespace: NamespaceSymbol = None):
        self.var_symbol = var
        self.type_symbol = type
        self.namespace_symbol = namespace

    @property
    def is_empty(self):
        return self.var_symbol is None and self.type_symbol is None and self.namespace_symbol is None

    def set(self, var: VariableSymbol = None, type: TypeSymbol = None, namespace: NamespaceSymbol = None):
        self.var_symbol = var
        self.type_symbol = type
        self.namespace_symbol = namespace

    def get_type(self, type: Type[S]) -> Union[S, None]:
        if type == VariableSymbol:
            return self.var_symbol
        elif type == TypeSymbol:
            return self.type_symbol
        elif type == NamespaceSymbol:
            return self.namespace_symbol
        else:
            raise ValueError(f"Unknown type: {type}")

    def set_type(self, type: Type[S], value: S):
        if type == VariableSymbol:
            self.var_symbol = value
        elif type == TypeSymbol:
            self.type_symbol = value
        elif type == NamespaceSymbol:
            self.namespace_symbol = value
        else:
            raise ValueError(f"Unknown type: {type}")


class NamespaceSymbol(Symbol):
    def __init__(self, name: str, symbols: Dict[str, NameSymbols], node: Node):
        super().__init__(name, node)

        self.symbols: Dict[str, NameSymbols] = symbols
        """A dict mapping str names to a record of the symbols it defines"""

    def parents(self, *, nearest_first: bool = True) -> List[NamespaceSymbol]:
        """Get a list of the parents of this namespace.

        Args:
            nearest_first: A flag deciding whether the nearer namespaces should be first or last. Defaults to True
                (this namespace first).

        Returns:
            A list of NamespaceSymbols where the closest are first if nearest_first is True.
        """
        parents = []
        curr = self
        while curr is not None:
            parents.append(curr)
            curr = curr.namespace
        if not nearest_first:
            parents.reverse()
        return parents

    def lookup_symbol(self, name: str, *, here: bool = False, nearest: bool = True) -> NameSymbols:
        """Find and return the NameSymbols record that matches.

        Finds the NameSymbols record associated with that name, or an empty one if it doesn't exist. If here is True,
        then the look up is only performed in this namespace, not recursing upwards. If nearest is True, then the look up
        finds the NameSymbols record that is closest to this namespace, or else it will start from the top namespace.

        Args:
            name: The name of the symbol as it was added to this namespace.
            here: A flag deciding whether to only check this namespace. Defaults to False (recurse upwards).
            nearest: A flag deciding whether to start from this namespace or the top namespace. Default to True (start here).

        Returns:
            The NameSymbols record that with the associated name, or an empty one if it doesn't exist.
        """

        if here:
            lookup_chain = [self]
        else:
            lookup_chain = self.parents(nearest_first=nearest)

        for namespace in lookup_chain:
            if name in namespace.symbols:
                return namespace.symbols[name]
        return NameSymbols()

    def declare(self, name: str) -> NameSymbols:
        if name in self.symbols and not self.symbols[name].is_empty:
            raise SymbolError(self.symbols[name])
        self.symbols[name] = NameSymbols()
        return self.symbols[name]

    # def define_symbol(self, name: str, symbol: Symbol):
    #     symbols = self.lookup_symbol(name, here=True)
    #
    #     if symbols.is_empty:
    #         self.symbols[name] = symbols
    #
    #     if symbols.get_type(type(symbol)) is None:
    #         symbols.set_type(type(symbol), symbol)
    #     else:
    #         raise SymbolError(symbols.get_type(type(symbol)))


class SymbolTable:
    def __init__(self):
        self._visiting_stack: List[NamespaceSymbol] = []

    @contextlib.contextmanager
    def enter(self, namespace: NamespaceSymbol):
        self._visiting_stack.append(namespace)
        yield namespace
        self._visiting_stack.pop()

    @property
    def current_namespace(self):
        if len(self._visiting_stack) > 0:
            return self._visiting_stack[-1]
        else:
            raise ValueError("Not inside a namespace yet")

    def define_node(self, node: Node, name: str, var: VariableSymbol = None, type: TypeSymbol = None, namespace: NamespaceSymbol = None):
        symbols = self.current_namespace.declare(name)
        symbols.set(var, type, namespace)
        symbol_data = SymbolData(var, type, namespace)
        node.add_data(symbol_data)

    # def define(self, symbol: Symbol, *, as_name: str = None) -> None:
    #     if as_name is None:
    #         as_name = symbol.name
    #     self.current_namespace.define_symbol(as_name, symbol)


class SymbolData(PassData):
    def __init__(self, var: VariableSymbol = None, type: TypeSymbol = None, namespace: NamespaceSymbol = None):
        super().__init__()

        self.var_symbol = var
        self.type_symbol = type
        self.namespace_symbol = namespace
