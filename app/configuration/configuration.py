from d4k_ms_base.logger import application_logger
from d4k_ms_base.service_environment import ServiceEnvironment


class Configuration:
    def __init__(self):
        self._se = ServiceEnvironment()
        self.data_file_path = self._se.get("DATAFILE_PATH")
        self.mount_path = self._se.get("MNT_PATH")
        self.uuid = self._se.get("UUID")


application_configuration = Configuration()
