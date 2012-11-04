from buildbot.schedulers.basic import AnyBranchScheduler

from buildbot.changes.filter import ChangeFilter

import re

def filter_t(l, e): return filter(lambda x: re.search(e, x), l)
def filter_f(l, e): return filter(lambda x: not re.search(e, x), l)

def Tllvm(l): return filter_t(l, r'^llvm/')
def Tclang(l): return filter_t(l, r'^clang/')
def Tclang_extra(l): return filter_t(l, r'^clang-tools-extra/')
def Tcmake(l):
    return filter_t(l, r'^llvm/cmake/') + filter_t(l, r'/CMakeLists\.txt$') + filter_t(l, r'/LLVMBuild\.txt$') + filter_t(l, r'^llvm/utils/llvm-build/')
def Tllvmlib(l):
    return filter_t(l, r'^llvm/(include|lib|tools|utils)/')
def Fllvmtest(l): return filter_f(l, r'^llvm/test/.+/')
def Fhtml(l): return filter_f(l, r'\.(html|rst)(\.\w)?$')
def FGNUmake(l): return filter_f(l, r'/Makefile(\.\w+)$')
def Fautoconf(l): return filter_f(FGNUmake(l), r'^llvm/autoconf/')
def Fcmakefiles(l): return filter_f(l, r'/CMakeLists\.txt$')
def Fcmake(l): return filter_f(Fcmakefiles(l), r'^llvm/cmake/')

#def filter_llvm(change):
#    return len(Tllvm(getattr(change, "files"))) > 0

#change_llvm = ChangeFilter(filter_fn = filter_llvm)

def filter_cmake_llvm(change):
    l = Fautoconf(Tllvm(getattr(change, "files")))
    if len(Tcmake(l)) > 0:
        return True
    return len(Fhtml(l)) > 0

change_llvm_master = ChangeFilter(filter_fn = filter_cmake_llvm,
                                  branch=['master'])

def filter_llvmclang(change):
    l = Fhtml(getattr(change, "files"))
    return len(Tclang(l) + Tllvm(l)) > 0

change_llvmclang = ChangeFilter(filter_fn = filter_llvmclang)

def filter_autoconf_llvmclang(change):
    l = Fcmake(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l)
    return len(Fhtml(l)) > 0

change_autoconf_llvmclang = ChangeFilter(filter_fn = filter_autoconf_llvmclang)

def filter_cmake_llvmclang(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l) + Tclang_extra(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fhtml(l)) > 0

change_cmake_llvmclang = ChangeFilter(filter_fn = filter_cmake_llvmclang)

def filter_cmake_clang(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l) + Tclang_extra(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fllvmtest(Fhtml(l))) > 0

change_clang_master = ChangeFilter(filter_fn = filter_cmake_clang,
                                       branch=['master'])

# Configure the Schedulers, which decide how to react to incoming changes.  In this
# case, just kick off a 'runtests' build

def get_schedulers():
    yield AnyBranchScheduler(
        name="quick-clang",
        change_filter = change_clang_master,
        treeStableTimer=None,
        builderNames=[
            "cmake-clang-x86_64-linux",
            ])
    yield AnyBranchScheduler(
        name="notquick",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=30,
        builderNames=[
            "cmake-clang-i686-mingw32",
            ])
    yield AnyBranchScheduler(
        name="notquick5",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=5 * 60,
        builderNames=[
            "cmake-clang-i686-msvc10",
#            "cmake-clang-i686-msvc9",
            ])
    yield AnyBranchScheduler(
        name="quick-llvm",
        change_filter = change_llvm_master,
        treeStableTimer=None,
        builderNames=[
            "cmake-llvm-x86_64-linux",
            ])
    yield AnyBranchScheduler(
        name="stable",
        change_filter = change_llvmclang,
        treeStableTimer=30 * 60,
        builderNames=[
            "clang-3stage-x86_64-linux",
            ])

    yield AnyBranchScheduler(
        name="stable_autoconf",
        change_filter = change_autoconf_llvmclang,
        treeStableTimer=60 * 60,
        builderNames=[
            "clang-3stage-cygwin",
            "clang-i686-msys",
            "clang-ppc-linux",
            ])

#EOF
