from buildbot.schedulers.basic import AnyBranchScheduler
from buildbot.schedulers.forcesched import *

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
def Fhtml(l): return filter_f(l, r'\.(TXT|html|rst)(\.\w)?$')
def FGNUmake(l): return filter_f(l, r'/Makefile(\.\w+)?$')
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
        name="notquick1",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=90,
        builderNames=[
            "ninja-clang-i686-msc17-R",
            ])
    yield AnyBranchScheduler(
        name="notquick5",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=5 * 60,
        builderNames=[
            "cmake-clang-i686-mingw32",
            ])
    yield AnyBranchScheduler(
        name="notquick20",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=20 * 60,
        builderNames=[
            "cmake-clang-x64-msc16-R",
#            "cmake-clang-i686-msvc10",
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

    # yield AnyBranchScheduler(
    #     name="notquick_autoconf",
    #     change_filter = change_autoconf_llvmclang,
    #     treeStableTimer=5 * 60,
    #     builderNames=[
    #         "clang-ppc-linux",
    #         ])

    yield AnyBranchScheduler(
        name="stable_autoconf",
        change_filter = change_autoconf_llvmclang,
        treeStableTimer=60 * 60,
        builderNames=[
            "clang-3stage-cygwin",
            "clang-i686-msys",
            ])

    yield ForceScheduler(
        name="force",
        builderNames=[
            "cmake-clang-x86_64-linux",
            "cmake-clang-i686-mingw32",
            "ninja-clang-i686-msc17-R",
            "cmake-clang-x64-msc16-R",
#            "cmake-clang-i686-msvc10",
            "cmake-llvm-x86_64-linux",
            "clang-3stage-x86_64-linux",
#            "clang-ppc-linux",
            "clang-3stage-cygwin",
            "clang-i686-msys",
            ],

        # will generate a combo box
        branch=StringParameter(name="branch", default="master"),
        # branch=ChoiceStringParameter(name="branch",
        #                              choices=["main","devel"], default="main"),

        # will generate a text input
        reason=StringParameter(name="reason",label="reason:<br>",
                               required=False, size=80),

        # will generate nothing in the form, but revision, repository,
        # and project are needed by buildbot scheduling system so we
        # need to pass a value ("")
        revision=StringParameter(name="revision", required=True,default=""),
        repository=FixedParameter(name="repository", default=""),
        project=FixedParameter(name="project", default="llvm-project"),

        # in case you dont require authentication this will display
        # input for user to type his name
        # username=UserNameParameter(label="your name:<br>", size=80),

        # A completely customized property list.  The name of the
        # property is the name of the parameter
        # properties=[

        #     BooleanParameter(name="force_build_clean",
        #                      label="force a make clean", default=False),

        #     StringParameter(name="pull_url",
        #                     label="optionally give a public git pull url:<br>",
        #                     default="", size=80)
        #     ]
        )

#EOF
