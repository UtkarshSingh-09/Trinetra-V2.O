import re
with open('/Users/utkarshsingh/Desktop/Trinetra/.venv/lib/python3.14/site-packages/docxtpl/template.py') as f:
    text = f.read()
matches = re.finditer(r're\.compile\(.*?\)', text)
for m in matches:
    print(m.group(0))
