from aizec.common import *
from aizec.aize_ast import *
from aizec.aize_error import AizeMessage
from aizec.aize_pass_data import NodePosition


# class SemanticError(AizeError):
#     def __init__(self, msg: str, node: Node):
#         self.msg = msg
#         self.node = node
#         self.node_pos = NodePosition.of(self.node)
#
#     def display(self, file: IO):
#         file.write(f"In {self.node_pos.source.get_name()}:\n")
#         file.write(f"Parsing Error: {self.msg}:\n")
#         file.write(self.node_pos.in_context())
