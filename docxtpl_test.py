import docxtpl.template
with open("/Users/utkarshsingh/Desktop/Trinetra/.venv/lib/python3.14/site-packages/docxtpl/template.py") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'tr ' in line or 'patch_xml' in line:
        pass # just to remind me, let's search for tr matching
