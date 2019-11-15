from __future__ import annotations

import subprocess
import os

from aizec.common.error import AizeError
from aizec.common.sematics import SemanticError  # TODO actually use this in the right place
from aizec.common.aize_ast import *
from aizec.common import *
from aizec.backends.c import _cgen as cgen


STD = Path(__file__).absolute().parent / "std"


C_STD = {
    'builtins': (STD / "aize_builtins.h", STD / "aize_builtins.c"),
    'aizeio': (STD / "aizeio.h", STD / "aizeio.c")
}


AIZE_BASE = cgen.PointerType(cgen.NameType('AizeBase'))
AIZE_OBJECT_REF = cgen.NameType('AizeObjectRef')


class CompilationError(AizeError):
    def __init__(self, msg: str):
        self.msg = msg

    def display(self, file: IO):
        file.write(f"{self.msg}.")


class CCompiler:
    name: str = None

    @classmethod
    def create(cls, config: Config) -> Union[CCompiler, None]:
        raise NotImplementedError()

    def call(self, args: List[str]):
        raise NotImplementedError()


class MinGW(CCompiler):
    name = "MinGW"

    @classmethod
    def create(cls, config: Config):
        if os.name != 'nt':
            return None
        if "mingw" in config and (Path(config["mingw"]) / "gcc.exe").exists():
            ver = Path(config["mingw"])
        else:
            if "mingw" in config and not (Path(config["mingw"]) / "gcc.exe").exists():
                config.reset()
            versions = []
            for prg_dir in Path(r"C:\Program Files (x86)").iterdir():
                if prg_dir.name == "mingw-w64":
                    for mingw_ver in prg_dir.iterdir():
                        if (mingw_ver / "mingw32" / "bin" / "gcc.exe").exists():
                            versions.append(mingw_ver / "mingw32" / "bin")
            if Path(r"C:\Users\magil\MinGW\bin\gcc.exe").exists():
                versions.append(Path(r"C:\Users\magil\MinGW\bin"))

            if len(versions) == 1:
                ver = versions[0]
            elif len(versions) > 1:
                print("Multiple MinGW installations found. Which would you like to use?")
                for n, version in enumerate(versions):
                    print(f"    {n}  :  {version}")
                while True:
                    n_ver = input(">>> ")
                    try:
                        n_ver = int(n_ver)
                    except ValueError:
                        pass
                    else:
                        if 0 <= n_ver < len(versions):
                            break
                ver = versions[n_ver]
                config['mingw'] = str(ver)
            else:

                return None
        return cls(ver)

    def __init__(self, bin_path: Path):
        self.bin = bin_path

    def call(self, args: List[str]):
        os.environ["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        check = subprocess.run([str(self.bin / "gcc.exe")] + args, check=False)
        return check


class GCC(CCompiler):
    name = "gcc"

    @classmethod
    def create(cls, config: Config):
        if subprocess.run(["gcc", "--version"], stdout=subprocess.PIPE).returncode != 0:
            return cls()
        else:
            return None

    def __init__(self):
        pass

    def call(self, args: List[str]):
        # os.environ["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        check = subprocess.run(["gcc"] + args, check=False)
        # process = subprocess.Popen(["gcc"] + args)

        return check


class Clang(CCompiler):
    name = "clang"

    @classmethod
    def create(cls, config: Config):
        if subprocess.run(["clang", "--version"], stdout=subprocess.PIPE).returncode != 0:
            return cls()
        else:
            return None

    def __init__(self):
        pass

    def call(self, args: List[str]):
        # os.environ["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        check = subprocess.run(["clang"] + args, check=False)
        return check


class CGenerator:
    def __init__(self, program: Program, header: IO, source: IO, debug: bool):
        self.program = program

        self.header = header
        self.source = source

        self.debug = debug

        self.links: List[Path] = []
        self.main: NameDecl

        self.in_main_main = False

    @classmethod
    def gen(cls, tree: Program, **kwargs):
        main_file = next(file.path for file in tree.files if file.is_main).with_suffix("")
        with main_file.with_suffix(".h").open("w") as header:
            with main_file.with_suffix(".c").open("w") as source:
                generator = cls(tree, header, source, **kwargs)
                tops = generator.visit_Program(tree)
                program = cgen.Program(tops, main_file)
                program.generate(main_file.name.replace(".", "_"), header, source)
        return main_file.with_suffix(".c"), main_file.with_suffix(".h"), generator

    @classmethod
    def available_compilers(cls, config):
        avail = []
        for compiler in [MinGW, Clang, GCC]:
            comp = compiler.create(config)
            if comp is not None:
                avail.append(comp)
        return avail

    @classmethod
    def find_c_compiler(cls, config):
        compilers = cls.available_compilers(config)
        if len(compilers) > 1:
            if 'ccompiler' in config and config['ccompiler'] in [comp.name for comp in compilers]:
                compiler = next(comp for comp in compilers if comp.name == config['ccompiler'])
            else:
                print("Multiple C Compilers found. Which would you like to use?")
                for n, compiler in enumerate(compilers):
                    print(f"    {n}  :  {compiler.name}")
                while True:
                    n_ver = input(">>> ")
                    try:
                        n_ver = int(n_ver)
                    except ValueError:
                        pass
                    else:
                        if 0 <= n_ver < len(compilers):
                            break
                compiler = compilers[n_ver]
                config['ccompiler'] = compiler.name
        elif len(compilers) == 1:
            compiler = compilers[0]
        else:
            raise CompilationError("No C Compiler found")
        return compiler.create(config)

    @classmethod
    def compile(cls, tree: Program, args):
        compiler = cls.find_c_compiler(args.config)
        source, header, gen = cls.gen(tree, debug=False)  # args.for_ == 'debug')
        call_args = []
        call_args += ["-Wall"]
        # TODO clean up this section of options corellating to options (dict? Option classes?)
        if args.for_ in ('debug', 'normal', 'release'):
            call_args += ["-Wno-sequence-point"]
            call_args += ["-Wno-incompatible-pointer-types"]
            if args.for_ in ('normal', 'release'):
                call_args += ['-Wno-unused-variable']

        if args.for_ in ('compiler-debug', 'debug', 'normal'):
            call_args += ["-O0"]
        else:
            call_args += ["-O3"]
        if args.for_ in ('debug', 'compiler-debug'):
            call_args += ['-g']

        call_args += [f"-o{args.out.as_posix()}"]
        call_args += [f"{source}"]
        call_args += [str(path) for path in gen.links]

        check = compiler.call(call_args)
        if args.for_ == 'compiler-debug':
            AizeError.message(f"Called arguments: {' '.join(check.args)}")
        if args.delete_temp:
            source.unlink()
            header.unlink()
        if check.returncode != 0:
            raise CompilationError(f"Compilation of generated C code failed (Exit Code {hex(check.returncode)})")

        if args.run:
            ret = os.system(args.out.as_posix()) & 2**32-1
            if ret == 0xc0000005:
                raise CompilationError(f"Running of generated executable failed (Segmentation Fault)")
            elif ret != 0:
                raise CompilationError(f"Running of generated executable failed ({hex(ret)})")

            # ret = subprocess.Popen(args.out.as_posix())
            # ret.communicate("")
            # try:
            #     if ret.returncode == 0xc0000005:
            #         raise CompilationError(f"Running of generated executable failed (Segmentation Fault)")
            #     elif ret.returncode != 0:
            #         raise CompilationError(f"Running of generated executable failed ({hex(ret.returncode)})")
            # finally:
            #     ret.terminate()

    @classmethod
    def get_cls_ptr(cls, obj: cgen.Expression, cls_obj: ClassType):
        return cgen.Cast(cgen.GetAttr(obj, 'obj'), cgen.PointerType(cgen.StructType(cls_obj.structs)))

    @classmethod
    def ensure_cls(cls, obj: Expr):
        if isinstance(obj.ret, ClassType):
            return obj.ret
        else:
            raise SemanticError("Expected a Class", obj)

    def visit(self, obj):
        return getattr(self, "visit_"+obj.__class__.__name__)(obj)

    def visit_Program(self, obj: Program):
        tops = []

        for header, source in (C_STD[std] for std in obj.needed_std):
            self.links.append(source)
            tops.append(cgen.Include(header.as_posix()))

        cls_enum = cgen.Enum("AizeClasses", [cls.structs.upper() for cls in obj.classes])
        tops.append(cls_enum)
        for file in obj.files:
            tops.extend(self.visit(file))
        return tops

    def visit_File(self, obj: File):
        tops = []
        for top in obj.tops:
            ret = self.visit(top)
            if isinstance(ret, (list, tuple)):
                tops.extend(ret)
            elif ret is not None:
                tops.append(ret)
        return tops

    def visit_NativeImport(self, obj: NativeImport):
        pass

    def visit_Import(self, obj: Import):
        pass

    def visit_Class(self, obj: Class):
        # TODO when types are a thing, a mechanism to add that to main?
        cls_ptr = self.visit(obj.type)
        attrs = {}
        attrs.update({attr.unique: self.visit(attr.type) for attr in obj.attrs.values()})
        cls_struct = cgen.Struct(obj.unique, attrs)

        implementers = {}
        owned_methods = []
        methods = {}
        for n, meth_proto in enumerate(obj.methods.values()):
            meth = obj.type.get_method(meth_proto.name)
            if meth.owner is obj.type:
                methods[str(len(owned_methods))] = cgen.Ref(cgen.GetVar(meth.unique))
                owned_methods.append(meth_proto)
        implementers[obj.type.structs.upper()] = cgen.ArrayInit(methods)
        ttable = cgen.GlobalArray(f"{obj.unique}_ttable", cgen.void_ptr(),
                                  (len(self.program.classes), len(owned_methods)),
                                  cgen.ArrayInit(implementers))

        # ttable = cgen.GlobalArray(f"{obj.unique}_ttable", cgen.void_ptr(),
        #                           (len(self.program.classes), len(obj.methods)),
        #                           cgen.ArrayInit({cls.structs.upper(): cgen.ArrayInit({str(n): cgen.Ref(cgen.GetVar(meth.unique))
        #                                                               for n, meth in enumerate(cls.methods.values())})
        #                                           for cls in [obj.type, *obj.type.children]})
        #                           )

        new_unique = obj.type.cls_namespace.get_name("new").unique
        new_attrs = {attr.unique: self.visit(attr.type) for attr in obj.attrs.values()}

        def set_attr(attr):
            return cgen.ExprStmt(cgen.SetArrow(self.get_cls_ptr(cgen.GetVar('mem'), obj.type), attr.unique,
                                               cgen.GetVar(attr.unique)))

        new_func = cgen.Function(new_unique, new_attrs, cls_ptr, [
            cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_enter"), [])),
            cgen.Declare(cls_ptr, "mem",
                         cgen.StructInit([cgen.Call(cgen.GetVar("aize_mem_malloc"),
                                                   [cgen.SizeOf(cls_struct.struct_type)]),
                                         cgen.GetVar(cls_struct.name.upper())
                                         ])),
            # cgen.ExprStmt(cgen.SetAttr(cgen.GetVar('mem'), "vtable", )),
            *(set_attr(attr) for attr in obj.attrs.values()),
            cgen.ExprStmt(cgen.SetArrow(cgen.GetAttr(cgen.GetVar('mem'), 'obj'), "ref_count", cgen.Constant(0))),
            cgen.Return(cgen.Call(cgen.GetVar('aize_mem_ret'), [cgen.GetVar("mem")])),
            # cgen.Return(cgen.GetVar("mem")),
        ])

        methods = []
        for meth in obj.methods.values():
            methods.append(self.visit(meth))

        return [cls_struct, new_func, *methods, ttable]

    def visit_Trait(self, obj: Trait):
        # TODO when types are a thing, a mechanism to add that to main?

        implementers = {}
        for cls in obj.type.iter_children():
            methods = {}
            for n, meth_proto in enumerate(obj.methods.values()):
                meth = cls.get_method(meth_proto.name)
                if meth.owner is obj.type:
                    methods[str(n)] = cgen.Ref(cgen.GetVar(meth.unique))
            implementers[cls.structs.upper()] = cgen.ArrayInit(methods)
        ttable = cgen.GlobalArray(f"{obj.unique}_ttable", cgen.void_ptr(),
                                  (len(self.program.classes), len(obj.methods)),
                                  cgen.ArrayInit(implementers))


        # ttable = cgen.GlobalArray(f"{obj.unique}_ttable", cgen.void_ptr(),
        #                           (len(self.program.classes), len(obj.methods)),
        #                           cgen.ArrayInit(
        #                               {cls.structs.upper(): cgen.ArrayInit({str(n): cgen.Ref(cgen.GetVar(meth.unique))
        #                                                                     for n, meth in
        #                                                                     enumerate(cls.methods.values())})
        #                                for cls in obj.type.iter_children()})
        #                           )

        methods = []
        for meth in obj.methods.values():
            if meth.body is not None:
                methods.append(self.visit(meth))

        return [*methods, ttable]

    def visit_ClassType(self, obj: ClassType):
        # return cgen.PointerType(cgen.StructType(obj.structs))
        # TODO Make specific types which replace the AizeBase* with their own class for more optimizations
        return AIZE_OBJECT_REF

    def visit_TraitType(self, obj: TraitType):
        return AIZE_OBJECT_REF

    def visit_Method(self, obj: Method):
        body = []

        for i in range(obj.temp_count):
            body.append(cgen.Declare(AIZE_OBJECT_REF, f"AT{i}", None))

        body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_enter"), [])))
        self.in_main_main = False

        for stmt in obj.body:
            ret = self.visit(stmt)
            if self.debug:
                body.append(cgen.Comment(f"{stmt}"))
                body.append(cgen.printf(str(stmt)))
            if isinstance(ret, (list, tuple)):
                body.extend(ret)
            elif ret is not None:
                body.append(ret)

        if len(obj.body) == 0 or not isinstance(obj.body[-1], Return):
            body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_exit"), [])))

        return cgen.Function(obj.unique,
                             {param.unique: self.visit(param.type) for param in obj.args},
                             self.visit(obj.type.ret),
                             body)

    def visit_Function(self, obj: Function):
        body = []

        for i in range(obj.temp_count):
            body.append(cgen.Declare(AIZE_OBJECT_REF, f"AT{i}", None))

        if obj.unique != 'main':
            body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_enter"), [])))
            self.in_main_main = False
        else:
            body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_init"), [])))
            self.in_main_main = True

        for stmt in obj.body:
            ret = self.visit(stmt)
            if self.debug:
                body.append(cgen.Comment(f"{stmt}"))
                body.append(cgen.printf(str(stmt)))
            if isinstance(ret, (list, tuple)):
                body.extend(ret)
            elif ret is not None:
                body.append(ret)

        if len(obj.body) == 0 or not isinstance(obj.body[-1], Return):
            body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_exit"), [])))

        return cgen.Function(obj.unique,
                             {param.unique: self.visit(param.type) for param in obj.args},
                             self.visit(obj.type.ret),
                             body)

    def visit_ExprStmt(self, obj: ExprStmt):
        return cgen.ExprStmt(self.visit(obj.expr))

    def visit_If(self, obj: If):
        return cgen.If(self.visit(obj.cond), self.visit(obj.then_stmt), self.visit(obj.else_stmt))

    def visit_While(self, obj: While):
        return cgen.While(self.visit(obj.cond), self.visit(obj.body))

    def visit_Block(self, obj: Block):
        body = []
        for stmt in obj.stmts:
            ret = self.visit(stmt)
            if isinstance(ret, (list, tuple)):
                body.extend(ret)
            elif ret is not None:
                body.append(ret)
        return cgen.Block(body)

    def visit_VarDecl(self, obj: VarDecl):
        return cgen.Declare(self.visit(obj.type), obj.unique, self.visit(obj.val))

    def visit_Return(self, obj: Return):
        if self.in_main_main:
            return cgen.Return(self.visit(obj.val))
        val = self.visit(obj.val)
        if isinstance(obj.val.ret, ClassType):
            ret = cgen.Call(cgen.GetVar("aize_mem_ret"), [val])
            return cgen.Return(ret)
        else:
            ret = cgen.Declare(self.visit(obj.val.ret), 'ATR', val)
            exit_call = cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_exit"), []))
            return [ret, exit_call, cgen.Return(cgen.GetVar('ATR'))]

    def visit_Call(self, obj: Call):
        if obj.method_call is not None:
            return self.visit(obj.method_call)
        return cgen.Call(self.visit(obj.left), [self.visit(arg) for arg in obj.args])

    def visit_MethodCall(self, obj: MethodCall):
        # TODO
        left = self.visit(obj.obj)
        left = cgen.SetVar(f"AT{obj.depth}", left)
        # noinspection PyTypeChecker
        left = cgen.GetAttr(left, 'typeid')
        left = cgen.GetItem(cgen.GetVar(obj.pointed.owner.ttable), left)
        left = cgen.GetItem(left, cgen.Constant(obj.index))
        left = cgen.Cast(left, self.visit(obj.pointed.type))
        left = cgen.Call(left, [cgen.GetVar(f"AT{obj.depth}")] + [self.visit(arg) for arg in obj.args])
        return left

    def visit_LT(self, obj: LT):
        return cgen.BinOp(self.visit(obj.left), '<', self.visit(obj.right))

    def visit_Add(self, obj: Add):
        return cgen.BinOp(self.visit(obj.left), '+', self.visit(obj.right))

    def visit_Sub(self, obj: Sub):
        return cgen.BinOp(self.visit(obj.left), '-', self.visit(obj.right))

    def visit_Div(self, obj: Div):
        return cgen.BinOp(self.visit(obj.left), '/', self.visit(obj.right))

    def visit_GetVar(self, obj: GetVar):
        return cgen.GetVar(obj.ref.unique)

    def visit_SetVar(self, obj: SetVar):
        return cgen.SetVar(obj.ref.unique, self.visit(obj.val))

    def visit_GetAttr(self, obj: GetAttr):
        cls: ClassType = self.ensure_cls(obj.left)
        return cgen.GetArrow(self.get_cls_ptr(self.visit(obj.left), cls), obj.pointed.unique)

    def visit_SetAttr(self, obj: SetAttr):
        cls: ClassType = self.ensure_cls(obj.left)
        return cgen.SetArrow(self.get_cls_ptr(self.visit(obj.left), cls), obj.pointed.unique, self.visit(obj.val))

    def visit_Num(self, obj: Num):
        return cgen.Constant(obj.num)

    def visit_GetNamespaceName(self, obj: GetNamespaceName):
        return cgen.GetVar(obj.pointed.unique)

    def visit_IntType(self, obj: IntType):
        return cgen.IntType()

    def visit_LongType(self, obj: LongType):
        return cgen.LongType()

    def visit_VoidType(self, obj: VoidType):
        return cgen.VoidType()

    def visit_FuncType(self, obj: FuncType):
        return cgen.FunctionType([self.visit(arg) for arg in obj.args], self.visit(obj.ret))
