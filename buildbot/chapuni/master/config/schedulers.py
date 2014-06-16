from buildbot.schedulers.basic import AnyBranchScheduler
from buildbot.schedulers.forcesched import *

from buildbot.changes.filter import ChangeFilter

import re

def filter_t(l, e): return filter(lambda x: re.search(e, x), l)
def filter_f(l, e): return filter(lambda x: not re.search(e, x), l)

def Tllvm(l): return filter_t(l, r'^llvm/')
def Tclang(l): return filter_t(l, r'^clang/')
def Tclang_extra(l): return filter_t(l, r'^clang-tools-extra/')
def Tdragonegg(l): return filter_t(l, r'^dragonegg/')
def Tcmake(l):
    return filter_t(l, r'^llvm/cmake/') + filter_t(l, r'/CMakeLists\.txt$')
def Tllvmlib(l):
    return filter_t(l, r'^llvm/(include|lib|tools|utils)/')
def Fllvmtest(l): return filter_f(l, r'^llvm/test/.+/')
def Fclangtest(l): return filter_f(l, r'^clang/test/.+/')
def Fhtml(l): return filter_f(l, r'\.(TXT|html|rst)(\.\w)?$')
def FGNUmake(l): return filter_f(l, r'/Makefile(\.\w+)?$')
def Fautoconf(l): return filter_f(FGNUmake(l), r'^llvm/(autoconf/|config.*)')
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
                                  #branch=['master'],
                                  )

def filter_all(change):
    l = Fhtml(getattr(change, "files"))
    return len(Tclang(l) + Tllvm(l) + Tdragonegg(l)) > 0

change_llvmclang = ChangeFilter(filter_fn = filter_all)

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
    l = Tclang(l) + Tllvm(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fllvmtest(Fhtml(l))) > 0

change_clang_master = ChangeFilter(filter_fn = filter_cmake_clang,
                                   #branch=['master'],
                                   )

def filter_cmake_tools(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l) + Tclang_extra(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fclangtest(Fllvmtest(Fhtml(l)))) > 0

change_tools_master = ChangeFilter(filter_fn = filter_cmake_tools,
                                   #branch=['master'],
                                   )

# Configure the Schedulers, which decide how to react to incoming changes.  In this
# case, just kick off a 'runtests' build

def get_schedulers():
    llvm_linux = AnyBranchScheduler(
        name="s_cmake-llvm-x86_64-linux",
        change_filter = change_llvm_master,
        #treeStableTimer=None,
        treeStableTimer=2,
        builderNames=[
            "cmake-llvm-x86_64-linux",
            ])
    yield llvm_linux

    clang_linux = AnyBranchScheduler(
        name="s_cmake-clang-x86_64-linux",
        change_filter = change_clang_master,
        #treeStableTimer=None,
        treeStableTimer=2,
        upstreams=[llvm_linux],
        waitAllUpstreams=False,
        builderNames=[
            "cmake-clang-x86_64-linux",
            ])
    yield clang_linux

    tools_linux = AnyBranchScheduler(
        name="s_cmake-clang-tools-x86_64-linux",
        change_filter = change_tools_master,
        #treeStableTimer=None,
        treeStableTimer=2,
        upstreams=[llvm_linux, clang_linux],
        waitAllUpstreams=False,
        builderNames=[
            "cmake-clang-tools-x86_64-linux",
            ])
    yield tools_linux

    cyg_centos6 = AnyBranchScheduler(
        name="s_clang-i686-cygwin-RA-centos6",
        change_filter = change_autoconf_llvmclang,
        treeStableTimer=5,
        upstreams=[llvm_linux, clang_linux],
        builderNames=[
            "clang-i686-cygwin-RA-centos6",
            ])
    yield cyg_centos6

    x64_centos6 = AnyBranchScheduler(
        name="s_ninja-x64-msvc-RA-centos6",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=10,
        upstreams=[llvm_linux, clang_linux, tools_linux,cyg_centos6],
        builderNames=[
            "ninja-x64-msvc-RA-centos6",
            ])
    yield x64_centos6

    llvmclang_mingw64 = AnyBranchScheduler(
        name="s_cmake-clang-x64-mingw64",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=1 * 60,
        upstreams=[cyg_centos6, x64_centos6, llvm_linux, clang_linux, tools_linux],
        builderNames=[
            "ninja-clang-x64-mingw64-RA",
            ])
    yield llvmclang_mingw64

    llvmclang_msc17 = AnyBranchScheduler(
        name="s_ninja-clang-i686-msc17-R",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=2 * 60,
        upstreams=[llvmclang_mingw64],
        builderNames=[
            "ninja-clang-i686-msc17-R",
            ])
    yield llvmclang_msc17

    llvmclang_msc17_x64 = AnyBranchScheduler(
        name="s_msbuild-llvmclang-x64-msc17-DA",
        change_filter = change_cmake_llvmclang,
        treeStableTimer=30 * 60,
        upstreams=[llvmclang_msc17,llvmclang_mingw64,x64_centos6],
        builderNames=[
            "msbuild-llvmclang-x64-msc17-DA",
            ])
    yield llvmclang_msc17_x64

    # llvmclang_msc16_x64 = AnyBranchScheduler(
    #     name="s_cmake-clang-x64-msc16-R",
    #     change_filter = change_cmake_llvmclang,
    #     treeStableTimer=15 * 60,
    #     upstreams=[llvmclang_msc17],
    #     builderNames=[
    #         "cmake-clang-x64-msc16-R",
    #         ])
    # yield llvmclang_msc16_x64

    clang_3stage_linux = AnyBranchScheduler(
        name="s_clang-3stage-x86_64-linux",
        change_filter = change_llvmclang,
        treeStableTimer=15 * 60,
        upstreams=[llvm_linux, clang_linux,cyg_centos6],
        builderNames=[
            "clang-3stage-x86_64-linux",
            ])
    yield clang_3stage_linux

    clang_3stage_i686_linux = AnyBranchScheduler(
        name="s_clang-3stage-i686-linux",
        change_filter = change_llvmclang,
        treeStableTimer=20 * 60,
        upstreams=[llvm_linux, clang_linux,cyg_centos6,clang_3stage_linux],
        builderNames=[
            "clang-3stage-i686-linux",
            ])
    yield clang_3stage_i686_linux

    # yield AnyBranchScheduler(
    #     name="s_clang-i686-msys",
    #     change_filter = change_autoconf_llvmclang,
    #     treeStableTimer=60 * 60,
    #     upstreams=[
    #         cyg_centos6, llvmclang_mingw64,
    #         ],
    #     builderNames=[
    #         "clang-i686-msys",
    #         ])

    yield AnyBranchScheduler(
        name="s_clang-3stage-i686-cygwin",
        change_filter = change_autoconf_llvmclang,
        treeStableTimer=30 * 60,
        upstreams=[
            cyg_centos6,
            llvmclang_mingw64,
            clang_3stage_linux,
            clang_3stage_i686_linux,
            ],
        builderNames=[
            "clang-3stage-i686-cygwin",
            ])

    yield ForceScheduler(
        name="force",
        builderNames=[
            "cmake-clang-x86_64-linux",
            "cmake-clang-tools-x86_64-linux",
            "ninja-x64-msvc-RA-centos6",
            "clang-3stage-i686-linux",
#            "cmake-clang-i686-mingw32",
            "ninja-clang-x64-mingw64-RA",
            "ninja-clang-i686-msc17-R",
            "msbuild-llvmclang-x64-msc17-DA",
#            "cmake-clang-x64-msc16-R",
#            "cmake-clang-i686-msvc10",
            "cmake-llvm-x86_64-linux",
            "clang-3stage-x86_64-linux",
#            "clang-ppc-linux",
            "clang-3stage-i686-cygwin",
            "clang-i686-cygwin-RA-centos6",
#            "clang-i686-msys",
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
