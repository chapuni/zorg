from buildbot.schedulers.basic import AnyBranchScheduler

from buildbot.changes.filter import ChangeFilter

import re

def filter_t(l, e): return filter(lambda x: re.search(e, x), l)
def filter_f(l, e): return filter(lambda x: not re.search(e, x), l)

def Tllvm(l): return filter_t(l, r'^llvm/')
def Tclang(l): return filter_t(l, r'^clang/')
def Tcmake(l):
    return filter_t(l, r'^llvm/cmake/') + filter_t(l, r'/CMakeLists.txt$')
def Tllvmlib(l):
    return filter_t(l, r'^llvm/(include|lib|tools|utils)/')
def Fllvmtest(l): return filter_f(l, r'^llvm/test/.+/')
def Fhtml(l): return filter_f(l, r'\.html(\.\w)?$')

def filter_llvm(change):
    return len(Tllvm(getattr(change, "files"))) > 0

change_llvm = ChangeFilter(filter_fn = filter_llvm)

def filter_cmake_llvm(change):
    return len(Fhtml(Tllvm(getattr(change, "files")))) > 0

change_llvm_master = ChangeFilter(filter_fn = filter_cmake_llvm,
                                  branch=['master'])

def filter_llvmclang(change):
    l = Fhtml(getattr(change, "files"))
    return len(Tclang(l) + Tllvm(l)) > 0

def filter_cmake_llvmclang(change):
    l = getattr(change, "files")
    l = Tclang(l) + Tllvm(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fllvmtest(Fhtml(l))) > 0

change_llvmclang = ChangeFilter(filter_fn = filter_llvmclang)

change_llvmclang_master = ChangeFilter(filter_fn = filter_cmake_llvmclang,
                                       branch=['master'])

# Configure the Schedulers, which decide how to react to incoming changes.  In this
# case, just kick off a 'runtests' build

def get_schedulers():
    yield AnyBranchScheduler(
        name="quick-clang",
        change_filter = change_llvmclang_master,
        treeStableTimer=None,
        builderNames=[
            "cmake-clang-x86_64-linux",
            ])
    yield AnyBranchScheduler(
        name="notquick",
        change_filter = change_llvmclang,
        treeStableTimer=30,
        builderNames=["cmake-clang-i686-msvc10",
                      #"clang-3stage-cygwin",
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
        builderNames=["cmake-clang-i686-msys",
                      "clang-i686-msys",
                      "clang-3stage-cygwin",
                      "clang-ppc-linux",
                      "clang-3stage-x86_64-linux",
                      ])

#EOF
