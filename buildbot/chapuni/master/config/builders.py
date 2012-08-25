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
centos6_lock = locks.SlaveLock("centos6_lock")
win7_git_lock = locks.SlaveLock("win7_git_lock")
win7_cyg_lock = locks.MasterLock("win7_cyg_lock")

def CheckMakefile(factory, makefile="Makefile"):
    factory.addStep(SetProperty(name="Makefile_isready",
                                command=["sh", "-c",
                                         "test -e " + makefile + "&& echo OK"],
                                flunkOnFailure=False,
                                property="exists_Makefile"))

# Factories
def AddGitLLVMTree(factory, repo, ref):
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

def AddGitFetch(factory, ref, locks=[]):
    factory.addStep(ShellCommand(
            name="git-fetch",
            command=[
                "git",
                "--git-dir", ref,
                "fetch",
                "--prune"],
            locks=locks,
            flunkOnFailure=False));

def AddGitWin7(factory):
    AddGitFetch(
        factory,
        "D:/llvm-project.git",
        [win7_git_lock.access('counting')])
    AddGitLLVMTree(
        factory,
        'chapuni@192.168.1.199:/var/cache/llvm-project-tree.git',
        'D:/llvm-project.git')

def AddCMake(factory, G,
             source="../llvm-project/llvm",
             prefix="install",
             buildClang=True,
             doStepIf=True,
             **kwargs):
    cmd = ["cmake", "-G"+G]
    cmd.append(WithProperties("-DCMAKE_INSTALL_PREFIX=%(workdir)s/"+prefix))
    cmd.append("-DLLVM_BUILD_TESTS=ON")
    if buildClang:
        cmd.append("-DLLVM_CLANG_SOURCE_DIR=%s/../clang" % source)
        cmd.append("-DLLVM_EXTERNAL_CLANG_SOURCE_DIR=%s/../clang" % source)
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

def AddCMakeCentOS6(factory,
                    LLVM_TARGETS_TO_BUILD="all",
                    **kwargs):
    AddCMake(factory, "Unix Makefiles",
             CMAKE_COLOR_MAKEFILE="OFF",
             CMAKE_BUILD_TYPE="Release",
             LLVM_TARGETS_TO_BUILD=LLVM_TARGETS_TO_BUILD,
             LLVM_LIT_ARGS="-v",
             **kwargs)

def AddCMakeDOS(factory, G, **kwargs):
    AddCMake(factory, G,
             LLVM_TARGETS_TO_BUILD="all",
             LLVM_LIT_ARGS="-v",
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
                WithProperties("--with-clang-srcdir=%(workdir)s/llvm-project/clang"),
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
            command=["make", "TESTARGS=-v -j4", "-C", "tools/clang/test"],
            workdir=workdir))
    factory.addStep(LitTestCommand(
            name="test_llvm",
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

def BuildStageN8(factory, n,
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
                WithProperties("--with-clang-srcdir=%(workdir)s/llvm-project/clang"),
                "--disable-timestamps",
                "--disable-assertions",
                "--enable-optimized"],
            name="configure",
            description="configuring",
            descriptionDone="Configure",
            workdir=workdir))
    factory.addStep(Compile(
            name="build",
            command=["make", "VERBOSE=1", "-k", "-j8", "-l8.2"],
            workdir=workdir))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "TESTARGS=-v -j8", "-C", "tools/clang/test"],
            workdir=workdir))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "LIT_ARGS=-v -j8", "check"],
            workdir=workdir))
    factory.addStep(Compile(
            name="install",
            command=["make", "VERBOSE=1", "install", "-j8"],
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

def BuildStageNcyg(factory, n,
                root="builds"):
    instroot="%s/install" % root
    workdir="%s/stagen" % root
    tools="%s/stage%d/bin" % (instroot, n - 1)
    tmpinst="%s/stagen" % instroot
    factory.addStep(ShellCommand(
            command=[
                WithProperties("%(workdir)s/llvm-project/llvm/configure"),
                WithProperties("CC=%%(workdir)s/%s/clang" % tools),
                WithProperties("CXX=%%(workdir)s/%s/clang++" % tools),
                WithProperties("--prefix=%%(workdir)s/%s" % tmpinst),
                WithProperties("--with-clang-srcdir=%(workdir)s/llvm-project/clang"),
                "LIBS=-static",
                "--disable-timestamps",
                "--disable-assertions",
                "--enable-optimized"],
            name="configure",
            description="configuring",
            descriptionDone="Configure",
            workdir=workdir))
    factory.addStep(Compile(name="make_quick",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            locks = [win7_cyg_lock.access('exclusive')],
                            command=["make", "VERBOSE=1", "-k", "-j5"],
                            workdir=workdir))
    factory.addStep(Compile(name="make_quick_again",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            command=["make", "VERBOSE=1", "-k", "-j8"],
                            workdir=workdir))
    factory.addStep(Compile(command=["make", "VERBOSE=1", "-k", "-j1"],
                            workdir=workdir))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "TESTARGS=-v -j1", "-C", "tools/clang/test"],
            workdir=workdir))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "LIT_ARGS=-v -j1", "check"],
            workdir=workdir))
    factory.addStep(Compile(
            name="install",
            command=["make", "VERBOSE=1", "install", "-j1"],
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

def PatchLLVMClang(factory, name):
    factory.addStep(ShellCommand(descriptionDone="llvm-project Local Patch",
                                 command=["sh", "-c",
                                          "patch -p1 -N < ../" + name],
                                 flunkOnFailure=False,
                                 workdir="llvm-project"))

def BlobPre(factory):
    factory.addStep(ShellCommand(
            name="blob-prebuild-add",
            description="Adding prebuild blob",
            descriptionDone="Added prebuild blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "add", "-A", "--ignore-errors", "build",
                ],
            flunkOnFailure=False,
            alwaysRun=True,
            workdir=".",
            ))
    factory.addStep(ShellCommand(
            name="blob-prebuild-commit",
            description="Committing prebuild blob",
            descriptionDone="Committed prebuild-blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "commit",
                "-m",
                WithProperties("%(buildnumber)s-prebuild"),
                ],
            flunkOnFailure=False,
            alwaysRun=True,
            workdir=".",
            ))

def BlobPost(factory):
    factory.addStep(ShellCommand(
            command=[
                "chmod", "-R", "u+r",
                "build",
                ],
            flunkOnFailure=False,
            workdir="."))
    factory.addStep(ShellCommand(
            name="blob-add",
            description="Adding blob",
            descriptionDone="Added blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "add", "-A", "--ignore-errors", "build",
                ],
            flunkOnFailure=False,
            warnOnFailure=True,
            alwaysRun=True,
            workdir=".",
            ))
    factory.addStep(ShellCommand(
            name="blob-commit",
            description="Committing blob",
            descriptionDone="Committed blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "commit",
                "--allow-empty",
                "-m",
                WithProperties("%(buildnumber)s-%(got_revision)s"),
                ],
            flunkOnFailure=False,
            warnOnFailure=True,
            alwaysRun=True,
            workdir=".",
            ))

def BlobPre3(factory):
    factory.addStep(ShellCommand(
            name="blob-prebuild-add",
            description="Adding prebuild blob",
            descriptionDone="Added prebuild blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "add", "-A", "--ignore-errors",
                "build", "builds",
                ],
            flunkOnFailure=False,
            alwaysRun=True,
            workdir=".",
            ))
    factory.addStep(ShellCommand(
            name="blob-prebuild-commit",
            description="Committing prebuild blob",
            descriptionDone="Committed prebuild-blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "commit",
                "-m",
                WithProperties("%(buildnumber)s-prebuild"),
                ],
            flunkOnFailure=False,
            alwaysRun=True,
            workdir=".",
            ))

def BlobPost3(factory):
    factory.addStep(ShellCommand(
            command=[
                "chmod", "-Rf", "u+r",
                "build", "builds",
                ],
            flunkOnFailure=False,
            workdir="."))
    factory.addStep(ShellCommand(
            name="blob-add",
            description="Adding blob",
            descriptionDone="Added blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "add", "-A", "--ignore-errors", "build", "builds",
                ],
            flunkOnFailure=False,
            warnOnFailure=True,
            alwaysRun=True,
            workdir=".",
            ))
    factory.addStep(ShellCommand(
            name="blob-commit",
            description="Committing blob",
            descriptionDone="Committed blob",
            command=[
                "git", "--git-dir=blob.git", "--work-tree=.",
                "commit",
                "--allow-empty",
                "-m",
                WithProperties("%(buildnumber)s-%(got_revision)s"),
                ],
            flunkOnFailure=False,
            warnOnFailure=True,
            alwaysRun=True,
            workdir=".",
            ))

def get_builders():

    # CentOS5(llvm-x86)
    factory = BuildFactory()
    AddGitLLVMTree(factory,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    CheckMakefile(factory)
    AddCMakeCentOS5(factory, buildClang=False, doStepIf=Makefile_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j4", "-k"],
            name            = 'build_llvm'))
    factory.addStep(LitTestCommand(
            name            = 'test_llvm',
            command         = ["make", "-j4", "check"],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    # yield BuilderConfig(name="cmake-llvm-x86_64-linux",
    #                     slavenames=["centos5"],
    #                     mergeRequests=False,
    #                     locks=[centos5_lock.access('counting')],
    #                     env={'PATH': '/home/chapuni/BUILD/cmake-2.8.8/bin:${PATH}'},
    #                     factory=factory)

    # CentOS6(llvm-x86)
    factory = BuildFactory()
    AddGitLLVMTree(factory,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')

    BlobPre(factory)

    CheckMakefile(factory)
    AddCMakeCentOS6(factory, buildClang=False, doStepIf=Makefile_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j8", "-k"],
            name            = 'build_llvm'))
    factory.addStep(LitTestCommand(
            name            = 'test_llvm',
            command         = ["make", "-j8", "check-llvm"],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))

    BlobPost(factory)

    yield BuilderConfig(name="cmake-llvm-x86_64-linux",
                        slavenames=["centos6"],
                        mergeRequests=False,
                        locks=[centos6_lock.access('counting')],
                        env={'PATH': '/home/chapuni/BUILD/cmake-2.8.8/bin:${PATH}'},
                        factory=factory)

    # CentOS5(clang only)
    factory = BuildFactory()
    AddGitLLVMTree(factory,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    CheckMakefile(factory)
    AddCMakeCentOS5(factory, doStepIf=Makefile_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j4", "-k"],
            locks           = [centos5_lock.access('counting')],
            name            = 'build_clang'))
    factory.addStep(LitTestCommand(
            name            = 'test_clang',
            command         = ["make", "-j4", "clang-test"],
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    # yield BuilderConfig(name="cmake-clang-x86_64-linux",
    #                     slavenames=["centos5"],
    #                     mergeRequests=False,
    #                     env={'PATH': '/home/chapuni/BUILD/cmake-2.8.8/bin:${PATH}'},
    #                     factory=factory)

    # CentOS6(clang only)
    factory = BuildFactory()
    AddGitLLVMTree(factory,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    BlobPre(factory)
    CheckMakefile(factory)
    AddCMakeCentOS6(factory, doStepIf=Makefile_not_ready)
    factory.addStep(Compile(
            command         = ["make", "-j8", "-k"],
            locks           = [centos6_lock.access('counting')],
            name            = 'build_clang'))
    factory.addStep(LitTestCommand(
            name            = 'test_clang',
            command         = ["make", "-j8", "check-clang"],
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    BlobPost(factory)
    yield BuilderConfig(name="cmake-clang-x86_64-linux",
                        slavenames=["centos6"],
                        mergeRequests=False,
                        env={'PATH': '/home/chapuni/BUILD/cmake-2.8.8/bin:${PATH}'},
                        factory=factory)

    # CentOS5(3stage)
    factory = BuildFactory()
    AddGitLLVMTree(factory,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/builds"),
                                    flunkOnFailure=False))
    #PatchLLVMClang(factory, "llvmclang.diff")
    AddCMakeCentOS5(factory,
                    LLVM_TARGETS_TO_BUILD="X86",
                    prefix="builds/install/stage1")
    factory.addStep(Compile(name="stage1_build",
                            command=["make", "-j4", "-l4.2", "-k"]))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_llvm',
            command         = ["make", "-j4", "-k", "check"],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output"),
                                    flunkOnFailure=False))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_clang',
            command         = ["make", "-j4", "-k", "clang-test"],
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
                                          "!", "-wholename", "*/test/*",
                                          "-type", "f",
                                          "-name", "*.o",
                                          "!", "-name", "llvm-config*",
                                          "-exec",
                                          "cmp", "../stage2/{}", "{}", ";"],
                                 workdir="last/stage3"))
    # yield BuilderConfig(name="clang-3stage-x86_64-linux",
    #                     slavenames=["centos5"],
    #                     mergeRequests=True,
    #                     env={'PATH': '/home/chapuni/BUILD/cmake-2.8.8/bin:${PATH}'},
    #                     factory=factory)

    # CentOS6(3stage)
    factory = BuildFactory()
    AddGitLLVMTree(factory,
                   '/var/cache/llvm-project-tree.git',
                   '/var/cache/llvm-project.git')
    BlobPre3(factory)
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/builds"),
                                    flunkOnFailure=False))
    #PatchLLVMClang(factory, "llvmclang.diff")
    AddCMakeCentOS6(factory,
                    LLVM_TARGETS_TO_BUILD="X86",
                    prefix="builds/install/stage1")
    factory.addStep(Compile(name="stage1_build",
                            command=["make", "-j8", "-l8.2", "-k"]))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_llvm',
            command         = ["make", "-j8", "-k", "check-llvm"],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output"),
                                    flunkOnFailure=False))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_clang',
            command         = ["make", "-j8", "-k", "check-clang"],
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    factory.addStep(Compile(name="stage1_install",
                            command=["make", "install", "-k", "-j8"]))

    # stage 2
    BuildStageN8(factory, 2)

    # stage 3
    BuildStageN8(factory, 3)

    # Trail
    BlobPost3(factory)
    # factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/last"),
    #                                 flunkOnFailure=False))
    # factory.addStep(ShellCommand(name="save_builds",
    #                              command=["mv", "-v",
    #                                       "builds",
    #                                       "last"],
    #                              workdir="."))
    factory.addStep(ShellCommand(name="compare_23",
                                 description="Comparing",
                                 descriptionDone="Compare-2-3",
                                 command=["find",
                                          "!", "-wholename", "*/test/*",
                                          "-type", "f",
                                          "-name", "*.o",
                                          "!", "-name", "llvm-config*",
                                          "-exec",
                                          "cmp", "../stage2/{}", "{}", ";"],
                                 workdir="builds/stage3"))
    yield BuilderConfig(name="clang-3stage-x86_64-linux",
                        slavenames=["centos6"],
                        mergeRequests=True,
                        env={'PATH': '/home/chapuni/BUILD/cmake-2.8.8/bin:${PATH}'},
                        factory=factory)

    # Cygwin(3stage)
    factory = BuildFactory()
    AddGitLLVMTree(factory,
                    'chapuni@192.168.1.199:/var/cache/llvm-project-tree.git',
                    '/cygdrive/d/llvm-project.git')
    PatchLLVMClang(factory, "llvmclang.diff")
    BlobPre3(factory)
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/builds"),
                                    flunkOnFailure=False))
#     AddCMake(factory, "Unix Makefiles",
#              LLVM_TARGETS_TO_BUILD="X86",
#              CMAKE_COLOR_MAKEFILE="OFF",
#              CMAKE_BUILD_TYPE="Release",
#              LLVM_LIT_ARGS="-v -j1",
#              CMAKE_LEGACY_CYGWIN_WIN32="0",
# #             CMAKE_EXE_LINKER_FLAGS="-Wl,--enable-auto-import /usr/lib/gcc/i686-pc-cygwin/4.3.4/libstdc++.a",
#              CMAKE_EXE_LINKER_FLAGS="-static",
#              prefix="builds/install/stage1")
    factory.addStep(ShellCommand(
            command=[
                "../llvm-project/llvm/configure",
                "-C",
                WithProperties("--prefix=%(workdir)s/builds/install/stage1"),
                WithProperties("--with-clang-srcdir=%(workdir)s/llvm-project/clang"),
                "LIBS=-static",
                "--enable-targets=x86",
                #"--enable-shared",
                "--with-optimize-option=-O1",
                "--enable-optimized"]))
    factory.addStep(Compile(name="stage1_build_quick",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            locks = [win7_cyg_lock.access('exclusive')],
                            command=["make", "-j5", "-k"]))
    factory.addStep(Compile(name="stage1_build_quick",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            command=["make", "-j8", "-k"]))
    factory.addStep(Compile(name="stage1_build",
                            command=["make", "-k"]))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_llvm',
            command         = ["make", "LIT_ARGS=-v -j1", "check"],
            description     = ["testing", "llvm"],
            descriptionDone = ["test",    "llvm"]))
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output"),
                                    flunkOnFailure=False))
    factory.addStep(LitTestCommand(
            name            = 'stage1_test_clang',
            command         = ["make", "TESTARGS=-v -j1", "-C", "tools/clang/test"],
            flunkOnFailure  = False,
            warnOnWarnings = False,
            flunkOnWarnings = False,
            description     = ["testing", "clang"],
            descriptionDone = ["test",    "clang"]))
    factory.addStep(Compile(name="stage1_install",
                            command=["make", "install", "-k"]))

    # stage 2
    BuildStageNcyg(factory, 2)

    # stage 3
    BuildStageNcyg(factory, 3)

    # Trail
    BlobPost3(factory)
    # factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/last"),
    #                                 flunkOnFailure=False))
    # factory.addStep(ShellCommand(name="save_builds",
    #                              command=["mv", "-v",
    #                                       "builds",
    #                                       "last"],
    #                              workdir="."))
    factory.addStep(ShellCommand(name="compare_23",
                                 description="Comparing",
                                 descriptionDone="Compare-2-3",
                                 command=["find",
                                          "!", "-wholename", "*/test/*",
                                          "-type", "f",
                                          "-name", "*.o",
                                          "!", "-name", "llvm-config*",
                                          "-exec",
                                          "cmp", "../stage2/{}", "{}", ";"],
                                 workdir="builds/stage3"))
    yield BuilderConfig(name="clang-3stage-cygwin",
                        slavenames=["cygwin"],
                        mergeRequests=True,
                        factory=factory)

    # Cygwin
    factory = BuildFactory()
    # check out the source
    AddGitLLVMTree(factory,
                    'chapuni@192.168.1.199:/var/cache/llvm-project-tree.git',
                    '/cygdrive/d/llvm-project.git')
    CheckMakefile(factory)
    PatchLLVM(factory, "llvm.patch")
    factory.addStep(ShellCommand(
            command=[
                "../llvm-project/llvm/configure",
                "-C",
                #"--enable-shared",
                WithProperties("--with-clang-srcdir=%(workdir)s/llvm-project/clang"),
                "LIBS=-static",
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

    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output"),
                                    flunkOnFailure=False))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "TESTARGS=-v -j1", "-C", "tools/clang/test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "LIT_ARGS=-v -j1", "check"]))
    # yield BuilderConfig(name="clang-i686-cygwin",
    #                     mergeRequests=True,
    #                     slavenames=["cygwin"],
    #                     factory=factory)

    # PS3
    factory = BuildFactory()
    # check out the source
    factory.addStep(ShellCommand(name="git-fetch",
                                 command=["git",
                                          "--git-dir", "/home/chapuni/llvm-project.git",
                                          "fetch", "origin", "--prune"],
                                 timeout=3600,
                                 flunkOnFailure=False));
    AddGitLLVMTree(factory,
                   'chapuni@192.168.1.199:/var/cache/llvm-project-tree.git',
                   '/home/chapuni/llvm-project.git')
    CheckMakefile(factory)
    factory.addStep(ShellCommand(
            command=[
                "../llvm-project/llvm/configure",
                "-C",
                "CC=ccache gcc",
                "CXX=ccache g++",
                WithProperties("--with-clang-srcdir=%(workdir)s/llvm-project/clang"),
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
    factory.addStep(Compile(
            command=["make",
                     "VERBOSE=1",
                     "-k",
                     ],
            timeout=3600,
            ))
    factory.addStep(RemoveDirectory(dir=WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output"),
                                    flunkOnFailure=False))
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
#    PatchLLVM(factory, "makefile.patch")
#    PatchLLVM(factory, "llvm.patch")
#    PatchClang(factory, "clang.patch")
    PatchLLVMClang(factory, "llvmclang.diff")
    factory.addStep(SetProperty(name="get_msys_path",
                                command=["sh", "-c", "PWD= sh pwd"],
                                workdir=".",
                                property="workdir_msys"))

    BlobPre(factory)

    CheckMakefile(factory)
    factory.addStep(ShellCommand(
            command=[
                "sh", "-c",
                WithProperties("PATH=/bin:$PATH PWD=%(workdir_msys)s/build %(workdir_msys)s/llvm-project/llvm/configure -C --enable-optimized --disable-pthreads --with-clang-srcdir=%(workdir_msys)s/llvm-project/clang")],
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
    factory.addStep(ShellCommand(
            command=[
                "rm", "-rf",
                WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output")],
            flunkOnFailure=False))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "TESTARGS=-v -j8", "-C", "tools/clang/test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "LIT_ARGS=-v -j8", "check"]))
    BlobPost(factory)
    yield BuilderConfig(name="clang-i686-msys",
                        mergeRequests=True,
                        slavenames=["win7"],
                        factory=factory)

    # cmake-msys
    factory = BuildFactory()
    AddGitWin7(factory)
    PatchLLVMClang(factory, "llvmclang.diff")
    BlobPre(factory)
    CheckMakefile(factory)
    AddCMakeDOS(factory, "MSYS Makefiles",
                CMAKE_BUILD_TYPE="Release",
                CMAKE_COLOR_MAKEFILE="OFF",
#                CMAKE_CXX_FLAGS_RELEASE="-O1 -DNDEBUG",
#                CMAKE_C_FLAGS_RELEASE="-O1 -DNDEBUG",
                doStepIf=Makefile_not_ready)
    factory.addStep(Compile(command=["make", "-j1", "-k"]))
    factory.addStep(ShellCommand(
            command=[
                "rm", "-rf",
                WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output")],
            flunkOnFailure=False))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["make", "-j1", "clang-test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["make", "-j1", "check"]))
    BlobPost(factory)
    yield BuilderConfig(name="cmake-clang-i686-msys",
                        mergeRequests=True,
                        slavenames=["win7"],
                        factory=factory)

    # MSVC10
    factory = BuildFactory()
    AddGitWin7(factory)
    BlobPre(factory)
    PatchLLVMClang(factory, "llvmclang.diff")
    CheckMakefile(factory, makefile="ALL_BUILD.vcxproj")
    AddCMakeDOS(factory, "Visual Studio 10",
                doStepIf=Makefile_not_ready)
    factory.addStep(Compile(name="zero_check",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            warnOnFailure=True,
                            timeout=3600,
                            command=["c:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe",
                                     "-m",
                                     "-v:m",
                                     "-p:Configuration=Release",
                                     "ZERO_CHECK.vcxproj"]))
    factory.addStep(Compile(name="all_build_quick",
                            haltOnFailure = False,
                            flunkOnFailure=False,
                            timeout=3600,
                            locks = [win7_cyg_lock.access('exclusive')],
                            command=["c:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe",
                                     "-m",
                                     "-v:m",
                                     "-p:Configuration=Release",
                                     "ALL_BUILD.vcxproj"]))
    factory.addStep(Compile(name="all_build",
                            command=["c:/Windows/Microsoft.NET/Framework/v4.0.30319/MSBuild.exe",
                                     "-m",
                                     "-v:m",
                                     "-p:Configuration=Release",
                                     "ALL_BUILD.vcxproj"]))
    factory.addStep(ShellCommand(
            command=[
                "rm", "-rf",
                WithProperties("%(workdir)s/build/tools/clang/test/Modules/Output")],
            flunkOnFailure=False))
    factory.addStep(LitTestCommand(
            name="test_clang",
            command=["c:/Python27/python.exe",
                     "../llvm-project/llvm/utils/lit/lit.py",
                     "--param", "build_config=Release",
                     "--param", "build_mode=Release",
                     "-v",
                     "tools/clang/test"]))
    factory.addStep(LitTestCommand(
            name="test_llvm",
            command=["c:/Python27/python.exe",
                     "../llvm-project/llvm/utils/lit/lit.py",
                     "--param", "build_config=Release",
                     "--param", "build_mode=Release",
                     "-v",
                     "test"]))
    BlobPost(factory)
    yield BuilderConfig(
        name="cmake-clang-i686-msvc10",
        mergeRequests=True,
        slavenames=["win7"],
        env={
            'INCLUDE': r'D:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\INCLUDE;D:\Program Files (x86)\Microsoft Visual Studio 10.0\VC\ATLMFC\INCLUDE;C:\Program Files (x86)\Microsoft SDKs\Windows\v7.0A\include;'
            },
        factory=factory)

#EOF
