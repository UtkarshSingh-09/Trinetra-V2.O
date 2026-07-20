import re
pat = r"<w:tr[ >](?:(?!<w:tr[ >]).)*({%|{{)tr ([^}%]*(?:%}|}})).*?</w:tr>"
xml = '<w:tr><w:tc><w:p><w:r><w:t>{%tr for peer in peer_companies %}{{ peer.name }}</w:t></w:r></w:p></w:tc></w:tr>'
print(re.sub(pat, r"\1 \2", xml, flags=re.DOTALL))
