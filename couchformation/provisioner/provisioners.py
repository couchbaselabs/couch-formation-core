##
##

from couchformation import constants as C


class Provisioners(object):

    def __init__(self, node_profile: str, config_profile: str):
        self.node_profiles = C.NODE_PROFILES
        self.playbook_dir = C.PLAYBOOK_DIR
        self.node_profile = node_profile
        self.config_profile = config_profile
