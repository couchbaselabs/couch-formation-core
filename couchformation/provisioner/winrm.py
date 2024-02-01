##
##

import winrm


class WinRMProvisioner(object):

    def __init__(self, parameters: dict, command: str, root: bool = True):
        self.parameters = parameters
        self.command = command
        self.root = root
        self.username = self.parameters.get('username')
        self.password = self.parameters.get('password')
        self.public_ip = self.parameters.get('public_ip')
        self.private_ip = self.parameters.get('private_ip')
        self.use_private_ip = self.parameters.get('use_private_ip') if self.parameters.get('use_private_ip') else False

    def run(self):
        if self.use_private_ip:
            hostname = self.private_ip
        else:
            hostname = self.public_ip

        s = winrm.Session(hostname, auth=(self.username, self.password), transport='ntlm')
        r = s.run_ps(self.command)
        return r.std_out
