import json
from app.file_handling.data_files import DataFiles
from usdm4 import USDM4
from usdm4.api import Wrapper, Study, StudyVersion


class USDMFile:
    def __init__(self, uuid: str):
        self._data_files = DataFiles(uuid=uuid)
        usdm_data = self._data_files.read("usdm")
        usdm_dict = json.loads(usdm_data)
        self.usdm: Wrapper = USDM4().from_json(usdm_dict)
        self.study: Study = self.usdm.study
        self._version: StudyVersion = self.study.first_version()
        
    def summary(self) -> dict:
        return {
            "sponsor_name": self._version.sponsor_name(),
            "sponsor_protocol_identifier": self._version.sponsor_identifier_text(),
            "title": self._version.official_title_text()
        }
    
    def document_templates(self) -> list[str]:
        return [x.templateName for x in self.study.documentedBy]
