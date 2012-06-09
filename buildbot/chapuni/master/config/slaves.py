import buildbot
import buildbot.buildslave
import os

import config

def create_slave(name, *args, **kwargs):
    password = config.options.get('Slave Passwords', name)
    return buildbot.buildslave.BuildSlave(name, password=password, *args, **kwargs)

def get_build_slaves():
    return [
        create_slave("centos5"),
        create_slave("win7"),
        create_slave("cygwin"),
        create_slave("ps3-f12"),
        create_slave("amd64-solaris"),
        ]
