import re
import yaml
from app.file_handling.data_files import DataFiles
from app.file_handling.usdm_file import USDMFile
from d4k_ms_base.logger import application_logger
from usdm4.api.study_version import StudyVersion
from usdm4.api.narrative_content import NarrativeContent, NarrativeContentItem
from usdm4.api.study_definition_document import StudyDefinitionDocument
from usdm4.api.study_definition_document_version import StudyDefinitionDocumentVersion
from usdm3.base.id_manager import IdManager
from usdm3.base.api_instance import APIInstance
from usdm4.builder.builder import Builder
from usdm4.api import __all__ as all_klasses

class TemplateFile:
    
    def set_template(self, uuid: str, template: str):
        self._data_files = DataFiles(template=template, uuid=uuid)
        self._template = template
        self._uuid = uuid
        self._data = self._read() if self._data_files.exists("protocol") else self.from_usdm()

    def from_usdm(self):
        self._data = {}
        usdm = USDMFile(self._uuid)
        study_version: StudyVersion = usdm.study.first_version()
        ncis = study_version.narrative_content_item_map()
        document_version = self._document_version(usdm)
        section = "0-1"
        if document_version:
            ncs = document_version.narrative_content_in_order()
            ncis = study_version.narrative_content_item_map()
            for nc in ncs:
                print(f"SECTION NUMBER: {nc.sectionNumber} <- {section}")
                nci = ncis[nc.contentItemId] if nc.contentItemId in ncis else None
                if nc.sectionNumber:
                    section_key = self._section_number_to_key(nc.sectionNumber)
                    section = str(section_key)
                else:
                    section_key = section
                    section = self._increment_section_number(section)
                self._data[section_key] = {
                    "content": nc.model_dump(),
                    "content_item": nci.model_dump(),
                }
        self._write()
        return self._data

    def to_usdm(self):
        usdm_file = USDMFile(self._uuid)
        id_manager = IdManager(all_klasses)
        self._decompose(usdm_file.usdm.model_dump(), id_manager)
        api = APIInstance(id_manager)
        builder = Builder()
        study_version: StudyVersion = usdm_file.study.first_version()
        prev_ncis = study_version.narrative_content_item_map()
        document_version = self._document_version(usdm_file)
        if document_version:
            document_version.narrative_content_in_order() 
            order = self._section_order()
            ncs = []
            ncis = []
            for x in order:
                item = self._data[x]
                ncs.append(api.create(NarrativeContent, item["content"]))
                if "id" in item["content_item"]:
                    print(f"ID PRESENT")
                    x1 = prev_ncis[item["content_item"]["id"]].text
                    x2 = item["content_item"]["text"]
                    x3 = x1 == x2
                    print(f"TEXT: {x1[0:20]}, {x2[0:20]}, {x3}")
                    prev_ncis[item["content_item"]["id"]].text = item["content_item"]["text"]
                else:
                    print(f"NEW ")
                    ncis.append(api.create(NarrativeContentItem, item["content_item"]))
            study_version.narrativeContentItems += ncis
            builder.double_link(ncs, "previousId", "nextId")
            document_version.contents = ncs
            self._data_files.save("usdm", usdm_file.usdm.to_json())
            return True
        else:
            return False

    def _document_version(self, usdm: USDMFile) -> StudyDefinitionDocumentVersion:
        study_version: StudyVersion = usdm.study.first_version()
        document = usdm.study.document_by_template_name(self._template)
        document_version = None
        for dv in document.versions:
            if dv.id in study_version.documentVersionIds:
                document_version = dv
                break
        return document_version
    
    def usdm_file(self) -> tuple[str, str, str]:
        full_path, filename, _ =  self._data_files.path("usdm")
        return full_path, filename, "application/json"

    def toc_sections(self) -> list:
        order = self._section_order()
        return [
            {
                "key": x,
                "sectionNumber": self._data[x]["content"]["sectionNumber"],
                "sectionTitle": self._data[x]["content"]["sectionTitle"],
            }
            for x in order
        ]

    def toc_level_1_sections(self) -> list:
        order = self._section_order()
        return [
            {
                "key": x,
                "sectionNumber": self._data[x]["content"]["sectionNumber"],
                "sectionTitle": self._data[x]["content"]["sectionTitle"],
            }
            for x in order
            if self._level(self._data[x]["content"]["sectionNumber"]) == 1
        ]

    def get_section(self, section_key) -> dict:
        return self._data[section_key]

    def put_section(self, section_key, text):
        section = self.get_section(section_key)
        if section:
            application_logger.info(f"Updatting section {section_key}")
            self._data[section_key]["content_item"]["text"] = text
            self._write()
        return self._data[section_key]

    def put_section_title(self, section_key, title):
        section = self.get_section(section_key)
        if section:
            application_logger.info(f"Updatting section title {section_key}")
            self._data[section_key]["content"]["sectionTitle"] = title
            self._write()
        return self._data[section_key]

    def insert_usdm(self, section_key: str, type: str, position: int) -> str:
        section = self.get_section(section_key)
        if section:
            application_logger.info(
                f"USDM insert {section_key}, type {type}, @ {position}"
            )
            self._data[section_key]["content_item"]["text"] = self._insert_usdm(
                self._data[section_key]["content_item"]["text"], type, position
            )
            self._write()
        # self._lock.release()
        return self._data[section_key]

    def delete_section(self, section_key):
        section = self.get_section(section_key)
        if section:
            self._data.pop(section_key)
            self._write()
            result = True
        else:
            result = False
        return result

    def can_add_sibling_section(self, section_key):
        potential_section_key = self._increment_section_number(section_key)
        return self._section_is_permitted(potential_section_key)

    def can_add_child_section(self, section_key):
        potential_section_key = self._child_section_number(section_key)
        return self._section_is_permitted(potential_section_key)

    def add_sibling_section(self, section_key):
        new_section_key = self._increment_section_number(section_key)
        if self._section_is_permitted(new_section_key):
            self._data[new_section_key] = self._section_entry(new_section_key)
            self._write()
            result = new_section_key
        else:
            result = None
        return result

    def add_child_section(self, section_key):
        new_section_key = self._child_section_number(section_key)
        if self._section_is_permitted(new_section_key):
            self._data[new_section_key] = self._section_entry(new_section_key)
            self._write()
            result = new_section_key
        else:
            result = None
        return result

    def _section_entry(self, section_key: str) -> dict:
        return {
            "content": {
                "name": f"SECTION_{section_key}",
                "sectionNumber": self._key_to_section_number(section_key),
                "sectionTitle": "To Be Provided",
                "displaySectionNumber": True,
                "displaySectionTitle": True,
                "childIds": [],
                "previousId": None,
                "nextId": None,
                "contentItemId": None,
                "instanceType": "NarrativeContent"
            },
            "content_item": {
                "name":  f"CONTENT_{section_key}",
                "text": "",
                "instanceType": "NarrativeContentItem"
            }
        }
        
    def _key_to_section_number(self, section_key: str) -> str:
        return section_key.replace("_", ".")

    def _section_number_to_key(self, section: str) -> str:
        text = self._normalise_section(section)
        return text.replace(".", "-")

    def _level(self, section: str) -> int:
        text = self._normalise_section(section)
        parts = text.split(".")
        return len(parts)

    def _normalise_section(self, section):
        return section[:-1] if section.endswith(".") else section

    def _read(self) -> dict:
        return yaml.safe_load(self._data_files.read("protocol"))

    def _write(self):
        self._data_files.save("protocol", self._data)

    def _section_order(self):
        return sorted(list(self._data.keys()), key=self._section)

    def _section(self, s):
        try:
            return [int(_) for _ in s.split("-")]
        except Exception as e:
            application_logger.exception(
                "Exception during numeric section formation", e
            )

    def _increment_section_number(self, section_key):
        print(f"INCREMENT: {section_key}")
        parts = section_key.split("-")
        parts[-1] = str(int(parts[-1]) + 1)
        return "-".join(parts)

    def _child_section_number(self, section_key):
        parts = section_key.split("-")
        parts.append("1")
        return "-".join(parts)

    def _section_is_permitted(self, section_key):
        result = True if section_key not in self._data.keys() else False
        application_logger.info(f"Section is permitted for {section_key}={result}")
        return result

    def _insert_usdm(self, text: str, type: str, position: int) -> str:
        if type == "reference":
            return self._insert_text(
                text,
                '<usdm:ref klass="klass name" id="identifier" attribute="attribute name"/>',
                position,
            )
        elif type == "tag":
            return self._insert_text(
                text, '<usdm:tag name="dictionary parameter tag name"/>', position
            )
        elif type == "xref":
            return self._insert_text(
                text,
                '<usdm:macro id="xref" klass="klass name" name="item name" attribute="attribute name"/>',
                position,
            )
        elif type == "image":
            return self._insert_text(
                text,
                '<usdm:macro id="image" file="file name" type="png|jpg"/>',
                position,
            )
        elif type == "element":
            return self._insert_text(
                text,
                '<usdm:macro id="element" name="study_phase|study_short_title|study_full_title|study_acronym|study_rationale|study_version_identifier|study_identifier|study_regulatory_identifiers|study_date|approval_date|organization_name|organization_address|organization_name_and_address|amendment|amendment_scopes"/>',
                position,
            )
        elif type == "bc":
            return self._insert_text(
                text,
                '<usdm:macro id="bc" name="bc name" activity="activity name"/>',
                position,
            )
        elif type == "section":
            return self._insert_text(
                text,
                '<usdm:macro id="section" name="title_page|inclusion|exclusion|objective_endpoints|soa" template="m11|plain"/>',
                position,
            )
        elif type == "timeline":
            return self._insert_text(
                text,
                '<usdm:macro id="section" name="timeline" template="m11|plain" timeline="..."/>',
                position,
            )
        elif type == "note":
            return self._insert_text(
                text, '<usdm:macro id="note" text="note text"/>', position
            )
        elif type == "list-item":
            return self._insert_list_item(text, position)
        elif type == "table":
            return self._insert_text(
                text, '<table class="table align-top"></table>', position
            )
        elif type == "table-row":
            return text
        elif type == "table-cell":
            return self._insert_cell_item(text, position)
        else:
            application_logger.error(f"Failed to recognize usdm type '{type}'")
            return text

    def _insert_text(self, s, i, index):
        return s[:index] + i + s[index:]

    def _insert_list_item(self, s: str, index):
        return self._insert_item(s, index, "li")

    def _insert_cell_item(self, s: str, index):
        return self._insert_item(s, index, "td")

    def _insert_item(self, s: str, index: int, tag: str):
        sub_s = s[index:]
        match = re.search(r"^<p>(.*?)</p>", sub_s)
        print(f"PARA: {match}")
        if match:
            para = match.group(0)
            new_text = s[:index] + f"<{tag}>{para}</{tag}>" + s[index + len(para) :]
            print(f"NEW: {new_text}")
            return new_text
        else:
            return s

    def _decompose(self, data: dict, id_manager: IdManager) -> None:
        if isinstance(data, dict):
            if "id" in data and isinstance(data["id"], str):
                id_manager.check_id(data["id"]) 
            for key, value in data.items():
                if isinstance(value, dict):
                    self._decompose(value, id_manager)
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        self._decompose(item, id_manager)