import os
#import buildbot
from buildbot.plugins import *
#import buildbot.status.html
#import buildbot.status.mail
#import buildbot.status.words

import config
from zorg.buildbot.util.ConfigEmailLookup import ConfigEmailLookup
from zorg.buildbot.util.InformativeMailNotifier import InformativeMailNotifier

# Returns a list of Status Targets. The results of each build will be
# pushed to these targets. buildbot/status/*.py has a variety to choose from,
# including web pages, email senders, and IRC bots.

def get_status_targets(standard_builders):

    # from buildbot.status import html
    # from buildbot.status.web import auth, authz
    # authz_cfg=authz.Authz(
    #     # change any of these to True to enable; see the manual for more
    #     # options
    #     gracefulShutdown   = False,
    #     forceBuild         = True, # use this to test your slave once it is set up
    #     forceAllBuilds     = False,
    #     pingBuilder        = True,
    #     stopBuild          = True,
    #     stopAllBuilds      = False,
    #     cancelPendingBuild = True,
    #     )

    # default_email = config.options.get('Master Options', 'default_email')
    nick_prefix = config.options.get('Master Options', 'nick_prefix')

    return [
        # reporters.IRC(
        #     "irc.freenode.net", "bb-chapuni",
        #     channels=[
        #         {"channel": "#llvmjp"},
        #     ],
        #     useColors=True,
        #     allowForce=True,
        #     port=6697,
        #     useSSL=True,
        #     showBlameList=True,
        #     useRevisions=True,
        #     notify_events={
        #         'exception': 1,
        #         'successToFailure': 1,
        #         'failureToSuccess': 1,
        #     }),
        # buildbot.status.html.WebStatus(
        #     order_console_by_time=False, # String
        #     change_hook_dialects={
        #         'base' : True,
        #         'github' : True
        #         },
        #     http_port = 8011, authz=authz_cfg),
        # buildbot.status.mail.MailNotifier(
        #     fromaddr = "chapuni@t.pgr.jp",
        #     sendToInterestedUsers = False,
        #     extraRecipients = [default_email],
        #     mode = "problem",
        #     builders = standard_builders),
        # buildbot.status.words.IRC(
        #     host = "irc.oftc.net", nick = "bb-chapuni", channels = ["#llvm"],
        #     allowForce = True,
        #     notify_events={
        #         'successToFailure': 1,
        #         'warningsToFailure': 1,
        #         'failureToSuccess': 1,
        #         'warningsToSuccess': 1,
        #         'exceptionToSuccess': 1,
        #         }),
        reporters.IRC(
            #"irc.oftc.net",
            host="2001:6b0:e:2a18::116",
            nick=nick_prefix+"chapuni",
            channels = [
                {"channel": "#llvm"},
                {"channel": "#llvm-build"},
            ],
            name="IRC_oftc",
            useColors=True,
            allowForce=False,
            showBlameList=True,
            notify_events={
                'successToWarnings': 1,
                'warningsToSuccess': 1,
                'exceptionToSuccess': 1,
                'exception': 1,
                }),
        reporters.IRC(
            #"irc.freenode.net",
            host="2001:5a0:3604:1:64:86:243:181",
            nick=nick_prefix+"chapuni",
            channels=[
                {"channel": "#llvmjp"},
            ],
            name="IRC_freenode",
            useColors=True,
            allowForce=False,
            showBlameList=True,
            useRevisions=True,
            #port=6697,
            #useSSL=True,
            notify_events={
                'successToWarnings': 1,
                'warningsToSuccess': 1,
                'exceptionToSuccess': 1,
                'exception': 1,
            }),
        # InformativeMailNotifier(
        #     fromaddr="chapuni@t.pgr.jp",
        #     extraRecipients=["geek4civic@gmail.com"],
        #     sendToInterestedUsers= False,
        #     subject="Build %(builder)s Failure",
        #     mode = "problem",
        #     num_lines = 15),
        ]
