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

from zorg.buildbot.commands.ClangTestCommand import ClangTestCommand

def clang_not_ready(step):
    return step.build.getProperty("clang_CMakeLists") != "CMakeLists.txt"

def sample_needed_update(step):
    return step.build.getProperty("branch") == "release_30"

def not_triggered(step):
    return not (step.build.getProperty("scheduler") == 'cmake-llvm-x86_64-linux'
                or step.build.getProperty("scheduler") == 'sa-clang-x86_64-linux')

from buildbot import locks
centos5_lock = locks.SlaveLock("centos5_lock")
win7_git_lock = locks.SlaveLock("win7_git_lock")

# Factories
def AddGitLLVMClang(factory, isLLVM, isClang, repo, ref):
    factory.addStep(Git(repourl=repo,
                        reference=ref,
                        workdir='llvm-project'))
    factory.addStep(SetProperty(name="got_revision",
                                command=["git", "describe", "--tags"],
                                workdir="llvm-project",
                                property="got_revision"))
    factory.addStep(ShellCommand(command=["git",
                                          "submodule",
                                          "foreach",
                                          "git checkout -f; git clean -fx"],
                                 workdir="llvm-project"))
    if isLLVM:
        factory.addStep(SetProperty(name="llvm_submodule_isready",
                                    command=["git",
                                             "--git-dir", "llvm/.git",
                                             "ls-tree",
                                             "--name-only",
                                             "HEAD", "CMakeLists.txt"],
                                    workdir="llvm-project",
                                    flunkOnFailure=False,
                                    property="clang_CMakeLists"))
    factory.addStep(ShellCommand(command=["git",
                                          "submodule",
                                          "update",
                                          "--init",
                                          "--reference", ref,
                                          "llvm"],
                                 haltOnFailure = True,
                                 workdir="llvm-project"))
    if isClang:
        factory.addStep(ShellCommand(command=["ln",
                                              "-svf",
                                              "../../clang", "llvm/tools/."],
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
        factory.addStep(ShellCommand(command=["git",
                                              "submodule",
                                              "update",
                                              "--init",
                                              "--reference", ref,
                                              "clang"],
                                     haltOnFailure = True,
                                     workdir="llvm-project"))

def AddGitWin7(factory):
    factory.addStep(ShellCommand(name="git-fetch",
                                 command=["git",
                                          "--git-dir", "D:/llvm-project.git",
                                          "fetch", "--prune"],
                                 locks=[win7_git_lock.access('counting')],
                                 flunkOnFailure=False));
    factory.addStep(Git(name="update_llvm_project",
                        repourl='chapuni@192.168.1.193:/var/cache/llvm-project.git',
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

def AddCMake(factory, doStepIf=None):
    factory.addStep(ShellCommand(description="configuring CMake",
                                 descriptionDone="CMake",
                                 command=["/home/chapuni/BUILD/cmake-2.8.2/bin/cmake",
                                          "-DLLVM_TARGETS_TO_BUILD=all",
                                          "-DCMAKE_C_COMPILER=/usr/bin/gcc44",
                                          "-DCMAKE_CXX_COMPILER=/usr/bin/g++44",
                                          "-DLLVM_LIT_ARGS=-v -j4",
                                          "-DCMAKE_BUILD_TYPE=Release",
                                          "-DHAVE_NEARBYINTF=1",
                                          "../llvm-project/llvm"],
                                 doStepIf=doStepIf))

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

    # CentOS5(clang only)
    factory = BuildFactory()
    AddGitLLVMClang(factory, False, True,
                    '/var/cache/llvm-project.git',
                    '/var/cache/llvm-project.git')
    AddCMake(factory, clang_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j4", "-k", "clang-test.deps"],
            locks           = [centos5_lock.access('counting')],
            name            = 'build_clang'))
    factory.addStep(ClangTestCommand(
            name            = 'test_clang',
            locks           = [centos5_lock.access('counting')],
            command         = ["make", "-j4", "clang-test"],
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    yield BuilderConfig(name="cmake-clang-x86_64-linux",
                        slavenames=["centos5"],
                        mergeRequests=False,
                        factory=factory)

    # CentOS5(3stage)
    factory = BuildFactory()
    AddGitLLVMClang(factory, False, True,
                    '/var/cache/llvm-project.git',
                    '/var/cache/llvm-project.git')
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/builds"),
                                    flunkOnFailure=False))
    factory.addStep(ShellCommand(name="CMake",
                                 description="configuring CMake",
                                 descriptionDone="CMake",
                                 command=["/home/chapuni/BUILD/cmake-2.8.2/bin/cmake",
                                          WithProperties("-DCMAKE_INSTALL_PREFIX=%(workdir)s/builds/install/stage1"),
                                          "-DLLVM_TARGETS_TO_BUILD=X86",
                                          "-DCMAKE_C_COMPILER=/usr/bin/gcc44",
                                          "-DCMAKE_CXX_COMPILER=/usr/bin/g++44",
                                          "-DLLVM_LIT_ARGS=-v -j4",
                                          "-DCMAKE_BUILD_TYPE=Release",
                                          "-DHAVE_NEARBYINTF=1",
                                          "../llvm-project/llvm"]))
    factory.addStep(Compile(name="stage1_build",
                            command=["make", "-j4", "-l4.2", "-k"]))
    factory.addStep(ClangTestCommand(
            name            = 'stage1_test_llvm',
            command         = ["make", "-j4", "-k", "check"],
            locks           = [centos5_lock.access('counting')],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    factory.addStep(ClangTestCommand(
            name            = 'stage1_test_clang',
            command         = ["make", "-j4", "-k", "clang-test"],
            locks           = [centos5_lock.access('counting')],
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    factory.addStep(Compile(name="stage1_install",
                            command=["make", "install", "-k", "-j4"]))

    # stage 2
    factory.addStep(ShellCommand(command=[WithProperties("%(workdir)s/llvm-project/llvm/configure"),
                                          WithProperties("CC=%(workdir)s/builds/install/stage1/bin/clang -std=gnu89"),
                                          WithProperties("CXX=%(workdir)s/builds/install/stage1/bin/clang++"),
                                          WithProperties("--prefix=%(workdir)s/builds/install/stagen"),
                                          "--disable-timestamps",
                                          "--disable-assertions",
                                          "--enable-optimized"],
                                 name="configure_2",
                                 description="configuring",
                                 descriptionDone="Configure",
                                 workdir="builds/stagen"))
    factory.addStep(Compile(name="stage2_build",
                            command=["make", "VERBOSE=1", "-k", "-j4", "-l4.2"],
                            workdir="builds/stagen"))
    factory.addStep(ClangTestCommand(name="stage2_test_clang",
                         locks=[centos5_lock.access('counting')],
                         command=["make", "TESTARGS=-v -j4",
                                  "-C", "tools/clang/test"],
                         workdir="builds/stagen"))
    factory.addStep(ClangTestCommand(name="stage2_test_llvm",
                         locks=[centos5_lock.access('counting')],
                         command=["make", "LIT_ARGS=-v -j4",
                                  "check"],
                         workdir="builds/stagen"))
    factory.addStep(Compile(name="stage2_install",
                            command=["make", "VERBOSE=1", "install", "-j4"],
                            workdir="builds/stagen"))
    factory.addStep(ShellCommand(name="stage2_install_fix",
                                 command=["mv", "-v",
                                          "stagen",
                                          "stage2"],
                                 workdir="builds/install"))
    factory.addStep(ShellCommand(name="stage2_builddir_fix",
                                 command=["mv", "-v",
                                          "stagen",
                                          "stage2"],
                                 workdir="builds"))

    # stage 3
    factory.addStep(ShellCommand(command=[WithProperties("%(workdir)s/llvm-project/llvm/configure"),
                                          WithProperties("CC=%(workdir)s/builds/install/stage2/bin/clang -std=gnu89"),
                                          WithProperties("CXX=%(workdir)s/builds/install/stage2/bin/clang++"),
                                          WithProperties("--prefix=%(workdir)s/builds/install/stagen"),
                                          "--disable-timestamps",
                                          "--disable-assertions",
                                          "--enable-optimized"],
                                 name="configure_3",
                                 description="configuring",
                                 descriptionDone="Configure",
                                 workdir="builds/stagen"))
    factory.addStep(Compile(name="stage3_build",
                            command=["make", "VERBOSE=1", "-k", "-j4", "-l4.2"],
                            workdir="builds/stagen"))
    factory.addStep(ClangTestCommand(name="stage3_test_clang",
                         locks=[centos5_lock.access('counting')],
                         command=["make", "TESTARGS=-v -j4",
                                  "-C", "tools/clang/test"],
                         workdir="builds/stagen"))
    factory.addStep(ClangTestCommand(name="stage3_test_llvm",
                         locks=[centos5_lock.access('counting')],
                         command=["make", "LIT_ARGS=-v -j4",
                                  "check"],
                         workdir="builds/stagen"))
    factory.addStep(Compile(name="stage3_install",
                            command=["make", "VERBOSE=1", "install", "-j4"],
                            workdir="builds/stagen"))
    factory.addStep(ShellCommand(name="stage3_install_fix",
                                 command=["mv", "-v",
                                          "stagen",
                                          "stage3"],
                                 workdir="builds/install"))
    factory.addStep(ShellCommand(name="stage3_builddir_fix",
                                 command=["mv", "-v",
                                          "stagen",
                                          "stage3"],
                                 workdir="builds"))
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
                        factory=factory)

    # CentOS5(llvm-x86)
    factory = BuildFactory()
    AddGitLLVMClang(factory, True, False,
                    '/var/cache/llvm-project.git',
                    '/var/cache/llvm-project.git')
    AddCMake(factory, clang_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j4", "-k", "check.deps"],
            name            = 'build_llvm'))
    factory.addStep(ClangTestCommand(
            name            = 'test_llvm',
            command         = ["make", "-j4", "check"],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    yield BuilderConfig(name="cmake-llvm-x86_64-linux",
                        slavenames=["centos5"],
                        mergeRequests=False,
                        locks=[centos5_lock.access('counting')],
                        factory=factory)

    # Cygwin
    factory = BuildFactory()
    # check out the source
    AddGitLLVMClang(factory, False, True,
                    'chapuni@192.168.1.193:/var/cache/llvm-project.git',
                    '/cygdrive/d/llvm-project.git')
    PatchLLVM(factory, "llvm.patch")
    factory.addStep(ShellCommand(command=["../llvm-project/llvm/configure",
                                          "-C",
                                          "--enable-shared",
                                          "--enable-optimized"],
                                 doStepIf=clang_not_ready))
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
    factory.addStep(Compile(command=["make", "OPTIONAL_DIRS=Hello",
                                     "-C", "lib/Transforms"]))

    # XXX
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          "for x in Release*/bin; do mkdir xxx;mv -v $x/* xxx;cp -v xxx/* $x;rm -rf xxx; done"],
                                 workdir="build"))

    factory.addStep(ClangTestCommand(name="test_clang",
                         command=["make", "TESTARGS=-v -j1",
                                  "-C", "tools/clang/test"]))
    factory.addStep(ClangTestCommand(name="test_llvm",
                         command=["make", "LIT_ARGS=-v -j1",
                                  "check"]))
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
                                          "fetch", "origin"],
                                 flunkOnFailure=False));
    AddGitLLVMClang(factory, False, True,
                    'chapuni@192.168.1.193:/var/cache/llvm-project.git',
                    '/home/chapuni/llvm-project.git')
    factory.addStep(ShellCommand(command=["../llvm-project/llvm/configure",
                                          "-C",
                                          "--build=ppc-redhat-linux",
                                          "--enable-optimized"],
                                 doStepIf=clang_not_ready))
    factory.addStep(ShellCommand(command=["./config.status", "--recheck"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(ShellCommand(command=["./config.status"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(Compile(command=["make",
                                     "VERBOSE=1",
                                     "OPTIMIZE_OPTION=-O3 -UPPC",
                                     "-k",
                                     ]))
    factory.addStep(ShellCommand(name="test_clang",
                                 flunkOnFailure=False,
                                 warnOnWarnings=False,
                                 flunkOnWarnings=False,
                                 command=["make", "TESTARGS=-v",
                                          "-C", "tools/clang/test"]))
    factory.addStep(ClangTestCommand(name="test_llvm",
                         command=["make", "LIT_ARGS=-v",
                                  "check"]))
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
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          "PATH=/bin:$PATH PWD=/e/bb-win7/clang-i686-msys/build /e/bb-win7/clang-i686-msys/llvm-project/llvm/configure -C --enable-optimized"],
                                 doStepIf=clang_not_ready))
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          "./config.status --recheck"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(ShellCommand(command=["sh", "-c",
                                          "./config.status"],
                                 doStepIf=sample_needed_update,
                                 workdir="build/projects/sample"))
    factory.addStep(Compile(command=["make", "VERBOSE=1", "-k", "-j1"]))
    factory.addStep(ClangTestCommand(name="test_clang",
                         command=["make", "TESTARGS=-v -j1",
                                  "-C", "tools/clang/test"]))
    factory.addStep(ClangTestCommand(name="test_llvm",
                         command=["make", "LIT_ARGS=-v -j1",
                                  "check"]))
    yield BuilderConfig(name="clang-i686-msys",
                        mergeRequests=True,
                        slavenames=["win7"],
                        factory=factory)

    # cmake-msys
    factory = BuildFactory()
    AddGitWin7(factory)
#    PatchLLVM(factory, "llvm.patch")
    factory.addStep(ShellCommand(name="CMake",
                                 description="configuring CMake",
                                 descriptionDone="CMake",
                                 command=["cmake",
                                          "-GMSYS Makefiles",
                                          "-DCMAKE_BUILD_TYPE=Release",
                                          "-DCMAKE_COLOR_MAKEFILE=OFF",
                                          "-DLLVM_TARGETS_TO_BUILD=all",
                                          "-DLLVM_LIT_ARGS=-v -j1",
                                          "-DLLVM_LIT_TOOLS_DIR=D:/gnuwin32/bin",
                                          "../llvm-project/llvm"],
                                 doStepIf=clang_not_ready))
    factory.addStep(Compile(command=["make", "-j1", "-k"]))
    factory.addStep(ClangTestCommand(name="test_clang",
                         command=["make", "-j1", "clang-test"]))
    factory.addStep(ClangTestCommand(name="test_llvm",
                         command=["make", "-j1", "check"]))
    yield BuilderConfig(name="cmake-clang-i686-msys",
                        mergeRequests=True,
                        slavenames=["win7"],
                        factory=factory)

    # MSVC10
    factory = BuildFactory()
    AddGitWin7(factory)
#    PatchLLVM(factory, "llvm.patch")
    factory.addStep(ShellCommand(name="CMake",
                                 description="configuring CMake",
                                 descriptionDone="CMake",
                                 command=["cmake",
                                          "-GVisual Studio 10",
                                          "-DLLVM_TARGETS_TO_BUILD=all",
                                          "-DLLVM_LIT_ARGS=-v -j1",
                                          "-DLLVM_LIT_TOOLS_DIR=D:/gnuwin32/bin",
                                          "../llvm-project/llvm"],
                                 doStepIf=clang_not_ready))
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
    factory.addStep(ClangTestCommand(name="test_clang",
                         command=["c:/Python27/python.exe",
                                  "../llvm-project/llvm/utils/lit/lit.py",
                                  "--param", "build_config=Release",
                                  "--param", "build_mode=Release",
                                  "-v", "-j1",
                                  "tools/clang/test"]))
    factory.addStep(ClangTestCommand(name="test_llvm",
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
