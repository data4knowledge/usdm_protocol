import os
import re
import yaml
import threading 
import csv
import pandas as pd
from d4kms_generic.logger import application_logger

class Database:
  
  DIR = "database"
  FILEPATH = os.path.join(DIR, "protocol.yaml")

  def __init__(self):
    self._data = self._read()
    self._lock = threading.Lock()

  def toc_sections(self):
    try:
      self._lock.acquire()
      order = self._section_order()
      self._lock.release()
      return [{'key': x, 'sectionNumber': self._data[x]['sectionNumber'], 'sectionTitle': self._data[x]['sectionTitle']} for x in order]
    except Exception as e:
      application_logger.exception("Exception during toc sections", e)
      self._lock.release()
      return []

  def toc_level_1_sections(self):
    try:
      self._lock.acquire()
      order = self._section_order()
      self._lock.release()
      return [{'key': x, 'sectionNumber': self._data[x]['sectionNumber'], 'sectionTitle': self._data[x]['sectionTitle']} for x in order if self._level(self._data[x]['sectionNumber']) == 1]
    except Exception as e:
      application_logger.exception("Exception during toc level 1 sections", e)
      self._lock.release()
      return []

  def get_section(self, section_key):
    try:
      return self._data[section_key]
    except Exception as e:
      application_logger.exception("Exception during section read", e)
      return None

  def put_section(self, section_key, text):
    try:
      self._lock.acquire()
      section = self.get_section(section_key)
      if section:
        application_logger.info(f"Updatting section {section_key}")
        self._data[section_key]['text'] = text
        self._write()
      self._lock.release()
      return self._data[section_key]
    except Exception as e:
      application_logger.exception("Exception during section write", e)
      self._lock.release()

  def put_section_title(self, section_key, title):
    try:
      self._lock.acquire()
      section = self.get_section(section_key)
      if section:
        application_logger.info(f"Updatting section title {section_key}")
        self._data[section_key]['sectionTitle'] = title
        self._write()
      self._lock.release()
      return self._data[section_key]
    except Exception as e:
      application_logger.exception("Exception during put section title", e)
      self._lock.release()

  def insert_usdm(self, section_key: str, type: str, position: int) -> str:
    try:
      self._lock.acquire()
      section = self.get_section(section_key)
      if section:
        application_logger.info(f"USDM insert {section_key}, type {type}, @ {position}")
        self._data[section_key]['text'] = self._insert_usdm(self._data[section_key]['text'], type, position)
        self._write()
      self._lock.release()
      return self._data[section_key]
    except Exception as e:
      application_logger.exception("Exception during insert of USDM tag", e)
      self._lock.release()

  def delete_section(self, section_key):
    try:
      self._lock.acquire()
      section = self.get_section(section_key)
      if section:
        self._data.pop(section_key)
        self._write()
        result = True
      else:
        result = False
      self._lock.release()
      return result
    except Exception as e:
      application_logger.exception("Exception during section delete", e)
      self._lock.release()
      return False

  def can_add_sibling_section(self, section_key):
    potential_section_key = self._increment_section_number(section_key)
    return self._section_is_permitted(potential_section_key)

  def can_add_child_section(self, section_key):
    potential_section_key = self._child_section_number(section_key)
    return self._section_is_permitted(potential_section_key)

  def add_sibling_section(self, section_key):
    try:
      self._lock.acquire()
      new_section_key = self._increment_section_number(section_key)
      if self._section_is_permitted(new_section_key):
        self._data[new_section_key] = {'sectionNumber': new_section_key.replace('-', '.'), 'sectionTitle': 'To Be Provided', 'name': '', 'text': ''}
        self._write()
        result = new_section_key
      else:
        result = None
      self._lock.release()
      return result
    except Exception as e:
      application_logger.exception("Exception during section add", e)
      return None

  def add_child_section(self, section_key):
    try:
      self._lock.acquire()
      new_section_key = self._child_section_number(section_key)
      if self._section_is_permitted(new_section_key):
        self._data[new_section_key] = {'sectionNumber': new_section_key.replace('-', '.'), 'sectionTitle': 'To Be Provided', 'name': '', 'text': ''}
        self._write()
        result = new_section_key
      else:
        result = None
      self._lock.release()
      return result
    except Exception as e:
      application_logger.exception("Exception during section add", e)
      return None

  def download_csv(self):
    full_path = os.path.join(self.DIR, "protocol_section.csv")
    filename = os.path.basename(full_path)
    media_type = 'text/plain' 
    self._write_csv_file(full_path)
    return full_path, filename, media_type

  def download_excel(self):
    full_path = os.path.join(self.DIR, "protocol_section.xlsx")
    filename = os.path.basename(full_path)
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    self._write_excel_file(full_path)
    return full_path, filename, media_type

  def _write_csv_file(self, full_path):
    order = self._section_order()
    data = [{'name': self._data[x]['name'], 'text': self._data[x]['text'], 'sectionNumber': str(self._data[x]['sectionNumber']), 'sectionTitle': self._data[x]['sectionTitle']} for x in order]
    with open(full_path, "w") as f:
      writer = csv.DictWriter(f, fieldnames=['sectionNumber',	'name',	'sectionTitle',	'text'], quoting=csv.QUOTE_ALL)
      writer.writeheader()
      writer.writerows(data)

  def _write_excel_file(self, full_path):
    order = self._section_order()
    df = pd.DataFrame(columns=['sectionNumber',	'name',	'sectionTitle',	'text'])
    for x in order:
      row = {'name': self._data[x]['name'], 'text': self._data[x]['text'], 'sectionNumber': str(self._data[x]['sectionNumber']), 'sectionTitle': self._data[x]['sectionTitle']}
      df.loc[len(df)]=row
    with pd.ExcelWriter(full_path) as writer:
      df.to_excel(writer, sheet_name="studyDesignContent", header=True, index=False)
   
  def _level(self, section):
    text = section[:-1] if section.endswith('.') else section
    parts = text.split('.')
    return len(parts)
  
  def _read(self):
    with open(self.FILEPATH, "r") as f:
      data = yaml.safe_load(f)
    return data
  
  def _write(self):
    with open(self.FILEPATH, "w") as f:
      yaml.safe_dump(self._data, f)

  def _section_order(self):
    return sorted(list(self._data.keys()), key=self._section)

  def _section(self, s):
    try:
      return [int(_) for _ in s.split("-")]
    except Exception as e:
      application_logger.exception("Exception during numeric section formation", e)

  def _increment_section_number(self, section_key):
    parts = section_key.split('-')
    parts[-1] = str(int(parts[-1]) + 1)
    return '-'.join(parts)

  def _child_section_number(self, section_key):
    parts = section_key.split('-')
    parts.append('1')
    return '-'.join(parts)

  def _section_is_permitted(self, section_key):
    result = True if section_key not in self._data.keys() else False
    application_logger.info(f"Section is permitted for {section_key}={result}")
    return result

  def _insert_usdm(self, text: str, type: str, position: int) -> str:
    if type == "reference":
      return self._insert_text(text, '<usdm:ref klass="klass name" id="identifier" attribute="attribute name"/>', position)
    elif type == "tag":
      return self._insert_text(text, '<usdm:tag name="dictionary parameter tag name"/>', position)
    elif type == "xref":
      return self._insert_text(text, '<usdm:macro id="xref" klass="klass name" name="item name" attribute="attribute name"/>', position)
    elif type == "image":
      return self._insert_text(text, '<usdm:macro id="image" file="file name" type="png|jpg"/>', position)
    elif type == "element":
      return self._insert_text(text, '<usdm:macro id="element" name="study_phase|study_short_title|study_full_title|study_acronym|study_rationale|study_version_identifier|study_identifier|study_regulatory_identifiers|study_date|approval_date|organization_name_and_address|amendment|amendment_scopes"/>', position)
    elif type == "section":
      return self._insert_text(text, '<usdm:macro id="section" name="title_page|inclusion|exclusion|objective_endpoints|soa" template="m11|plain"/>', position)
    elif type == "timeline":
      return self._insert_text(text, '<usdm:macro id="section" name="timeline" template="m11|plain" timeline="..."/>', position)
    elif type == "note":
      return self._insert_text(text, '<usdm:macro id="note" text="note text"/>', position)
    elif type == "list-item":
      return self._insert_list_item(text, position)
    elif type == "table":
      return self._insert_text(text, '<table class="table align-top"></table>', position)
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
    return self._insert_item(s, index, 'li')

  def _insert_cell_item(self, s: str, index):
    return self._insert_item(s, index, 'td')

  def _insert_item(self, s: str, index: int, tag: str):
    sub_s = s[index:]
    match = re.search(r'^<p>(.*?)</p>', sub_s)
    print(f"PARA: {match}")
    if match:
      para = match.group(0)
      new_text = s[:index] + f"<{tag}>{para}</{tag}>" + s[index+len(para):]
      print(f"NEW: {new_text}")
      return new_text
    else:
      return s
