import docx

doc = docx.Document("agents/cam-agent/trinetra_cam_template.docx")
for table in doc.tables:
    for row in table.rows:
        for cell in row.cells:
            if "PAN, Aadhaar, and GSTIN matching completed successfully" in cell.text:
                cell.text = cell.text.replace("PAN, Aadhaar, and GSTIN matching completed successfully", "{{ kyc_alignment_status }}")
            if "Missing Documents" in cell.text:
                # The next cell usually contains the value, let's find it.
                pass
            if cell.text.strip() == "None" or cell.text.strip() == "None.":
                # Only replace if it's adjacent to Missing Documents or similar?
                # Actually, let's just replace all "None" in the specific tables with Jinja tags?
                pass

doc.save("agents/cam-agent/trinetra_cam_template.docx")
print("Template modified successfully.")
