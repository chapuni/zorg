import config.builders
import config.slaves
import config.status

# Load local options.
import os
import configparser
options = configparser.RawConfigParser()
options.read(os.path.join(os.path.dirname(__file__), 'local.cfg'))
