# The 'builders' list defines the Builders, which tell Buildbot how to perform a build:
# what steps, and which slaves can execute them.  Note that any particular build will
# only take place on one slave.

from buildbot.process.factory import BuildFactory
from buildbot.steps.source import Git
from buildbot.steps.shell import WithProperties
from buildbot.steps.shell import ShellCommand
from buildbot.steps.shell import SetProperty
from buildbot.steps.shell import Compile
from buildbot.steps.shell import Test
from buildbot.steps.slave import RemoveDirectory

from buildbot.config import BuilderConfig

from zorg.buildbot.commands.LitTestCommand import LitTestCommand

def clang_not_ready(step):
    return step.build.getProperty("clang_CMakeLists") != "CMakeLists.txt"

def Makefile_not_ready(step):
    return step.build.getProperty("exists_Makefile") != "OK"

def sample_needed_update(step):
    return step.build.getProperty("branch") == "release_30"

def not_triggered(step):
    return not (step.build.getProperty("scheduler") == 'cmake-llvm-x86_64-linux'
                or step.build.getProperty("scheduler") == 'sa-clang-x86_64-linux')

from buildbot import locks
centos5_lock = locks.SlaveLock("centos5_lock")
win7_git_lock = locks.SlaveLock("win7_git_lock")

def CheckMakefile(factory, makefile="Makefile"):
    factory.addStep(SetProperty(name="Makefile_isready",
                                command=["sh", "-c",
                                         "test -e " + makefile + "&& echo OK"],
                                flunkOnFailure=False,
                                property="exists_Makefile"))

# Factories
def AddGitLLVMTree(factory, isClang, repo, ref):
    factory.addStep(Git(repourl=repo,
                        reference=ref,
                        timeout=3600,
                        workdir='llvm-project'))
    factory.addStep(SetProperty(name="got_revision",
                                command=["git", "describe", "--tags"],
                                workdir="llvm-project",
                                property="got_revision"))
    factory.addStep(ShellCommand(command=["git",
                                          "clean",
                                          "-fx"],
                                 workdir="llvm-project"))
    if isClang:
        factory.addStep(ShellCommand(command=["ln",
                                              "-svf",
                                              "../../clang", "llvm/tools/."],
                                     workdir="llvm-project"))

def AddGitWin7(factory):
    factory.addStep(ShellCommand(name="git-fetch",
                                 command=["git",
                                          "--git-dir", "D:/llvm-project.git",
                                          "fetch", "--prune"],
                                 locks=[win7_git_lock.access('counting')],
                                 flunkOnFailure=False));
    factory.addStep(Git(name="update_llvm_project",
                        repourl='chapuni@192.168.1.193:/var/cache/llvm-project-subm.git',
                        reference='d:/llvm-project.git',
                        workdir='llvm-project'))
    factory.addStep(SetProperty(name="got_revision",
                                command=["git", "describe", "--tags"],
                                workdir="llvm-project",
                                property="got_revision"))
    factory.addStep(ShellCommand(name="clean_submodule",
                                 command=["git",
                                          "submodule",
                                          "foreach",
                                          "git checkout -f; git clean -fx"],
                                 workdir="llvm-project"))
    factory.addStep(ShellCommand(name="update_submodule",
                                 command=["git",
                                          "submodule",
                                          "update"],
                                 haltOnFailure = True,
                                 workdir="llvm-project"))
    factory.addStep(SetProperty(name="llvm_submodule_isready",
                                command=["git",
                                         "--git-dir", "llvm/tools/clang/.git",
                                         "ls-tree",
                                         "--name-only",
                                         "HEAD", "CMakeLists.txt"],
                                workdir="llvm-project",
                                flunkOnFailure=False,
                                property="clang_CMakeLists"))
    factory.addStep(ShellCommand(name="llvm_submodule_update",
                                 command=["git",
                                          "submodule",
                                          "update",
                                          "--init",
                                          "--reference",
                                          "d:/llvm-project.git",
                                          "llvm"],
                                 haltOnFailure = True,
                                 doStepIf=clang_not_ready,
                                 workdir="llvm-project"))
    factory.addStep(ShellCommand(name="clang_git_clone",
                                 command=["git",
                                          "clone",
                                          "-n",
                                          "--reference",
                                          "d:/llvm-project.git",
                                          "http://llvm.org/git/clang.git"],
                                 doStepIf=clang_not_ready,
                                 workdir="llvm-project"))
    factory.addStep(ShellCommand(name="clang_git_worktree",
                                 command=["sh", "-c",
                                          "git config core.worktree $PWD/../llvm/tools/clang"],
                                 doStepIf=clang_not_ready,
                                 workdir="llvm-project/clang"))
    factory.addStep(ShellCommand(name="clang_mkdir",
                                 command=["mkdir", "clang"],
                                 doStepIf=clang_not_ready,
                                 flunkOnFailure=False,
                                 workdir="llvm-project/llvm/tools"))
    factory.addStep(ShellCommand(name="clang_gitdir",
                                 command=["sh", "-c",
                                          "echo gitdir: $PWD/clang/.git > llvm/tools/clang/.git"],
                                 doStepIf=clang_not_ready,
                                 workdir="llvm-project"))
    factory.addStep(ShellCommand(name="clang_git_reset",
                                 command=["git",
                                          "checkout",
                                          "-f"],
                                 doStepIf=clang_not_ready,
                                 workdir="llvm-project/clang"))
    factory.addStep(ShellCommand(name="clang_submodule_update",
                                 command=["git",
                                          "submodule",
                                          "update", "--init",
                                          "clang"],
                                 haltOnFailure = True,
                                 doStepIf=clang_not_ready,
                                 workdir="llvm-project"))

def AddCMake(factory, G,
             source="../llvm-project/llvm",
             prefix="install",
             doStepIf=True,
             **kwargs):
    cmd = ["cmake", "-G"+G]
    cmd.append(WithProperties("-DCMAKE_INSTALL_PREFIX=%(workdir)s/"+prefix))
    for i in sorted(kwargs.items()):
        cmd.append("-D%s=%s" % i)
    cmd.append(source)
    factory.addStep(ShellCommand(name="CMake",
                                 description="configuring CMake",
                                 descriptionDone="CMake",
                                 command=cmd,
                                 doStepIf=doStepIf))

def AddCMakeCentOS5(factory,
                    LLVM_TARGETS_TO_BUILD="all",
                    **kwargs):
    AddCMake(factory, "Unix Makefiles",
             CMAKE_COLOR_MAKEFILE="OFF",
             CMAKE_C_COMPILER="/usr/bin/gcc44",
             CMAKE_CXX_COMPILER="/usr/bin/g++44",
             CMAKE_BUILD_TYPE="Release",
             LLVM_TARGETS_TO_BUILD=LLVM_TARGETS_TO_BUILD,
             LLVM_LIT_ARGS="-v -j4",
             HAVE_NEARBYINTF=1,
             **kwargs)

def AddCMakeDOS(factory, G, **kwargs):
    AddCMake(factory, G,
             LLVM_TARGETS_TO_BUILD="all",
             LLVM_LIT_ARGS="-v -j1",
             LLVM_LIT_TOOLS_DIR="D:/gnuwin32/bin",
             **kwargs)

def BuildStageN(factory, n,
                root="builds"):
    instroot="%s/install" % root
    workdir="%s/stagen" % root
    tools="%s/stage%d/bin" % (instroot, n - 1)
    tmpinst="%s/stagen" % instroot
    factory.addStep(ShellCommand(
            command=[
                WithProperties("%(workdir)s/llvm-project/llvm/configure"),
                WithProperties("CC=%%(workdir)s/%s/clang -std=gnu89" % tools),
                WithProperties("CXX=%%(workdir)s/%s/clang++" % tools),
                WithProperties("--prefix=%%(workdir)s/%s" % tmpinst),
                "--disable-timestamps",
                "--disable-assertions",
                "--enable-optimized"],
            name="configure",
            description="configuring",
            descriptionDone="Configure",
            workdir=workdir))
    factory.addStep(Compile(
            name="build",
            command=["make", "VERBOSE=1", "-k", "-j4", "-l4.2"],
            workdir=workdir))
    factory.addStep(LitTestCommand(
            name="test_clang",
            locks=[centos5_lock.access('counting')],
            command=["make", "TESTARGS=-v -j4", "-C", "tools/clang/test"],
            workdir=workdir))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            locks=[centos5_lock.access('counting')],
            command=["make", "LIT_ARGS=-v -j4", "check"],
            workdir=workdir))
    factory.addStep(Compile(
            name="install",
            command=["make", "VERBOSE=1", "install", "-j4"],
            workdir=workdir))
    factory.addStep(ShellCommand(
            name="install_fix",
            command=[
                "mv", "-v",
                tmpinst,
                "%s/stage%d" % (instroot, n)],
            workdir="."))
    factory.addStep(ShellCommand(
            name="builddir_fix",
            command=[
                "mv", "-v",
                workdir,
                "%s/stage%d" % (root, n)],
            workdir="."))

def PatchLLVM(factory, name):
    factory.addStep(ShellCommand(descriptionDone="LLVM Local Patch",
                                 command=["sh", "-c",
                                          "patch -p1 -N < ../../" + name],
                                 flunkOnFailure=False,
                                 workdir="llvm-project/llvm"))
def PatchClang(factory, name):
    factory.addStep(ShellCommand(descriptionDone="Clang Local Patch",
                                 command=["sh", "-c",
                                          "patch -p1 -N < ../../../../" + name],
                                 flunkOnFailure=False,
                                 workdir="llvm-project/llvm/tools/clang"))

def get_builders():

    # CentOS5(llvm-x86)
    factory = BuildFactory()
    AddGitLLVMTree(factory, False,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    CheckMakefile(factory)
    AddCMakeCentOS5(factory, doStepIf=Makefile_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j4", "-k", "check.deps"],
            name            = 'build_llvm'))
    factory.addStep(LitTestCommand(
            name            = 'test_llvm',
            command         = ["make", "-j4", "check"],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    yield BuilderConfig(name="cmake-llvm-x86_64-linux",
                        slavenames=["centos5"],
                        mergeRequests=False,
                        locks=[centos5_lock.access('counting')],
                        env={'PATH': '/home/chapuni/BUILD/cmake-2.8.2/bin:${PATH}'},
                        factory=factory)

    # CentOS5(clang only)
    factory = BuildFactory()
    AddGitLLVMTree(factory, True,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    CheckMakefile(factory)
    AddCMakeCentOS5(factory, doStepIf=Makefile_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j4", "-k", "clang-test.deps"],
            locks           = [centos5_lock.access('counting')],
            name            = 'build_clang'))
    factory.addStep(LitTestCommand(
            name            = 'test_clang',
            locks           = [centos5_lock.access('counting')],
            command         = ["make", "-j4", "clang-test"],
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    yield BuilderConfig(name="cmake-clang-x86_64-linux",
                        slavenames=["centos5"],
                        mergeRequests=False,
                        env={'PATH': '/home/chapuni/BUILD/cmake-2.8.2/bin:${PATH}'},
                        factory=factory)

    # CentOS5(3stage)
    factory = BuildFactory()
    AddGitLLVMTree(factory, True,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/builds"),
                                    flunkOnFailure=False))
    AddCMakeCentOS5(factory,
                    LLVM_TARGETS_TO_BUILD="X86",
                    prefix="builds/install/stage1")
    factory.addStep(Compile(name="stage1_build",
                            command=["make", "-j4", "-l4.2", "-k"]))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_llvm',
            command         = ["make", "-j4", "-k", "check"],
            locks           = [centos5_lock.access('counting')],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_clang',
            command         = ["make", "-j4", "-k", "clang-test"],
            locks           = [centos5_lock.access('counting')],
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    factory.addStep(Compile(name="stage1_install",
                            command=["make", "install", "-k", "-j4"]))

    # stage 2
    BuildStageN(factory, 2)

    # stage 3
    BuildStageN(factory, 3)

    # Trail
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/last"),
                                    flunkOnFailure=False))
    factory.addStep(ShellCommand(name="save_builds",
                                 command=["mv", "-v",
                                          "builds",
                                          "last"],
                                 workdir="."))
    factory.addStep(ShellCommand(name="compare_23",
                                 description="Comparing",
                                 descriptionDone="Compare-2-3",
                                 command=["find",
                                          "bin",
                                          "-type", "f",
                                          "!", "-name", "llvm-config",
                                          "-exec",
                                          "cmp", "../stage2/{}", "{}", ";"],
                                 workdir="last/install/stage3"))
    yield BuilderConfig(name="clang-3stage-x86_64-linux",
                        slavenames=["centos5"],
                        mergeRequests=True,
                        env={'PATH': '/home/chapuni/BUILD/cmake-2.8.2/bin:${PATH}'},
                        factory=factory)

    # Cygwin
    factory = BuildFactory()
    # check out the source
    AddGitLLVMTree(factory, True,
                    'chapuni@192.168.1.193:/var/cache/llvm-project-tree.git',
                    '/cygdrive/d/llvm-project.git')
    CheckMakefile(factory)
    PatchLLVM(factory, "llvm.patch")
    factory.addStep(ShellCommand(command=["../llvm-project/llvm/configure",
                                          "-C",
                                          #"--enable-shared",
                                          "LIBS=/usr/lib/gcc/i686-pc-cygwin/4.3.4/libstdc++.a",
                                          "--enable-optimized"],
                                 doStepIf=Makefile_not_ready))
    factory.addStep(ShellCommand(command=["./config.status", "--recheck"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(ShellCommand(command=["./config.status"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(Compile(name="make_quick",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            command=["make", "VERBOSE=1", "-k", "-j8"]))
    factory.addStep(Compile(command=["make", "VERBOSE=1", "-k", "-j1"]))

    # Build plugin manually
    # factory.addStep(Compile(command=["make", "OPTIONAL_DIRS=Hello",
    #                                  "-C", "lib/Transforms"]))

    # XXX
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          "for x in Release*/bin; do mkdir xxx;mv -v $x/* xxx;cp -v xxx/* $x;rm -rf xxx; done"],
                                 workdir="build"))

    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "TESTARGS=-v -j1", "-C", "tools/clang/test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "LIT_ARGS=-v -j1", "check"]))
    yield BuilderConfig(name="clang-i686-cygwin",
                        mergeRequests=True,
                        slavenames=["cygwin"],
                        factory=factory)

    # PS3
    factory = BuildFactory()
    # check out the source
    factory.addStep(ShellCommand(name="git-fetch",
                                 command=["git",
                                          "--git-dir", "/home/chapuni/llvm-project.git",
                                          "fetch", "origin", "--prune"],
                                 timeout=3600,
                                 flunkOnFailure=False));
    AddGitLLVMTree(factory, True,
                   'chapuni@192.168.1.193:/var/cache/llvm-project-tree.git',
                   '/home/chapuni/llvm-project.git')
    CheckMakefile(factory)
    factory.addStep(ShellCommand(command=["../llvm-project/llvm/configure",
                                          "-C",
                                          "CC=ccache gcc",
                                          "CXX=ccache g++",
                                          "--enable-optimized",
                                          "--with-optimize-option=-O3 -UPPC",
                                          "--build=ppc-redhat-linux"],
                                  doStepIf=Makefile_not_ready))
    factory.addStep(ShellCommand(command=["./config.status", "--recheck"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(ShellCommand(command=["./config.status"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(Compile(command=["make",
                                     "VERBOSE=1",
                                     "-k",
                                     ]))
    factory.addStep(ShellCommand(name="test_clang",
                                 flunkOnFailure=False,
                                 warnOnWarnings=False,
                                 flunkOnWarnings=False,
                                 command=["make", "TESTARGS=-v",
                                          "-C", "tools/clang/test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "LIT_ARGS=-v", "check"]))
    yield BuilderConfig(name="clang-ppc-linux",
                        mergeRequests=True,
                        slavenames=["ps3-f12"],
                        factory=factory)

    # autoconf-msys
    factory = BuildFactory()
    AddGitWin7(factory)
    PatchLLVM(factory, "makefile.patch")
#    PatchLLVM(factory, "llvm.patch")
    PatchClang(factory, "clang.patch")
    factory.addStep(SetProperty(name="get_msys_path",
                                command=["sh", "-c", "PWD= sh pwd"],
                                workdir=".",
                                property="workdir_msys"))
    CheckMakefile(factory)
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          WithProperties("PATH=/bin:$PATH PWD=%(workdir_msys)s/build %(workdir_msys)s/llvm-project/llvm/configure -C --enable-optimized")],
                                 doStepIf=Makefile_not_ready))
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          "./config.status --recheck"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          "./config.status"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(Compile(command=["make", "VERBOSE=1", "-k", "-j1"]))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "TESTARGS=-v -j1", "-C", "tools/clang/test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "LIT_ARGS=-v -j1", "check"]))
    yield BuilderConfig(name="clang-i686-msys",
                        mergeRequests=True,
                        slavenames=["win7"],
                        factory=factory)

    # cmake-msys
    factory = BuildFactory()
    AddGitWin7(factory)
#    PatchLLVM(factory, "llvm.patch")
    CheckMakefile(factory)
    AddCMakeDOS(factory, "MSYS Makefiles",
                CMAKE_BUILD_TYPE="Release",
                CMAKE_COLOR_MAKEFILE="OFF",
                doStepIf=Makefile_not_ready)
    factory.addStep(Compile(command=["make", "-j1", "-k"]))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "-j1", "clang-test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "-j1", "check"]))
    yield BuilderConfig(name="cmake-clang-i686-msys",
                        mergeRequests=True,
                        slavenames=["win7"],
                        factory=factory)

    # MSVC10
    factory = BuildFactory()
    AddGitWin7(factory)
#    PatchLLVM(factory, "llvm.patch")
    CheckMakefile(factory, makefile="LLVM.sln")
    AddCMakeDOS(factory, "Visual Studio 10",
                doStepIf=Makefile_not_ready)
    factory.addStep(Compile(name="all_build",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            command=["c:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe",
                                     "-m",
                                     "-v:m",
                                     "-p:Configuration=Release",
                                     "LLVM.sln"]))
    factory.addStep(Compile(name="all_build_again",
                            command=["c:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe",
                                     "-m",
                                     "-v:m",
                                     "-p:Configuration=Release",
                                     "LLVM.sln"]))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["c:/Python27/python.exe",
                     "../llvm-project/llvm/utils/lit/lit.py",
                     "--param", "build_config=Release",
                     "--param", "build_mode=Release",
                     "-v", "-j1",
                     "tools/clang/test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["c:/Python27/python.exe",
                     "../llvm-project/llvm/utils/lit/lit.py",
                     "--param", "build_config=Release",
                     "--param", "build_mode=Release",
                     "-v", "-j1",
                     "test"]))
    yield BuilderConfig(name="cmake-clang-i686-msvc10",
                        mergeRequests=True,
                        slavenames=["win7"],
                        factory=factory)

#EOF
