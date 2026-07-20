from docxtpl.template import DocxTemplate
doc = DocxTemplate("agents/cam-agent/trinetra_cam_template.docx")

import docxtpl.template
original_render_xml_part = doc.render_xml_part
def fake_render(src_xml, part, context, jinja_env=None):
    if '{%tr for' in src_xml or '{% tr for' in src_xml:
        print("IT IS IN THE XML BUT NOT AS A TAG")
    else:
        print("IT IS COMPLETELY GONE")
    
    with open("debug.xml", "w") as f:
        f.write(src_xml)
        
    return original_render_xml_part(src_xml, part, context, jinja_env)

doc.render_xml_part = fake_render
try:
    doc.render({})
except Exception as e:
    pass
