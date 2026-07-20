import zipfile
with zipfile.ZipFile('agents/cam-agent/trinetra_cam_template.docx') as z:
    xml = z.read('word/document.xml').decode('utf-8')
import re
print("Matches for 'for':", re.findall(r'.{0,40}for.{0,40}', xml))
print("Matches for 'peer':", re.findall(r'.{0,40}peer.{0,40}', xml))
