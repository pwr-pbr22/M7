import configparser


class ProjectConfiguration:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.properties')
        self.project = self.config.get("Config", "project")
        self.connstr = self.config.get("Config", "connstr")
        self.gh_keys = self.config.get("Config", "gh_keys").split(",")
