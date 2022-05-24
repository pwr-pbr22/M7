import configparser


class ProjectConfiguration:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.properties')
        self.projects = self.config.get("Config", "projects").split(",")
        self.connstr = self.config.get("Config", "connstr")
        self.gh_keys = self.config.get("Config", "gh_keys").split(",")
