import re
import docxtpl
from docxtpl.template import DocxTemplate
doc = DocxTemplate("agents/cam-agent/trinetra_cam_template.docx")
doc.init_docx()
xml = doc.xml_to_string(doc.docx._element.body)
pat = r"{%tr.*?(?:%}|}})"
for m in re.finditer(pat, xml):
    print(repr(m.group(0)))
