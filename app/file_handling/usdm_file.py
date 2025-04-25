import json
from app.file_handling.data_files import DataFiles
from usdm4 import USDM4
from usdm4.api import Wrapper, Study


class USDMFile:
    def __init__(self, uuid: str):
        self._data_files = DataFiles(uuid=uuid)
        usdm_data = self._data_files.read("usdm")
        usdm_dict = json.loads(usdm_data)
        self.usdm: Wrapper = USDM4().from_json(usdm_dict)
        self.study: Study = self.usdm.study
