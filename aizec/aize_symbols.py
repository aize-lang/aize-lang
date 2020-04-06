from __future__ import annotations

import contextlib
from typing import *

from aizec.aize_ast import Node, PassData


class SymbolError(Exception):
    def __init__(self, data: Any):
        self.data = data


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


class NamespaceSymbol(Symbol):
    def __init__(self, name: str, node: Node):
        super().__init__(name, node)

        self.value_symbols: Dict[str, VariableSymbol] = {}
        self.type_symbols: Dict[str, TypeSymbol] = {}
        self.namespace_symbols: Dict[str, NamespaceSymbol] = {}

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

    def lookup_type(self, name: str, *, here: bool = False, nearest: bool = True) -> TypeSymbol:
        if here:
            lookup_chain = [self]
        else:
            lookup_chain = self.parents(nearest_first=nearest)

        for namespace in lookup_chain:
            if name in namespace.type_symbols:
                return namespace.type_symbols[name]
        raise SymbolError(name)

    def define_value(self, value: VariableSymbol, as_name: str = None, visible: bool = True):
        if as_name is None:
            as_name = value.name

        if visible:
            if as_name in self.value_symbols:
                raise SymbolError(self.value_symbols[as_name])
            else:
                self.value_symbols[as_name] = value
        SymbolData.of_else(value.node).defined.append(value)
        value.namespace = self

    def define_type(self, type: TypeSymbol, as_name: str = None, visible: bool = True):
        if as_name is None:
            as_name = type.name

        if visible:
            if as_name in self.type_symbols:
                raise SymbolError(self.type_symbols[as_name])
            else:
                self.type_symbols[as_name] = type
        SymbolData.of_else(type.node).defined.append(type)
        type.namespace = self

    def define_namespace(self, namespace: NamespaceSymbol, as_name: str = None, visible: bool = True, is_body: bool = False):
        if as_name is None:
            as_name = namespace.name

        if visible:
            if as_name in self.namespace_symbols:
                raise SymbolError(self.namespace_symbols[as_name])
            else:
                self.namespace_symbols[as_name] = namespace
        SymbolData.of_else(namespace.node).defined.append(namespace)
        namespace.namespace = self
        if is_body:
            BodyData.of_else(namespace.node).body_namespace = namespace


class SymbolTable:
    def __init__(self):
        self._visiting_stack: List[NamespaceSymbol] = []

    @contextlib.contextmanager
    def enter(self, namespace: Union[NamespaceSymbol, None]):
        if namespace is None:
            yield namespace
        else:
            self._visiting_stack.append(namespace)
            yield namespace
            self._visiting_stack.pop()

    @property
    def current_namespace(self):
        if len(self._visiting_stack) > 0:
            return self._visiting_stack[-1]
        else:
            raise ValueError("Not inside a namespace yet")

    def lookup_type(self, name: str, *, here: bool = False, nearest: bool = True):
        return self.current_namespace.lookup_type(name, here=here, nearest=nearest)

    def define_value(self, value: VariableSymbol, as_name: str = None, visible: bool = True):
        self.current_namespace.define_value(value, as_name, visible)

    def define_type(self, type: TypeSymbol, as_name: str = None, visible: bool = True):
        self.current_namespace.define_type(type, as_name, visible)

    def define_namespace(self, namespace: NamespaceSymbol, as_name: str = None, visible: bool = True, is_body: bool = False):
        self.current_namespace.define_namespace(namespace, as_name, visible, is_body)

    def define_top(self, namespace: NamespaceSymbol, is_body: bool = False):
        SymbolData.of_else(namespace.node).defined.append(namespace)
        if is_body:
            BodyData.of_else(namespace.node).body_namespace = namespace


class SymbolData(PassData):
    def __init__(self):
        super().__init__()

        self.defined: List[Symbol] = []


class BodyData(PassData):
    def __init__(self):
        super().__init__()

        # noinspection PyTypeChecker
        self.body_namespace: NamespaceSymbol = None
