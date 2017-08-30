from buildbot.plugins import *

import config

def create_slave(name, *args, **kwargs):
    password = config.options.get('Slave Passwords', name)
    #return buildbot.buildslave.BuildSlave(name, password=password, *args, **kwargs)
    return worker.Worker(name, password, *args, **kwargs)

def get_build_slaves():
    return [
        #create_slave("centos5"),
        #create_slave("centos6"),
        #create_slave("win7", keepalive_interval=5*60),
        #create_slave("cygwin"),
        #create_slave("ps3-f12"),
        create_slave("lab-sled4"),
        #create_slave("lab-sled3"),
        ]
