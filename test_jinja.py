import jinja2
try:
    jinja2.Template("{%tr endfor %}")
except Exception as e:
    print(repr(e))
try:
    jinja2.Template("{%tr for %}")
except Exception as e:
    print(repr(e))
