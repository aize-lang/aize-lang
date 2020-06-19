from __future__ import annotations

from aizec.common import *
from aizec.aize_common import Position

from aizec.ir.nodes import NodeIR


__all__ = [
    'Symbol',
    'VariableSymbol', 'ErroredVariableSymbol',
    'NamespaceSymbol', 'ErroredNamespaceSymbol',
    'TypeSymbol', 'IntTypeSymbol', 'FunctionTypeSymbol', 'ErroredTypeSymbol', 'StructTypeSymbol',
    'SymbolTable',
    'FailedLookupError', 'DuplicateSymbolError'
]


class SymbolError(Exception):
    pass


class DuplicateSymbolError(SymbolError):
    def __init__(self, new_symbol: Symbol, old_symbol: Symbol):
        self.new_symbol = new_symbol
        self.old_symbol = old_symbol


class FailedLookupError(SymbolError):
    def __init__(self, failed_name: str):
        self.failed_name = failed_name


class Symbol:
    """
    An object which describes the attributes of anything which can be referred to by a identifier
    Meant to be used with SymbolTables during Semantic Analysis to find out what refers to what

    Has 3 subclasses for each of the types of symbols:
        - `VariableSymbol` for variables
        - `TypeSymbol` for types
        - `NamespaceSymbol` for namespaces
    """

    def __init__(self, name: str, pos: Position):
        self.name: str = name
        """The name of this symbol, typically what it is called in its parent namespace"""

        self.namespace: Union[NamespaceSymbol, None] = None
        """The namespace this symbol is defined in, or None if it is the top-level namespace or unassigned"""

        self.position: Position = pos


class VariableSymbol(Symbol):
    def __init__(self, name: str, declarer: NodeIR, type: TypeSymbol, pos: Position):
        super().__init__(name, pos)

        self.declarer: NodeIR = declarer

        self.type: TypeSymbol = type
        """A reference to the symbol of the type of this variable"""


class ErroredVariableSymbol(VariableSymbol):
    def __init__(self, declarer: NodeIR, pos: Position):
        super().__init__("<errored value>", declarer, ErroredTypeSymbol(pos) ,pos)


class TypeSymbol(Symbol):
    def __init__(self, name: str, pos: Position):
        super().__init__(name, pos)

    def is_super_of(self, sub: TypeSymbol) -> bool:
        """Check if `other` is a subtype of this type"""
        return sub is self


class ErroredTypeSymbol(TypeSymbol):
    def __init__(self, pos: Position):
        super().__init__("<errored type>", pos)

    def is_super_of(self, sub: TypeSymbol) -> bool:
        return False


class StructTypeSymbol(TypeSymbol):
    def __init__(self, name: str, fields: Dict[str, Tuple[TypeSymbol, Position]], funcs: Dict[str, VariableSymbol], pos: Position):
        super().__init__(name, pos)

        self.fields = fields
        self.funcs = funcs

    def is_super_of(self, sub: TypeSymbol) -> bool:
        return isinstance(sub, StructTypeSymbol) and sub is self

    def __str__(self):
        return f"struct {self.name}"


class IntTypeSymbol(TypeSymbol):
    def __init__(self, name: str, signed: bool, bit_size: int, pos: Position):
        super().__init__(name, pos)
        self.is_signed = signed
        self.bit_size = bit_size

    def is_super_of(self, sub: TypeSymbol) -> bool:
        return isinstance(sub, IntTypeSymbol) and sub.is_signed == self.is_signed and sub.bit_size <= self.bit_size

    def __str__(self):
        return self.name


class FunctionTypeSymbol(TypeSymbol):
    def __init__(self, params: List[TypeSymbol], ret: TypeSymbol, pos: Position):
        super().__init__("<function type>", pos)
        self.params = params
        self.ret = ret

    def is_super_of(self, sub: TypeSymbol) -> bool:
        if not isinstance(sub, FunctionTypeSymbol):
            return False
        if len(self.params) != len(sub.params):
            return False
        for super_param, sub_param in zip(self.params, sub.params):
            # reverse the order to account for contravariance in parameters
            if not sub_param.is_super_of(super_param):
                return False
        if not self.ret.is_super_of(sub.ret):
            return False
        return True


class NamespaceSymbol(Symbol):
    def __init__(self, name: str, pos: Position):
        super().__init__(name, pos)

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

    def get_root(self) -> NamespaceSymbol:
        curr = self
        while curr is not None:
            curr = curr.namespace
        return curr

    def lookup_type(self, name: str, *, here: bool = False, nearest: bool = True) -> TypeSymbol:
        """
        Lookup a TypeSymbol with the given name in the current namespace, if it was marked with visible when it was defined.

        Args:
            name: The name of the TypeSymbol to lookup.
            here: If True, only lookup in this namespace, otherwise, recurse NamespaceSymbols.
            nearest: Whether to start looking from the top (earlier namespace) if False or this if True.

        Returns:
            The TypeSymbol which was found first with the specified parameters.

        Raises:
            FailedLookupError: If the name was not found.
        """
        if here:
            lookup_chain = [self]
        else:
            lookup_chain = self.parents(nearest_first=nearest)

        for namespace in lookup_chain:
            if name in namespace.type_symbols:
                return namespace.type_symbols[name]
        raise FailedLookupError(name)

    def lookup_value(self, name: str, *, here: bool = False, nearest: bool = True) -> VariableSymbol:
        if here:
            lookup_chain = [self]
        else:
            lookup_chain = self.parents(nearest_first=nearest)

        for namespace in lookup_chain:
            if name in namespace.value_symbols:
                return namespace.value_symbols[name]
        raise FailedLookupError(name)

    def lookup_namespace(self, name: str, *, here: bool = False, nearest: bool = True) -> NamespaceSymbol:
        """
        Lookup a NamespaceSymbol with the given name in the current namespace, if it was marked with visible when it was defined.

        Args:
            name: The name of the NamespaceSymbol to lookup.
            here: If True, only lookup in this namespace, otherwise, recurse NamespaceSymbols.
            nearest: Whether to start looking from the top (earlier namespace) if False or this if True.

        Returns:
            The NamespaceSymbol which was found first with the specified parameters.

        Raises:
            FailedLookupError: If the name was not found.
        """
        if here:
            lookup_chain = [self]
        else:
            lookup_chain = self.parents(nearest_first=nearest)

        for namespace in lookup_chain:
            if name in namespace.namespace_symbols:
                return namespace.namespace_symbols[name]
        raise FailedLookupError(name)

    def define_value(self, value: VariableSymbol, as_name: str = None, visible: bool = True):
        """
        Defines a variable in this namespace.

        Args:
            value: The variable to define.
            as_name: A name to define it as in this namespace (for lookups), if different from the value's.
            visible: If the value is visible to lookups.

        Raises:
            DuplicateSymbolError: If the name used by the variable is already used in this immediate namespace.
        """
        if as_name is None:
            as_name = value.name

        if visible:
            if as_name in self.value_symbols:
                raise DuplicateSymbolError(value, self.value_symbols[as_name])
            else:
                self.value_symbols[as_name] = value
        value.namespace = self

    def define_type(self, type: TypeSymbol, as_name: str = None, visible: bool = True):
        if as_name is None:
            as_name = type.name

        if visible:
            if as_name in self.type_symbols:
                raise DuplicateSymbolError(type, self.type_symbols[as_name])
            else:
                self.type_symbols[as_name] = type
        type.namespace = self

    def define_namespace(self, namespace: NamespaceSymbol, as_name: str = None, visible: bool = True, is_parent: bool = True):
        if as_name is None:
            as_name = namespace.name

        if visible:
            if as_name in self.namespace_symbols:
                raise DuplicateSymbolError(namespace, self.namespace_symbols[as_name])
            else:
                self.namespace_symbols[as_name] = namespace
        if is_parent:
            namespace.namespace = self

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.name}', {self.position})"


class ErroredNamespaceSymbol(NamespaceSymbol):
    def __init__(self, pos: Position):
        super().__init__("<errored>", pos)

    def define_value(self, value: VariableSymbol, as_name: str = None, visible: bool = True):
        raise NotImplementedError()

    def define_type(self, type: TypeSymbol, as_name: str = None, visible: bool = True):
        raise NotImplementedError()

    def define_namespace(self, namespace: NamespaceSymbol, as_name: str = None, visible: bool = True, as_parent: bool = True):
        raise NotImplementedError()

    def __repr__(self):
        return f"{self.__class__.__name__}()"


class SymbolTable:
    def __init__(self):
        self._visiting_stack: List[NamespaceSymbol] = []

    @contextmanager
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

    def lookup_value(self, name: str, *, here: bool = False, nearest: bool = True):
        return self.current_namespace.lookup_value(name, here=here, nearest=nearest)

    def define_value(self, value: VariableSymbol, as_name: str = None, visible: bool = True):
        self.current_namespace.define_value(value, as_name, visible)

    def define_type(self, type: TypeSymbol, as_name: str = None, visible: bool = True):
        self.current_namespace.define_type(type, as_name, visible)

    def define_namespace(self, namespace: NamespaceSymbol, as_name: str = None, visible: bool = True):
        self.current_namespace.define_namespace(namespace, as_name, visible)
