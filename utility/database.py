import os
import yaml
import threading 
from d4kms_generic.logger import application_logger

class Database:
  
  DIR = "database"
  FILEPATH = os.path.join(DIR, "protocol.yaml")

  def __init__(self):
    self._data = self._read()
    self._lock = threading.Lock()

  def toc_sections(self):
    order = self._section_order()
    #print(f"ORDER: {order}")
    return [{'key': x, 'sectionNumber': self._data[x]['sectionNumber'], 'sectionTitle': self._data[x]['sectionTitle']} for x in order]

  def toc_level_1_sections(self):
    order = self._section_order()
    return [{'key': x, 'sectionNumber': self._data[x]['sectionNumber'], 'sectionTitle': self._data[x]['sectionTitle']} for x in order if self._level(self._data[x]['sectionNumber']) == 1]

  def get_section(self, section_key):
    try:
      return self._data[section_key]
    except Exception as e:
      application_logger.exception("Exception during section read", e)
      return None

  def put_section(self, section_key, text):
    section = self.get_section(section_key)
    if section:
      try:
        application_logger.info(f"Updatting section {section_key}")
        self._lock.acquire()
        self._data[section_key]['text'] = text
        self._write()
        self._lock.release()
      except Exception as e:
        application_logger.exception("Exception during section write", e)
        self._lock.release()

  def delete_section(self, section_key):
    section = self.get_section(section_key)
    if section:
      try:
        self._lock.acquire()
        self._data.pop(section_key)
        self._write()
        self._lock.release()
        return True
      except Exception as e:
        application_logger.exception("Exception during section delete", e)
        self._lock.release()
    return False

  def can_add_section(self, section_key):
    potential_section_key = self._increment_section_number(section_key)
    return self._section_is_permitted(potential_section_key)
  
  def add_section(self, section_key):
    new_section_key = self._increment_section_number(section_key)
    if self._section_is_permitted(new_section_key):
      try:
        self._lock.acquire()
        self._data[new_section_key] = {'sectionNumber': new_section_key.replace('-', '.'), 'sectionTitle': 'To Be Provided', 'name': '', 'text': ''}
        self._write()
        self._lock.release()
        return new_section_key
      except Exception as e:
        application_logger.exception("Exception during section add", e)
    return None

  def _level(self, section):
    text = section[:-1] if section.endswith('.') else section
    parts = text.split('.')
    return len(parts)
  
  def _read(self):
    with open(self.FILEPATH, "r") as f:
      data = yaml.load(f, Loader=yaml.FullLoader)
    return data
  
  def _write(self):
    with open(self.FILEPATH, "w") as f:
      yaml.dump(self._data, f)

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

  def _section_is_permitted(self, section_key):
    result = True if section_key not in self._data.keys() else False
    application_logger.info(f"Section is permitted for {section_key}={result}")
    return result
