from buildbot.plugins import schedulers, util
from buildbot.schedulers.basic import AnyBranchScheduler

from buildbot.changes.filter import ChangeFilter

import re

def filter_t(l, e): return filter(lambda x: re.search(e, x), l)
def filter_f(l, e): return filter(lambda x: not re.search(e, x), l)

def Tllvm(l): return filter_t(l, r'^llvm/')
def Tlld(l): return filter_t(l, r'^lld/')
def Tclang(l): return filter_t(l, r'^clang/')
def Tclang_extra(l): return filter_t(l, r'^clang-tools-extra/')
def Tdragonegg(l): return filter_t(l, r'^dragonegg/')
def Tlibcxx(l): return filter_t(l, r'^libcxx/')
def Tlibcxxabi(l): return filter_t(l, r'^libcxxabi/')
def Tcmake(l):
    return filter_t(l, r'^llvm/cmake/') + filter_t(l, r'/CMakeLists\.txt$')
def Tllvmlib(l):
    return filter_t(l, r'^llvm/(include|lib|tools|utils)/')
def Fllvmtest(l): return filter_f(l, r'^llvm/test/.+/')
def Flldtest(l): return filter_f(l, r'^lld/test/.+/')
def Fclangtest(l): return filter_f(l, r'^clang/test/.+/')
def Ftoolstest(l): return filter_f(l, r'^clang-tools-extra/test/.+/')
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

def filter_cmake_llvm_build(change):
    l = Fautoconf(Tllvm(getattr(change, "files")))
    if len(Tcmake(l)) > 0:
        return True
    return len(Fllvmtest(Fhtml(l))) > 0

change_llvm_build_master = ChangeFilter(filter_fn = filter_cmake_llvm_build,
                                  #branch=['master'],
                                  )

def filter_cmake_clang_build(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fclangtest(Fllvmtest(Fhtml(l)))) > 0

change_clang_build_master = ChangeFilter(filter_fn = filter_cmake_clang_build,
                                  #branch=['master'],
                                  )

def filter_all(change):
    l = Fhtml(getattr(change, "files"))
    return len(Tclang(l) + Tllvm(l)) > 0

change_llvmclang = ChangeFilter(filter_fn = filter_all)
change_llvmclang_release_38 = ChangeFilter(
    filter_fn = filter_all,
    branch=['release_38'],
    )

def filter_autoconf_llvmclang(change):
    l = Fcmake(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l)
    return len(Fhtml(l)) > 0

change_autoconf_llvmclang = ChangeFilter(
    filter_fn = filter_autoconf_llvmclang,
    branch=['release_38'],
    )

def filter_cmake_llvmclang(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l) + Tclang_extra(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fhtml(l)) > 0

change_cmake_llvmclang = ChangeFilter(filter_fn = filter_cmake_llvmclang)
change_cmake_llvmclang_release_38 = ChangeFilter(
    filter_fn = filter_cmake_llvmclang,
    branch=['release_38'],
    )

def filter_cmake_llvmclang_build(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tclang(l) + Tllvm(l) + Tclang_extra(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Ftoolstest(Fclangtest(Fllvmtest(Fhtml(l))))) > 0

change_cmake_llvmclang_build = ChangeFilter(filter_fn = filter_cmake_llvmclang_build)

def filter_cmake_lld_build(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tlld(l) + Tllvm(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Flldtest(Fllvmtest(Fhtml(l)))) > 0

change_lld_build_master = ChangeFilter(filter_fn = filter_cmake_lld_build,
                                   #branch=['master'],
                                   )

def filter_cmake_lld(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tlld(l) + Tllvm(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fllvmtest(Fhtml(l))) > 0

change_lld_master = ChangeFilter(filter_fn = filter_cmake_lld,
                                   #branch=['master'],
                                   )

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

def filter_cmake_dragonegg(change):
    l = Fautoconf(getattr(change, "files"))
    l = Tllvm(l) + Tdragonegg(l)
    if len(Tcmake(l)) > 0:
        return True
    return len(Fllvmtest(Fhtml(l))) > 0

change_dragonegg_master = ChangeFilter(filter_fn = filter_cmake_dragonegg,
                                   #branch=['master'],
                                   )

def filter_llvmclangtoolslldcxxabi(change):
    l = Fhtml(getattr(change, "files"))
    return len(Tclang(l) + Tclang_extra(l) + Tllvm(l) + Tlld(l) + Tlibcxx(l) + Tlibcxxabi(l)) > 0

change_llvmclangtoolslldcxxabi = ChangeFilter(filter_fn = filter_llvmclangtoolslldcxxabi)

# Configure the Schedulers, which decide how to react to incoming changes.  In this
# case, just kick off a 'runtests' build

def get_schedulers():
    llvm32RA = AnyBranchScheduler(
        name="s_llvm-i686-linux-RA",
        change_filter = change_llvm_build_master,
        treeStableTimer=1,
        builderNames=[
            "llvm-i686-linux-RA",
            ])
    yield llvm32RA

    clang32RA = AnyBranchScheduler(
        name="s_clang-i686-linux-RA",
        change_filter = change_clang_build_master,
        treeStableTimer=2,
        #upstreams=[llvm32RA],
        builderNames=[
            "clang-i686-linux-RA",
            ])
    yield clang32RA

    tools32RA = AnyBranchScheduler(
        name="s_clang-tools-i686-linux-RA",
        change_filter = change_cmake_llvmclang_build,
        treeStableTimer=3,
        #upstreams=[llvm32RA, clang32RA],
        builderNames=[
            "clang-tools-i686-linux-RA",
            ])
    yield tools32RA

    lld32RA = AnyBranchScheduler(
        name="s_lld-i686-linux-RA",
        change_filter = change_lld_build_master,
        treeStableTimer=2,
        #upstreams=[llvm32RA],
        builderNames=[
            "lld-i686-linux-RA",
            ])
    yield lld32RA

    llvm64R = AnyBranchScheduler(
        name="s_llvm-x86_64-linux-R",
        change_filter = change_llvm_build_master,
        treeStableTimer=4,
        #upstreams=[llvm32RA],
        builderNames=[
            "llvm-x86_64-linux-R",
            ])
    yield llvm64R

    clang64R = AnyBranchScheduler(
        name="s_clang-x86_64-linux-R",
        change_filter = change_clang_build_master,
        treeStableTimer=5,
        #upstreams=[llvm64R,clang32RA],
        builderNames=[
            "clang-x86_64-linux-R",
            ])
    yield clang64R

    tools64R = AnyBranchScheduler(
        name="s_clang-tools-x86_64-linux-R",
        change_filter = change_cmake_llvmclang_build,
        treeStableTimer=6,
        #upstreams=[llvm64R, clang64R, tools32RA],
        builderNames=[
            "clang-tools-x86_64-linux-R",
            ])
    yield tools64R

    lld64R = AnyBranchScheduler(
        name="s_lld-x86_64-linux-R",
        change_filter = change_lld_build_master,
        treeStableTimer=5,
        #upstreams=[llvm64R, lld32RA],
        builderNames=[
            "lld-x86_64-linux-R",
            ])
    yield lld64R

    testllvm32RA = AnyBranchScheduler(
        name="s_test-llvm-i686-linux-RA",
        change_filter = change_llvm_master,
        treeStableTimer=2,
        #upstreams=[llvm32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-llvm-i686-linux-RA",
            ])
    yield testllvm32RA

    testclang32RA = AnyBranchScheduler(
        name="s_test-clang-i686-linux-RA",
        change_filter = change_clang_master,
        treeStableTimer=3,
        #upstreams=[clang32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-i686-linux-RA",
            ])
    yield testclang32RA

    testtools32RA = AnyBranchScheduler(
        name="s_test-clang-tools-i686-linux-RA",
        change_filter = change_tools_master,
        treeStableTimer=4,
        #upstreams=[tools32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-tools-i686-linux-RA",
            ])
    yield testtools32RA

    testlld32RA = AnyBranchScheduler(
        name="s_test-lld-i686-linux-RA",
        change_filter = change_lld_master,
        treeStableTimer=3,
        #upstreams=[lld32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-lld-i686-linux-RA",
            ])
    yield testlld32RA

    testllvmmsc64RA = AnyBranchScheduler(
        name="s_test-llvm-msc-x64-on-i686-linux-RA",
        change_filter = change_llvm_master,
        treeStableTimer=10,
        #upstreams=[testllvm32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-llvm-msc-x64-on-i686-linux-RA",
            ])
    yield testllvmmsc64RA

    testclangmsc64RA = AnyBranchScheduler(
        name="s_test-clang-msc-x64-on-i686-linux-RA",
        change_filter = change_clang_master,
        treeStableTimer=10,
        #upstreams=[testclang32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-msc-x64-on-i686-linux-RA",
            ])
    yield testclangmsc64RA

    testtoolsmsc64RA = AnyBranchScheduler(
        name="s_test-clang-tools-msc-x64-on-i686-linux-RA",
        change_filter = change_tools_master,
        treeStableTimer=10,
        #upstreams=[testtools32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-tools-msc-x64-on-i686-linux-RA",
            ])
    yield testtoolsmsc64RA

    testllvm64R = AnyBranchScheduler(
        name="s_test-llvm-x86_64-linux-R",
        change_filter = change_llvm_master,
        treeStableTimer=5,
        #upstreams=[llvm64R,testllvm32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-llvm-x86_64-linux-R",
            ])
    yield testllvm64R

    testclang64R = AnyBranchScheduler(
        name="s_test-clang-x86_64-linux-R",
        change_filter = change_clang_master,
        treeStableTimer=6,
        #upstreams=[clang64R,testclang32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-x86_64-linux-R",
            ])
    yield testclang64R

    testtools64R = AnyBranchScheduler(
        name="s_test-clang-tools-x86_64-linux-R",
        change_filter = change_tools_master,
        treeStableTimer=7,
        #upstreams=[tools64R, testtools32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-tools-x86_64-linux-R",
            ])
    yield testtools64R

    testlld64R = AnyBranchScheduler(
        name="s_test-lld-x86_64-linux-R",
        change_filter = change_lld_master,
        treeStableTimer=6,
        #upstreams=[lld64R, testlld32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-lld-x86_64-linux-R",
            ])
    yield testlld64R

    testllvmmsc32R = AnyBranchScheduler(
        name="s_test-llvm-msc-x86-on-x86_64-linux-R",
        change_filter = change_llvm_master,
        treeStableTimer=10,
        #upstreams=[testllvm64R, testllvmmsc64RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-llvm-msc-x86-on-x86_64-linux-R",
            ])
    yield testllvmmsc32R

    testclangmsc32R = AnyBranchScheduler(
        name="s_test-clang-msc-x86-on-x86_64-linux-R",
        change_filter = change_clang_master,
        treeStableTimer=10,
        #upstreams=[testclang64R, testclangmsc64RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-msc-x86-on-x86_64-linux-R",
            ])
    yield testclangmsc32R

    testtoolsmsc32R = AnyBranchScheduler(
        name="s_test-clang-tools-msc-x86-on-x86_64-linux-R",
        change_filter = change_tools_master,
        treeStableTimer=10,
        #upstreams=[testtools64R, testtoolsmsc64RA],
        #waitAllUpstreams=False,
        builderNames=[
            "test-clang-tools-msc-x86-on-x86_64-linux-R",
            ])
    yield testtoolsmsc32R

    mingw32_linux = AnyBranchScheduler(
        name="s_i686-mingw32-RA-on-linux",
        change_filter = change_cmake_llvmclang_build,
        #treeStableTimer=None,
        treeStableTimer=30,
        #upstreams=[llvm32RA, clang32RA, tools32RA],
        #waitAllUpstreams=False,
        builderNames=[
            "i686-mingw32-RA-on-linux",
            ])
    yield mingw32_linux

    bootstrap_i686_linux = AnyBranchScheduler(
        name="s_bootstrap-clang-libcxx-lld-i686-linux",
        change_filter = change_llvmclangtoolslldcxxabi,
        treeStableTimer=15 * 60,
        #upstreams=[testllvm64R, testclang64R, testlld64R],
        builderNames=[
            "bootstrap-clang-libcxx-lld-i686-linux",
            ])
    yield bootstrap_i686_linux

    clang_3stage_linux = AnyBranchScheduler(
        name="s_clang-3stage-x86_64-linux",
        change_filter = change_llvmclang,
        treeStableTimer=60 * 60,
        #upstreams=[testllvm64R,testclang64R,bootstrap_i686_linux],
        builderNames=[
            "clang-3stage-x86_64-linux",
            ])
    #yield clang_3stage_linux

    yield schedulers.ForceScheduler(
        name="force",
        builderNames=[
#            "ninja-clang-x64-mingw64-RA",
#            "ninja-clang-i686-msc19-R",
#            "msbuild-llvmclang-x64-msc19-DA",
            "clang-3stage-x86_64-linux",
            "i686-mingw32-RA-on-linux",

            "llvm-i686-linux-RA",
            "clang-i686-linux-RA",
            "clang-tools-i686-linux-RA",
            "lld-i686-linux-RA",
            "test-llvm-i686-linux-RA",
            "test-clang-i686-linux-RA",
            "test-clang-tools-i686-linux-RA",
            "test-lld-i686-linux-RA",
            "test-llvm-msc-x64-on-i686-linux-RA",
            "test-clang-msc-x64-on-i686-linux-RA",
            "test-clang-tools-msc-x64-on-i686-linux-RA",
            "llvm-x86_64-linux-R",
            "clang-x86_64-linux-R",
            "clang-tools-x86_64-linux-R",
            "lld-x86_64-linux-R",
            "test-llvm-x86_64-linux-R",
            "test-clang-x86_64-linux-R",
            "test-clang-tools-x86_64-linux-R",
            "test-lld-x86_64-linux-R",
            "test-llvm-msc-x86-on-x86_64-linux-R",
            "test-clang-msc-x86-on-x86_64-linux-R",
            "test-clang-tools-msc-x86-on-x86_64-linux-R",

            "bootstrap-clang-libcxx-lld-i686-linux",
            ],

        # branch=ChoiceStringParameter(name="branch",
        #                              choices=["main","devel"], default="main"),


        # will generate nothing in the form, but revision, repository,
        # and project are needed by buildbot scheduling system so we
        # need to pass a value ("")
        codebases=[
            util.CodebaseParameter(
                "",
                name="Main repository",
                # will generate a combo box
                branch=util.StringParameter(name="branch", default="master"),
                # will generate a text input
                reason=util.StringParameter(name="reason",label="reason:<br>",
                                       required=False, size=80),
                revision=util.StringParameter(name="revision", required=True,default=""),
                repository=util.FixedParameter(name="repository", default=""),
                project=util.FixedParameter(name="project", default="llvm-project"),
            ),
        ],

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
