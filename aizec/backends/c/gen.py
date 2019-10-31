import subprocess
import os

from aizec.common.error import AizeError
from aizec.common.aize_ast import *
from aizec.common import *
from aizec.backends.c import _cgen as cgen


STD = Path(__file__).absolute().parent / "std"


C_STD = {
    'builtins': (STD / "aize_builtins.h", STD / "aize_builtins.c"),
    'aizeio': (STD / "aizeio.h", STD / "aizeio.c")
}


AIZE_BASE = cgen.PointerType(cgen.NameType('AizeBase'))


class CompilationError(AizeError):
    def __init__(self, msg: str):
        self.msg = msg

    def display(self, file: IO):
        file.write(f"{self.msg}.")


class CCompiler:
    name: str = None

    def call(self, args: List[str]):
        raise NotImplementedError()


class MinGW(CCompiler):
    name = "MinGW"

    @classmethod
    def exists(cls):
        if os.name == 'nt':
            for prg_dir in Path(r"C:\Program Files (x86)").iterdir():
                if prg_dir.name.startswith("mingw-w"):
                    return True
        return False

    @classmethod
    def create(cls, config: Config):
        for prg_dir in Path(r"C:\Program Files (x86)").iterdir():
            if prg_dir.name == "mingw-w64":
                versions = list(prg_dir.iterdir())
                if len(versions) > 1:
                    if "mingw" in config and Path(config["mingw"]).exists():
                        ver = Path(config["mingw"])
                    else:
                        print("Multiple versions of MinGW detected. Which would you like to use?")
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
                        config["mingw"] = str(ver)
                elif len(versions) == 1:
                    ver = versions[0]
                else:
                    raise CompilationError(f"MinGW folder exists ({prg_dir}) but no compilers in it")
                path = ver / "mingw32" / "bin"
                return cls(path)
        else:
            raise CompilationError(f"No MinGW installation found")

    def __init__(self, bin_path: Path):
        self.bin = bin_path

    def call(self, args: List[str]):
        os.environ["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        check = subprocess.run([str(self.bin / "gcc.exe")] + args, check=False)
        return check


class GCC(CCompiler):
    name = "gcc"

    @classmethod
    def exists(cls):
        if os.name == 'posix':
            check = subprocess.run(["gcc", "--version"], stdout=subprocess.PIPE)
            return check.returncode == 0
        return False

    @classmethod
    def create(cls, config: Config):
        return cls()

    def __init__(self):
        pass

    def call(self, args: List[str]):
        # os.environ["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        check = subprocess.run(["gcc"] + args, check=False)
        return check


class Clang(CCompiler):
    name = "clang"

    @classmethod
    def exists(cls):
        if os.name == 'posix':
            check = subprocess.run(["clang", "--version"], stdout=subprocess.PIPE)
            return check.returncode == 0
        return False

    @classmethod
    def create(cls, config: Config):
        return cls()

    def __init__(self):
        pass

    def call(self, args: List[str]):
        # os.environ["PATH"] = str(self.bin) + os.pathsep + os.environ["PATH"]
        check = subprocess.run(["clang"] + args, check=False)
        return check


class CGenerator:
    def __init__(self, header: IO, source: IO, debug: bool):
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
                generator = cls(header, source, **kwargs)
                tops = generator.visit_Program(tree)
                program = cgen.Program(tops, main_file)
                program.generate(main_file.name.replace(".", "_"), header, source)
        return main_file.with_suffix(".c"), main_file.with_suffix(".h"), generator

    @classmethod
    def available_compilers(cls):
        return [compiler for compiler in [MinGW, GCC, Clang] if compiler.exists()]

    @classmethod
    def find_c_compiler(cls, config):
        compilers = cls.available_compilers()
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
        if args.for_ != 'debug':
            call_args += ["-Wno-sequence-point"]
            call_args += ["-Wno-incompatible-pointer-types"]

        if args.for_ in ('debug', 'normal'):
            call_args += ["-O0"]
        else:
            call_args += ["-O3"]
        if args.for_ == 'debug':
            call_args += ['-g']

        call_args += [f"-o{args.out.as_posix()}"]
        call_args += [f"{source}"]
        call_args += [str(path) for path in gen.links]

        check = compiler.call(call_args)
        if args.delete_c:
            source.unlink()
            header.unlink()
        if check.returncode != 0:
            raise CompilationError(f"Compilation of generated C code failed (Exit Code {hex(check.returncode)})")

        if args.run:
            ret = subprocess.run(args.out.as_posix(), check=False)
            if ret.returncode == 0xc0000005:
                raise CompilationError(f"Running of generated executable failed (Segmentation Fault)")
            elif ret.returncode != 0:
                raise CompilationError(f"Running of generated executable failed ({hex(ret.returncode)})")

    def visit(self, obj):
        return getattr(self, "visit_"+obj.__class__.__name__)(obj)

    def visit_Program(self, obj: Program):
        tops = []

        for header, source in (C_STD[std] for std in obj.needed_std):
            self.links.append(source)
            tops.append(cgen.Include(header.as_posix()))
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
        if obj.base is None:
            attrs = {'base': cgen.StructType('AizeBase')}
        else:
            attrs = {'base': self.visit(obj.type.base)}
        attrs.update({attr.unique: self.visit(attr.type) for attr in obj.attrs.values()})
        cls_struct = cgen.Struct(obj.unique, attrs)

        vtable_items = [cgen.Ref(cgen.GetVar(meth.unique)) for meth in obj.methods.values()]
        vtable = cgen.GlobalArray(f"{obj.unique}_vtable", cgen.void_ptr(),
                                  len(vtable_items),
                                  cgen.ArrayInit(vtable_items))

        new_unique = obj.type.cls_namespace.get_name("new").unique
        new_attrs = {attr.unique: self.visit(attr.type) for attr in obj.attrs.values()}

        def set_attr(attr):
            return cgen.ExprStmt(cgen.SetArrow(cgen.GetVar("mem"), attr.unique, cgen.GetVar(attr.unique)))

        new_func = cgen.Function(new_unique, new_attrs, cls_ptr, [
            cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_enter"), [])),
            cgen.Declare(cls_ptr, "mem",
                         cgen.Call(cgen.GetVar("aize_mem_malloc"), [cgen.SizeOf(cls_struct.struct_type)])),
            cgen.ExprStmt(cgen.SetArrow(cgen.Cast(cgen.GetVar('mem'), AIZE_BASE), "vtable", cgen.GetVar(vtable.name))),
            *(set_attr(attr) for attr in obj.attrs.values()),
            cgen.ExprStmt(cgen.SetArrow(cgen.Cast(cgen.GetVar('mem'), AIZE_BASE), "ref_count", cgen.Constant(0))),
            cgen.Return(cgen.Call(cgen.GetVar('aize_mem_ret'), [cgen.GetVar("mem")])),
            # cgen.Return(cgen.GetVar("mem")),
        ])

        methods = []
        for meth in obj.methods.values():
            methods.append(self.visit(meth))

        return [cls_struct, new_func, *methods, vtable]

    def visit_ClassType(self, obj: ClassType):
        return cgen.PointerType(cgen.StructType(obj.structs))

    def visit_Method(self, obj: Method):
        body = []

        for i in range(obj.temp_count):
            body.append(cgen.Declare(cgen.void_ptr(), f"AT{i}", None))

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
            body.append(cgen.Declare(cgen.void_ptr(), f"AT{i}", None))

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
        return cgen.Block([self.visit(stmt) for stmt in obj.stmts])

    def visit_VarDecl(self, obj: VarDecl):
        return cgen.Declare(self.visit(obj.type), obj.unique, self.visit(obj.val))

    def visit_Return(self, obj: Return):
        if self.in_main_main:
            return cgen.Return(self.visit(obj.val))
        val = self.visit(obj.val)
        if isinstance(obj.val.ret, ClassType) and False:
            ret = cgen.Call(cgen.GetVar("aize_mem_ret"), [val])
            return cgen.Return(ret)
        else:
            exit_call = cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_exit"), []))
            return [exit_call, cgen.Return(val)]

    def visit_Call(self, obj: Call):
        if obj.method_call is not None:
            return self.visit(obj.method_call)
        return cgen.Call(self.visit(obj.left), [self.visit(arg) for arg in obj.args])

    def visit_MethodCall(self, obj: MethodCall):
        # TODO
        left = self.visit(obj.obj)
        left = cgen.SetVar(f"AT{obj.depth}", left)
        # noinspection PyTypeChecker
        left = cgen.Cast(left, AIZE_BASE)
        left = cgen.GetArrow(left, 'vtable')
        left = cgen.GetItem(left, obj.index)
        left = cgen.Cast(left, self.visit(obj.pointed.type))
        left = cgen.Call(left, [cgen.GetVar(f"AT{obj.depth}")] + [self.visit(arg) for arg in obj.args])
        return left

    def visit_LT(self, obj: LT):
        return cgen.BinOp(self.visit(obj.left), '<', self.visit(obj.right))

    def visit_Add(self, obj: Add):
        return cgen.BinOp(self.visit(obj.left), '+', self.visit(obj.right))

    def visit_Sub(self, obj: Sub):
        return cgen.BinOp(self.visit(obj.left), '-', self.visit(obj.right))

    def visit_GetVar(self, obj: GetVar):
        return cgen.GetVar(obj.ref.unique)

    def visit_SetVar(self, obj: SetVar):
        return cgen.SetVar(obj.ref.unique, self.visit(obj.val))

    def visit_GetAttr(self, obj: GetAttr):
        return cgen.GetArrow(self.visit(obj.left), obj.pointed.unique)

    def visit_SetAttr(self, obj: SetAttr):
        return cgen.SetArrow(self.visit(obj.left), obj.pointed.unique, self.visit(obj.val))

    def visit_Num(self, obj: Num):
        return cgen.Constant(obj.num)

    # TODO for this and SemAnal, Make expr visitors and stmt visitors sep
    #  OR
    #  Make GetNamespaceAttr expr only, and make something else for getting types

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
