import os
import yaml
import threading 

class Database:
  
  DIR = "database"
  FILEPATH = os.path.join(DIR, "protocol.yaml")

  def __init__(self):
    self._data = self._read()
    self._lock = threading.Lock()

  def toc_sections(self):
    return [{'key': k, 'sectionNumber': x['sectionNumber'], 'sectionTitle': x['sectionTitle']} for k,x in self._data.items()]

  def toc_level_1_sections(self):
    return [{'key': k, 'sectionNumber': x['sectionNumber'], 'sectionTitle': x['sectionTitle']} for k,x in self._data.items() if self._level(x['sectionNumber']) == 1]

  def get_section(self, section_key):
    try:
      return self._data[section_key]
    except:
      return None

  def put_section(self, section_key, text):
    section = self.get_section(section_key)
    print(f"PUT SECT: {section}")
    if section:
      try:
        self._lock.acquire()
        self._data[section_key]['text'] = text
        self._write()
        self._lock.release()
      except:
        self._lock.release()

  def delete_section(self, section_key):
    section = self.get_section(section_key)
    if section:
      try:
        self._lock.acquire()
        self._data.pop(section_key)
        self._write()
        self._lock.release()
      except:
        self._lock.release()

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
      data = yaml.dump(self._data, f)
