import os

import buildbot
import buildbot.process.factory
from buildbot.steps.source import SVN, Git
from buildbot.steps.shell import Configure, ShellCommand
from buildbot.steps.shell import WarningCountingShellCommand
from buildbot.process.properties import WithProperties
from zorg.buildbot.commands.LitTestCommand import LitTestCommand

def getClangAndLLDBuildFactory(
           clean=True,
           env=None):

    llvm_srcdir = "llvm.src"
    llvm_objdir = "llvm.obj"

    # Prepare environmental variables. Set here all env we want everywhere.
    merged_env = {
        'TERM' : 'dumb' # Make sure Clang doesn't use color escape sequences.
                 }
    if env is not None:
        # Overwrite pre-set items with the given ones, so user can set anything.
        merged_env.update(env)

    f = buildbot.process.factory.BuildFactory()

    # Determine the build directory.
    f.addStep(buildbot.steps.shell.SetProperty(name="get_builddir",
                                               command=["pwd"],
                                               property="builddir",
                                               description="set build dir",
                                               workdir=".",
                                               env=merged_env))
    # Get LLVM, Clang and LLD.
    f.addStep(SVN(name='svn-llvm',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/llvm/',
                  defaultBranch='trunk',
                  workdir=llvm_srcdir))
    f.addStep(SVN(name='svn-compiler-rt',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/compiler-rt/',
                  defaultBranch='trunk',
                  workdir='%s/projects/compiler-rt' % llvm_srcdir))
    f.addStep(SVN(name='svn-clang',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/cfe/',
                  defaultBranch='trunk',
                  workdir='%s/tools/clang' % llvm_srcdir))
    f.addStep(SVN(name='svn-clang-tools-extra',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/clang-tools-extra/',
                  defaultBranch='trunk',
                  workdir='%s/tools/clang/tools/extra' % llvm_srcdir))
    f.addStep(SVN(name='svn-lld',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/lld/',
                  defaultBranch='trunk',
                  workdir='%s/tools/lld' % llvm_srcdir))

    # Clean directory, if requested.
    if clean:
        f.addStep(ShellCommand(name="rm-llvm_objdir",
                               command=["rm", "-rf", llvm_objdir],
                               haltOnFailure=True,
                               description=["rm build dir", "llvm"],
                               workdir=".",
                               env=merged_env))

    # Create configuration files with cmake.
    f.addStep(ShellCommand(name="create-build-dir",
                               command=["mkdir", "-p", llvm_objdir],
                               haltOnFailure=False,
                               description=["create build dir"],
                               workdir=".",
                               env=merged_env))
    cmakeCommand = [
        "cmake",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DLLVM_ENABLE_ASSERTIONS=ON",
        "-DCMAKE_CXX_FLAGS=\"-std=c++11 -Wdocumentation -Wno-documentation-deprecated-sync\"",
        "-DLLVM_LIT_ARGS=\"-v\"",
        "-G", "Ninja",
        "../%s" % llvm_srcdir]
    # Note: ShellCommand does not pass the params with special symbols right.
    # The " ".join is a workaround for this bug.
    f.addStep(ShellCommand(name="cmake-configure",
                               description=["cmake configure"],
                               haltOnFailure=True,
                               command=WithProperties(" ".join(cmakeCommand)),
                               workdir=llvm_objdir,
                               env=merged_env))

    # Build everything.
    f.addStep(WarningCountingShellCommand(name="build",
                                          command=["nice", "-n", "10", "ninja"],
                                          haltOnFailure=True,
                                          description=["build"],
                                          workdir=llvm_objdir,
                                          env=merged_env))

    # Test everything.
    f.addStep(LitTestCommand(name="test",
                             command=["nice", "-n", "10", "ninja", "check-all"],
                             haltOnFailure=True,
                             description=["test"],
                             workdir=llvm_objdir,
                             env=merged_env))

    return f
