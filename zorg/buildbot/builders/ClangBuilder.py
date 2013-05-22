import buildbot
import buildbot.process.factory
import os

from buildbot.process.properties import WithProperties
from buildbot.steps.shell import Configure, ShellCommand, SetProperty
from buildbot.steps.shell import WarningCountingShellCommand
from buildbot.steps.source import SVN
from buildbot.steps.transfer import FileDownload
from zorg.buildbot.Artifacts import GetCompilerArtifacts, uploadArtifacts
from zorg.buildbot.builders.Util import getConfigArgs
from zorg.buildbot.commands import DejaGNUCommand
from zorg.buildbot.commands import SuppressionDejaGNUCommand
from zorg.buildbot.commands.BatchFileDownload import BatchFileDownload
from zorg.buildbot.commands.LitTestCommand import LitTestCommand
from zorg.buildbot.PhasedBuilderUtils import GetLatestValidated, find_cc
from zorg.buildbot.PhasedBuilderUtils import find_liblto, SVNCleanupStep

def getClangBuildFactory(
            triple=None,
            clean=True,
            test=True,
            package_dst=None,
            run_cxx_tests=False,
            examples=False,
            valgrind=False,
            valgrindLeakCheck=False,
            outOfDir=False,
            useTwoStage=False,
            completely_clean=False, 
            make='make',
            jobs="%(jobs)s",
            stage1_config='Debug+Asserts',
            stage2_config='Release+Asserts',
            env={}, # Environmental variables for all steps.
            extra_configure_args=[],
            use_pty_in_tests=False,
            trunk_revision=None,
            force_checkout=False,
            extra_clean_step=None,
            checkout_compiler_rt=False,
            run_gdb=False,
            run_modern_gdb=False,
            run_gcc=False):
    # Prepare environmental variables. Set here all env we want everywhere.
    merged_env = {
        'TERM' : 'dumb' # Make sure Clang doesn't use color escape sequences.
                 }
    if env is not None:
        # Overwrite pre-set items with the given ones, so user can set anything.
        merged_env.update(env)

    if run_gdb or run_gcc or run_modern_gdb:
        outOfDir = True
        
    # Don't use in-dir builds with a two stage build process.
    inDir = not outOfDir and not useTwoStage
    if inDir:
        llvm_srcdir = "llvm"
        llvm_1_objdir = "llvm"
        llvm_1_installdir = None
    else:
        llvm_srcdir = "llvm.src"
        llvm_1_objdir = "llvm.obj"
        llvm_1_installdir = "llvm.install.1"
        llvm_2_objdir = "llvm.obj.2"
        llvm_2_installdir = "llvm.install"

    f = buildbot.process.factory.BuildFactory()

    # Determine the build directory.
    f.addStep(buildbot.steps.shell.SetProperty(name="get_builddir",
                                               command=["pwd"],
                                               property="builddir",
                                               description="set build dir",
                                               workdir=".",
                                               env=merged_env))

    # Blow away completely, if requested.
    if completely_clean:
        f.addStep(ShellCommand(name="rm-llvm.src",
                               command=["rm", "-rf", llvm_srcdir],
                               haltOnFailure=True,
                               description=["rm src dir", "llvm"],
                               workdir=".",
                               env=merged_env))

    # Checkout sources.
    if trunk_revision:
        # The SVN build step provides no mechanism to check out a specific revision
        # based on a property, so just run the commands directly here.
        svn_co = ['svn', 'checkout']
        if force_checkout:
            svn_co += ['--force']
        svn_co += ['--revision', WithProperties(trunk_revision)]

        svn_co_llvm = svn_co + \
          [WithProperties('http://llvm.org/svn/llvm-project/llvm/trunk@%s' %
                          trunk_revision),
           llvm_srcdir]
        svn_co_clang = svn_co + \
          [WithProperties('http://llvm.org/svn/llvm-project/cfe/trunk@%s' %
                          trunk_revision),
           '%s/tools/clang' % llvm_srcdir]
        svn_co_clang_tools_extra = svn_co + \
          [WithProperties('http://llvm.org/svn/llvm-project/clang-tools-extra/trunk@%s' %
                          trunk_revision),
           '%s/tools/clang/tools/extra' % llvm_srcdir]

        f.addStep(ShellCommand(name='svn-llvm',
                               command=svn_co_llvm,
                               haltOnFailure=True,
                               workdir='.'))
        f.addStep(ShellCommand(name='svn-clang',
                               command=svn_co_clang,
                               haltOnFailure=True,
                               workdir='.'))
        f.addStep(ShellCommand(name='svn-clang-tools-extra',
                               command=svn_co_clang_tools_extra,
                               haltOnFailure=True,
                               workdir='.'))
    else:
        f.addStep(SVN(name='svn-llvm',
                      mode='update',
                      baseURL='http://llvm.org/svn/llvm-project/llvm/',
                      defaultBranch='trunk',
                      workdir=llvm_srcdir))
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
        if checkout_compiler_rt:
            f.addStep(SVN(name='svn-compiler-rt',
                          mode='update',
                          baseURL='http://llvm.org/svn/llvm-project/compiler-rt/',
                          defaultBranch='trunk',
                          workdir='%s/projects/compiler-rt' % llvm_srcdir))

    # Clean up llvm (stage 1); unless in-dir.
    if clean and llvm_srcdir != llvm_1_objdir:
        f.addStep(ShellCommand(name="rm-llvm.obj.stage1",
                               command=["rm", "-rf", llvm_1_objdir],
                               haltOnFailure=True,
                               description=["rm build dir", "llvm"],
                               workdir=".",
                               env=merged_env))

    # Force without llvm-gcc so we don't run afoul of Frontend test failures.
    base_configure_args = [WithProperties("%%(builddir)s/%s/configure" % llvm_srcdir),
                           '--disable-bindings']
    base_configure_args += extra_configure_args
    if triple:
        base_configure_args += ['--build=%s' % triple,
                                '--host=%s' % triple]
    args = base_configure_args + ["--without-llvmgcc", "--without-llvmgxx"]
    args.append(WithProperties("--prefix=%%(builddir)s/%s" % llvm_1_installdir))
    args += getConfigArgs(stage1_config)
    if not clean:
        f.addStep(SetProperty(name="Makefile_isready",
                              workdir=llvm_1_objdir,
                              command=["sh", "-c",
                                       "test -e Makefile.config && echo OK || echo Missing"],
                              flunkOnFailure=False,
                          property="exists_Makefile"))
    f.addStep(Configure(command=args,
                        workdir=llvm_1_objdir,
                        description=['configuring',stage1_config],
                        descriptionDone=['configure',stage1_config],
                        env=merged_env,
                        doStepIf=lambda step: step.build.getProperty("exists_Makefile") != "OK"))

    # Make clean if using in-dir builds.
    if clean and llvm_srcdir == llvm_1_objdir:
        f.addStep(WarningCountingShellCommand(name="clean-llvm",
                                              command=[make, "clean"],
                                              haltOnFailure=True,
                                              description="cleaning llvm",
                                              descriptionDone="clean llvm",
                                              workdir=llvm_1_objdir,
                                              doStepIf=clean,
                                              env=merged_env))

    if extra_clean_step:
        f.addStep(extra_clean_step)

    f.addStep(WarningCountingShellCommand(name="compile",
                                          command=['nice', '-n', '10',
                                                   make, WithProperties("-j%s" % jobs)],
                                          haltOnFailure=True,
                                          description=["compiling", stage1_config],
                                          descriptionDone=["compile", stage1_config],
                                          workdir=llvm_1_objdir,
                                          env=merged_env))

    if examples:
        f.addStep(WarningCountingShellCommand(name="compile.examples",
                                              command=['nice', '-n', '10',
                                                       make, WithProperties("-j%s" % jobs),
                                                       "BUILD_EXAMPLES=1"],
                                              haltOnFailure=True,
                                              description=["compilinge", stage1_config, "examples"],
                                              descriptionDone=["compile", stage1_config, "examples"],
                                              workdir=llvm_1_objdir,
                                              env=merged_env))

    clangTestArgs = '-v -j %s' % jobs
    if valgrind:
        clangTestArgs += ' --vg'
        if valgrindLeakCheck:
            clangTestArgs += ' --vg-leak'
        clangTestArgs += ' --vg-arg --suppressions=%(builddir)s/llvm/tools/clang/utils/valgrind/x86_64-pc-linux-gnu_gcc-4.3.3.supp --vg-arg --suppressions=%(builddir)s/llvm/utils/valgrind/x86_64-pc-linux-gnu.supp'
    extraTestDirs = ''
    if run_cxx_tests:
        extraTestDirs += '%(builddir)s/llvm/tools/clang/utils/C++Tests'
    if test:
        f.addStep(LitTestCommand(name='check-all',
                                   command=[make, "check-all", "VERBOSE=1",
                                            WithProperties("LIT_ARGS=%s" % clangTestArgs),
                                            WithProperties("EXTRA_TESTDIRS=%s" % extraTestDirs)],
                                   description=["checking"],
                                   descriptionDone=["checked"],
                                   workdir=llvm_1_objdir,
                                   usePTY=use_pty_in_tests,
                                   env=merged_env))

    # Install llvm and clang.
    if llvm_1_installdir:
        f.addStep(ShellCommand(name="rm-install.clang.stage1",
                               command=["rm", "-rf", llvm_1_installdir],
                               haltOnFailure=True,
                               description=["rm install dir", "clang"],
                               workdir=".",
                               env=merged_env))
        f.addStep(WarningCountingShellCommand(name="install.clang.stage1",
                                              command = ['nice', '-n', '10',
                                                         make, 'install-clang'],
                                              haltOnFailure=True,
                                              description=["install", "clang",
                                                           stage1_config],
                                              workdir=llvm_1_objdir,
                                              env=merged_env))

    if run_gdb or run_gcc or run_modern_gdb:
        ignores = getClangTestsIgnoresFromPath(os.path.expanduser('~/public/clang-tests'), 'clang-x86_64-darwin10')
        install_prefix = "%%(builddir)s/%s" % llvm_1_installdir
        if run_gdb:
            addClangGDBTests(f, ignores, install_prefix)
        if run_modern_gdb:
            addModernClangGDBTests(f, jobs, install_prefix)
        if run_gcc:
            addClangGCCTests(f, ignores, install_prefix)

    if not useTwoStage:
        if package_dst:
            name = WithProperties(
                "%(builddir)s/" + llvm_1_objdir +
                "/clang-r%(got_revision)s-b%(buildnumber)s.tgz")
            f.addStep(ShellCommand(name='pkg.tar',
                                   description="tar root",
                                   command=["tar", "zcvf", name, "./"],
                                   workdir=llvm_1_installdir,
                                   warnOnFailure=True,
                                   flunkOnFailure=False,
                                   haltOnFailure=False,
                                   env=merged_env))
            f.addStep(ShellCommand(name='pkg.upload',
                                   description="upload root",
                                   command=["scp", name,
                                            WithProperties(
                            package_dst + "/%(buildername)s")],
                                   workdir=".",
                                   warnOnFailure=True,
                                   flunkOnFailure=False,
                                   haltOnFailure=False,
                                   env=merged_env))

        return f

    # Clean up llvm (stage 2).
    if clean:
        f.addStep(ShellCommand(name="rm-llvm.obj.stage2",
                               command=["rm", "-rf", llvm_2_objdir],
                               haltOnFailure=True,
                               description=["rm build dir", "llvm", "(stage 2)"],
                               workdir=".",
                               env=merged_env))

    # Configure llvm (stage 2).
    args = base_configure_args + ["--without-llvmgcc", "--without-llvmgxx"]
    args.append(WithProperties("--prefix=%(builddir)s/" + llvm_2_installdir))
    args += getConfigArgs(stage2_config)
    local_env = dict(merged_env)
    local_env.update({
        'CC'  : WithProperties("%%(builddir)s/%s/bin/clang"   % llvm_1_installdir),
        'CXX' : WithProperties("%%(builddir)s/%s/bin/clang++" % llvm_1_installdir)})

    f.addStep(Configure(name="configure.llvm.stage2",
                        command=args,
                        haltOnFailure=True,
                        workdir=llvm_2_objdir,
                        description=["configure", "llvm", "(stage 2)",
                                     stage2_config],
                        env=local_env))

    # Build llvm (stage 2).
    f.addStep(WarningCountingShellCommand(name="compile.llvm.stage2",
                                          command=['nice', '-n', '10',
                                                   make, WithProperties("-j%s" % jobs)],
                                          haltOnFailure=True,
                                          description=["compiling", "(stage 2)",
                                                       stage2_config],
                                          descriptionDone=["compile", "(stage 2)",
                                                           stage2_config],
                                          workdir=llvm_2_objdir,
                                          env=merged_env))

    if test:
        f.addStep(LitTestCommand(name='check-all',
                                   command=[make, "check-all", "VERBOSE=1",
                                            WithProperties("LIT_ARGS=%s" % clangTestArgs),
                                            WithProperties("EXTRA_TESTDIRS=%s" % extraTestDirs)],
                                   description=["checking"],
                                   descriptionDone=["checked"],
                                   workdir=llvm_2_objdir,
                                   usePTY=use_pty_in_tests,
                                   env=merged_env))

    # Install clang (stage 2).
    f.addStep(ShellCommand(name="rm-install.clang.stage2",
                           command=["rm", "-rf", llvm_2_installdir],
                           haltOnFailure=True,
                           description=["rm install dir", "clang"],
                           workdir=".",
                           env=merged_env))
    f.addStep(WarningCountingShellCommand(name="install.clang.stage2",
                                          command = ['nice', '-n', '10',
                                                     make, 'install-clang'],
                                          haltOnFailure=True,
                                          description=["install", "clang",
                                                       "(stage 2)"],
                                          workdir=llvm_2_objdir,
                                          env=merged_env))

    if package_dst:
        name = WithProperties(
            "%(builddir)s/" + llvm_2_objdir +
            "/clang-r%(got_revision)s-b%(buildnumber)s.tgz")
        f.addStep(ShellCommand(name='pkg.tar',
                               description="tar root",
                               command=["tar", "zcvf", name, "./"],
                               workdir=llvm_2_installdir,
                               warnOnFailure=True,
                               flunkOnFailure=False,
                               haltOnFailure=False,
                               env=merged_env))
        f.addStep(ShellCommand(name='pkg.upload',
                               description="upload root",
                               command=["scp", name,
                                        WithProperties(
                        package_dst + "/%(buildername)s")],
                               workdir=".",
                               warnOnFailure=True,
                               flunkOnFailure=False,
                               haltOnFailure=False,
                               env=merged_env))

    return f

def getClangMSVCBuildFactory(update=True, clean=True, vcDrive='c', jobs=1, cmake=r"cmake"):
    f = buildbot.process.factory.BuildFactory()

    if update:
        f.addStep(SVN(name='svn-llvm',
                      mode='update', baseURL='http://llvm.org/svn/llvm-project/llvm/',
                      defaultBranch='trunk',
                      workdir='llvm'))
        f.addStep(SVN(name='svn-clang',
                      mode='update', baseURL='http://llvm.org/svn/llvm-project/cfe/',
                      defaultBranch='trunk',
                      workdir='llvm/tools/clang'))
        f.addStep(SVN(name='svn-clang-tools-extra',
                      mode='update', baseURL='http://llvm.org/svn/llvm-project/clang-tools-extra/',
                      defaultBranch='trunk',
                      workdir='llvm/tools/clang/tools/extra'))

    # Full & fast clean.
    if clean:
        f.addStep(ShellCommand(name='clean-1',
                               command=['del','/s/q','build'],
                               warnOnFailure=True,
                               description='cleaning',
                               descriptionDone='clean',
                               workdir='llvm'))
        f.addStep(ShellCommand(name='clean-2',
                               command=['rmdir','/s/q','build'],
                               warnOnFailure=True,
                               description='cleaning',
                               descriptionDone='clean',
                               workdir='llvm'))

    # Create the project files.

    # Use batch files instead of ShellCommand directly, Windows quoting is
    # borked. FIXME: See buildbot ticket #595 and buildbot ticket #377.
    f.addStep(BatchFileDownload(name='cmakegen',
                                command=[cmake,
                                         "-DLLVM_TARGETS_TO_BUILD:=X86",
                                         "-DLLVM_INCLUDE_EXAMPLES:=OFF",
                                         "-DLLVM_INCLUDE_TESTS:=OFF",
                                         "-DLLVM_TARGETS_TO_BUILD:=X86",
                                         "-G",
                                         "Visual Studio 9 2008",
                                         ".."],
                                workdir="llvm\\build"))
    f.addStep(ShellCommand(name='cmake',
                           command=['cmakegen.bat'],
                           haltOnFailure=True,
                           description='cmake gen',
                           workdir='llvm\\build'))

    # Build it.
    f.addStep(BatchFileDownload(name='vcbuild',
                                command=[vcDrive + r""":\Program Files\Microsoft Visual Studio 9.0\VC\VCPackages\vcbuild.exe""",
                                         "/M%d" % jobs,
                                         "LLVM.sln",
                                         "Debug|Win32"],
                                workdir="llvm\\build"))
    f.addStep(WarningCountingShellCommand(name='vcbuild',
                                          command=['vcbuild.bat'],
                                          haltOnFailure=True,
                                          description='vcbuild',
                                          workdir='llvm\\build',
                                          warningPattern=" warning C.*:"))

    # Build clang-test project.
    f.addStep(BatchFileDownload(name='vcbuild_test',
                                command=[vcDrive + r""":\Program Files\Microsoft Visual Studio 9.0\VC\VCPackages\vcbuild.exe""",
                                         "clang-test.vcproj",
                                         "Debug|Win32"],
                                workdir="llvm\\build\\tools\\clang\\test"))
    f.addStep(LitTestCommand(name='test-clang',
                               command=["vcbuild_test.bat"],
                               workdir="llvm\\build\\tools\\clang\\test"))

    return f

# Builds on Windows using CMake, MinGW(32|64), and no Microsoft tools.
def getClangMinGWBuildFactory(update=True, clean=True, jobs=6, cmake=r"cmake"):
    f = buildbot.process.factory.BuildFactory()

    if update:
        f.addStep(SVN(name='svn-llvm',
                      mode='update', baseURL='http://llvm.org/svn/llvm-project/llvm/',
                      defaultBranch='trunk',
                      workdir='llvm'))
        f.addStep(SVN(name='svn-clang',
                      mode='update', baseURL='http://llvm.org/svn/llvm-project/cfe/',
                      defaultBranch='trunk',
                      workdir='llvm/tools/clang'))
        f.addStep(SVN(name='svn-clang-tools-extra',
                      mode='update', baseURL='http://llvm.org/svn/llvm-project/clang-tools-extra/',
                      defaultBranch='trunk',
                      workdir='llvm/tools/clang/tools/extra'))

    # Full & fast clean.
    if clean:
        # note: This command is redundant as the next command removes everything
        f.addStep(ShellCommand(name='clean-1',
                               command=['del','/s/q','build'],
                               warnOnFailure=True,
                               description='cleaning',
                               descriptionDone='clean',
                               workdir='llvm'))
        f.addStep(ShellCommand(name='clean-2',
                               command=['rmdir','/s/q','build'],
                               warnOnFailure=True,
                               description='cleaning',
                               descriptionDone='clean',
                               workdir='llvm'))

    # Create the Makefiles.

    # Use batch files instead of ShellCommand directly, Windows quoting is
    # borked. FIXME: See buildbot ticket #595 and buildbot ticket #377.
    f.addStep(BatchFileDownload(name='cmakegen',
                                command=[cmake,
                                         "-DLLVM_TARGETS_TO_BUILD:=X86",
                                         "-DLLVM_INCLUDE_EXAMPLES:=OFF",
                                         "-DLLVM_INCLUDE_TESTS:=OFF",
                                         "-DLLVM_TARGETS_TO_BUILD:=X86",
                                         "-G",
                                         "Ninja",
                                         ".."],
                                workdir="llvm\\build"))
    f.addStep(ShellCommand(name='cmake',
                           command=['cmakegen.bat'],
                           haltOnFailure=True,
                           description='cmake gen',
                           workdir='llvm\\build'))

    # Build it.
    f.addStep(BatchFileDownload(name='makeall',
                                command=["ninja", "-j", "%d" % jobs],
                                haltOnFailure=True,
                                workdir='llvm\\build'))

    f.addStep(WarningCountingShellCommand(name='makeall',
                                          command=['makeall.bat'],
                                          haltOnFailure=True,
                                          description='makeall',
                                          workdir='llvm\\build'))

    # Build global check project (make check) (sources not checked out...).
    if 0:
        f.addStep(BatchFileDownload(name='makecheck',
                                    command=["ninja", "check"],
                                    workdir='llvm\\build'))
        f.addStep(WarningCountingShellCommand(name='check',
                                              command=['makecheck.bat'],
                                              description='make check',
                                              workdir='llvm\\build'))

    # Build clang-test project (make clang-test).
    f.addStep(BatchFileDownload(name='maketest',
                                command=["ninja", "clang-test"],
                                workdir="llvm\\build"))
    f.addStep(LitTestCommand(name='clang-test',
                               command=["maketest.bat"],
                               workdir="llvm\\build"))

    return f

def addClangGCCTests(f, ignores={}, install_prefix="%(builddir)s/llvm.install",
                     languages = ('gcc', 'g++', 'objc', 'obj-c++')):
    make_vars = [WithProperties(
            'CC_UNDER_TEST=%s/bin/clang' % install_prefix),
                 WithProperties(
            'CXX_UNDER_TEST=%s/bin/clang++' % install_prefix)]
    f.addStep(SVN(name='svn-clang-tests', mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/clang-tests/',
                  defaultBranch='trunk', workdir='clang-tests'))
    gcc_dg_ignores = ignores.get('gcc-4_2-testsuite', {})
    for lang in languages:
        f.addStep(SuppressionDejaGNUCommand.SuppressionDejaGNUCommand(
            name='test-gcc-4_2-testsuite-%s' % lang,
            command=["make", "-k", "check-%s" % lang] + make_vars,
            description="gcc-4_2-testsuite (%s)" % lang,
            workdir='clang-tests/gcc-4_2-testsuite',
            logfiles={ 'dg.sum' : 'obj/%s/%s.sum' % (lang, lang),
                       '%s.log' % lang : 'obj/%s/%s.log' % (lang, lang)},
            ignore=gcc_dg_ignores.get(lang, [])))

def addClangGDBTests(f, ignores={}, install_prefix="%(builddir)s/llvm.install"):
    make_vars = [WithProperties(
            'CC_UNDER_TEST=%s/bin/clang' % install_prefix),
                 WithProperties(
            'CXX_UNDER_TEST=%s/bin/clang++' % install_prefix)]
    f.addStep(SVN(name='svn-clang-tests', mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/clang-tests/',
                  defaultBranch='trunk', workdir='clang-tests'))
    f.addStep(SuppressionDejaGNUCommand.SuppressionDejaGNUCommand(
            name='test-gdb-1472-testsuite',
            command=["make", "-k", "check"] + make_vars,
            description="gdb-1472-testsuite",
            workdir='clang-tests/gdb-1472-testsuite',
            logfiles={ 'dg.sum' : 'obj/filtered.gdb.sum',
                       'gdb.log' : 'obj/gdb.log' }))

def addModernClangGDBTests(f, jobs, install_prefix):
    make_vars = [WithProperties('RUNTESTFLAGS=CC_FOR_TARGET=\'{0}/bin/clang\' '
                                'CXX_FOR_TARGET=\'{0}/bin/clang++\' '
                                'CFLAGS_FOR_TARGET=\'-w -fno-limit-debug-info\''
                                .format(install_prefix))]
    f.addStep(SVN(name='svn-clang-tests', mode='update',
                  svnurl='http://llvm.org/svn/llvm-project/clang-tests-external/trunk/gdb/7.5',
                  workdir='clang-tests/src'))
    f.addStep(Configure(command='../src/configure',
                        workdir='clang-tests/build/'))
    f.addStep(WarningCountingShellCommand(name='gdb-75-build',
                                          command=['make', WithProperties('-j%s' % jobs)],
                                          haltOnFailure=True,
                                          workdir='clang-tests/build'))
    f.addStep(DejaGNUCommand.DejaGNUCommand(
            name='gdb-75-check',
            command=['make', '-k', WithProperties('-j%s' % jobs), 'check'] + make_vars,
            workdir='clang-tests/build',
            logfiles={'dg.sum':'gdb/testsuite/gdb.sum', 
                      'gdb.log':'gdb/testsuite/gdb.log'}))



# FIXME: Deprecated.
addClangTests = addClangGCCTests

def getClangTestsIgnoresFromPath(path, key):
    def readList(path):
        if not os.path.exists(path):
            return []

        f = open(path)
        lines = [ln.strip() for ln in f]
        f.close()
        return lines

    ignores = {}

    gcc_dg_ignores = {}
    for lang in ('gcc', 'g++', 'objc', 'obj-c++'):
        lang_path = os.path.join(path, 'gcc-4_2-testsuite', 'expected_results',
                                 key, lang)
        gcc_dg_ignores[lang] = (
            readList(os.path.join(lang_path, 'FAIL.txt')) +
            readList(os.path.join(lang_path, 'UNRESOLVED.txt')) +
            readList(os.path.join(lang_path, 'XPASS.txt')))
    ignores['gcc-4_2-testsuite' ] = gcc_dg_ignores

    ignores_path = os.path.join(path, 'gdb-1472-testsuite', 'expected_results',
                                key)
    gdb_dg_ignores = (
        readList(os.path.join(ignores_path, 'FAIL.txt')) +
        readList(os.path.join(ignores_path, 'UNRESOLVED.txt')) +
        readList(os.path.join(ignores_path, 'XPASS.txt')))
    ignores['gdb-1472-testsuite' ] = gdb_dg_ignores

    return ignores

from zorg.buildbot.PhasedBuilderUtils import getBuildDir, setProperty
from zorg.buildbot.builders.Util import _did_last_build_fail
from buildbot.steps.source.svn import SVN as HostSVN

def phasedClang(config_options, is_bootstrap=True, use_lto=False,
                incremental=False):
    # Create an instance of the Builder.
    f = buildbot.process.factory.BuildFactory()
    # Determine the build directory.
    f = getBuildDir(f)
    # get rid of old archives from prior builds
    f.addStep(buildbot.steps.shell.ShellCommand(
            name='rm.archives', command=['sh', '-c', 'rm -rfv *gz'],
            haltOnFailure=False, description=['rm archives'],
            workdir=WithProperties('%(builddir)s')))
    # Clean the build directory.
    clang_build_dir = 'clang-build'
    if incremental:
        f.addStep(buildbot.steps.shell.ShellCommand(
                name='rm.clang-build', command=['rm', '-rfv', clang_build_dir],
                haltOnFailure=False, description=['rm dir', clang_build_dir],
                workdir=WithProperties('%(builddir)s'),
                doStepIf=_did_last_build_fail))
    else:
        f.addStep(buildbot.steps.shell.ShellCommand(
                name='rm.clang-build', command=['rm', '-rfv', clang_build_dir],
                haltOnFailure=False, description=['rm dir', clang_build_dir],
                workdir=WithProperties('%(builddir)s')))
    
    # Cleanup the clang link, which buildbot's SVN always_purge does not know
    # (in 8.5 this changed to method='fresh')
    # how to remove correctly. If we don't do this, the LLVM update steps will
    # end up doing a clobber every time.
    #
    # FIXME: Should file a Trac for this, but I am lazy.
    f.addStep(buildbot.steps.shell.ShellCommand(
            name='rm.clang-sources-link',
            command=['rm', '-rfv', 'llvm/tools/clang'],
            haltOnFailure=False, description=['rm', 'clang sources link'],
            workdir=WithProperties('%(builddir)s')))
    f.addStep(buildbot.steps.shell.ShellCommand(
            name='rm.compiler-rt-sources-link',
            command=['rm', '-rfv', 'llvm/projects/compiler-rt'],
            haltOnFailure=False, description=['rm', 'compiler-rt sources link'],
            workdir=WithProperties('%(builddir)s')))
    # Pull sources.
    f = SVNCleanupStep(f, 'llvm')
    f.addStep(HostSVN(name='pull.llvm', mode='incremental', method='fresh',
                      repourl='http://llvm.org/svn/llvm-project/llvm/trunk',
                      retry=(60, 5), workdir='llvm', description='pull.llvm',
                      alwaysUseLatest=False))
    f = SVNCleanupStep(f, 'clang.src')
    f.addStep(HostSVN(name='pull.clang', mode='incremental', method='fresh',
                      repourl='http://llvm.org/svn/llvm-project/cfe/trunk',
                      workdir='clang.src', retry=(60, 5),
                      description='pull.clang', alwaysUseLatest=False))
    f = SVNCleanupStep(f, 'clang-tools-extra.src')
    f.addStep(HostSVN(name='pull.clang-tools-extra', mode='incremental',
                      method='fresh',
                      repourl='http://llvm.org/svn/llvm-project/'
                              'clang-tools-extra/trunk',
                      workdir='clang-tools-extra.src', alwaysUseLatest=False,
                      retry=(60, 5), description='pull.clang-tools-extra'))
    f = SVNCleanupStep(f, 'compiler-rt.src')
    f.addStep(HostSVN(name='pull.compiler-rt', mode='incremental',
                      method='fresh',
                      repourl='http://llvm.org/svn/llvm-project/compiler-rt/'
                              'trunk',
                      workdir='compiler-rt.src', alwaysUseLatest=False,
                      retry=(60, 5), description='pull.compiler-rt'))
    # Create symlinks to the clang compiler-rt sources inside the LLVM tree.
    # We don't actually check out the sources there, because the SVN purge
    # would always remove them then.
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='ln.clang-sources', haltOnFailure=True,
              command=['ln', '-sfv', '../../clang.src', 'clang'],
              workdir='llvm/tools', description=['ln', 'clang sources']))
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='ln.compiler-rt-sources',
              command=['ln', '-sfv', '../../compiler-rt.src', 'compiler-rt'],
              haltOnFailure=True, workdir='llvm/projects',
              description=['ln', 'compiler-rt sources']))
    # TODO: We used to use a symlink here but it seems to not work. I am trying
    # to get this builder to work so I am just going to copy it instead.
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='rm.clang-tools-extra-source',
              command=['rm', '-rfv', 'extra'],
              haltOnFailure=True, workdir='clang.src/tools',
              description=['rm', 'clang-tools-extra sources']))
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='cp.clang-tools-extra-sources',
              command=['cp', '-Rfv', '../../clang-tools-extra.src', 'extra'],
              haltOnFailure=True, workdir='clang.src/tools',
              description=['cp', 'clang-tools-extra sources']))    
    # Checkout the supplemental 'debuginfo-tests' repository.
    debuginfo_url = 'http://llvm.org/svn/llvm-project/debuginfo-tests/trunk'
    f.addStep(HostSVN(name='pull.debug-info tests', mode='incremental',
                      repourl=debuginfo_url,
                      method='fresh',
                      workdir='llvm/tools/clang/test/debuginfo-tests',
                      alwaysUseLatest=False, retry = (60, 5),
                      description='pull.debug-info tests'))
    # Clean the install directory.
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='rm.clang-install', command=['rm', '-rfv', 'clang-install'],
              haltOnFailure=False, description=['rm dir', 'clang-install'],
              workdir=WithProperties('%(builddir)s')))
    # Construct the configure arguments.
    configure_args = ['../llvm/configure']
    configure_args.extend(config_options)
    configure_args.extend(['--disable-bindings', '--with-llvmcc=clang',
                           '--without-llvmgcc', '--without-llvmgxx',
                           '--enable-keep-symbols'])
    configure_args.append(
        WithProperties('--prefix=%(builddir)s/clang-install'))    
    
    # If we are using a previously built compiler, download it and override CC
    # and CXX.
    if is_bootstrap:
        f = GetCompilerArtifacts(f)
    else:
        f = GetLatestValidated(f)
    cc_command = ['find', 'host-compiler', '-name', 'clang']
    f.addStep(buildbot.steps.shell.SetProperty(
              name='find.cc',
              command=cc_command,
              extract_fn=find_cc,
              workdir=WithProperties('%(builddir)s')))
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='sanity.test', haltOnFailure=True,
              command=[WithProperties('%(builddir)s/%(cc_path)s'), '-v'],
              description=['sanity test']))
    configure_args.extend([
            WithProperties('CC=%(builddir)s/%(cc_path)s'),
            WithProperties('CXX=%(builddir)s/%(cc_path)s++')])
    
    # If we need to use lto, find liblto, add in proper flags here, etc.
    if use_lto:
        liblto_command = ['find', WithProperties('%(builddir)s/host-compiler'),
                          '-name', 'libLTO.dylib']
        f.addStep(buildbot.steps.shell.SetProperty(
                name='find.liblto',
                command=liblto_command,
                extract_fn=find_liblto,
                workdir=WithProperties('%(builddir)s')))
        configure_args.append(
          '--with-extra-options=-flto -gline-tables-only')
    
    # Configure the LLVM build.
    if incremental:
        # *NOTE* This is a temporary work around. I am eventually going to just
        # set up cmake/ninja but for now I am sticking with the make => I need
        # configure to run only after a failure so on success I have incremental
        # builds.
        f.addStep(buildbot.steps.shell.ShellCommand(
                name='configure.with.host', command=configure_args,
                haltOnFailure=True, description=['configure'],
                workdir=clang_build_dir,
                doStepIf=_did_last_build_fail))
    else:
        f.addStep(buildbot.steps.shell.ShellCommand(
                name='configure.with.host', command=configure_args,
                haltOnFailure=True, description=['configure'],
                workdir=clang_build_dir))
    
    # Build the compiler.
    make_command = ['make', '-j', WithProperties('%(jobs)s')]
    timeout = 40*60 # Normal timeout is 20 minutes.
    if use_lto:
        make_command.append(WithProperties('DYLD_LIBRARY_PATH=%(liblto_path)s'))
        timeout = 180*60 # LTO timeout is 180 minutes.
    
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='make', command=make_command,
              haltOnFailure=True, description=['make'], workdir=clang_build_dir,
              timeout=timeout))
    # Use make install-clang to produce minimal archive for use by downstream
    # builders.
    f.addStep(buildbot.steps.shell.ShellCommand(
              name='make.install-clang', haltOnFailure=True,
              command=['make', 'install-clang', '-j',
                       WithProperties('%(jobs)s'),
                       'RC_SUPPORTED_ARCHS=armv7 i386 x86_64'],
              description=['make install'], workdir=clang_build_dir))
    # Save artifacts of this build for use by other builders.
    f = uploadArtifacts(f)
    # Run the LLVM and Clang regression tests.
    f.addStep(LitTestCommand(name='run.llvm.tests', haltOnFailure=True,
                             command=['make', '-j', WithProperties('%(jobs)s'),
                             'VERBOSE=1', 'check-all'],
                             description=['all', 'tests'],
                             workdir=clang_build_dir))
    return f
