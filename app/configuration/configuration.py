from d4k_ms_base.service_environment import ServiceEnvironment


class Configuration:
    def __init__(self):
        self._se = ServiceEnvironment()
        self.data_file_path = self._se.get("DATAFILE_PATH")
        self.mount_path = self._se.get("MNT_PATH")

application_configuration = Configuration()
