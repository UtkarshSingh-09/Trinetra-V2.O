import glob
for file in glob.glob("agents/*/main.py"):
    with open(file, "r") as f:
        text = f.read()

    # We need to find the "vectorai.upsert" that we injected, and indent it correctly.
    # Our injected code has 8 spaces indentation: "        vectorai.upsert("
    # Let's replace "        vectorai.upsert(" with "            vectorai.upsert(" 
    # and "        )" with "            )"
    text = text.replace("        # Actian VectorAI", "            # Actian VectorAI")
    text = text.replace("        normalized_features =", "            normalized_features =")
    text = text.replace("        feature_text =", "            feature_text =")
    text = text.replace("        vectorai.upsert(", "            vectorai.upsert(")
    text = text.replace("            collection=", "                collection=")
    text = text.replace("            doc_id=", "                doc_id=")
    text = text.replace("            text=", "                text=")
    text = text.replace("            metadata={", "                metadata={")
    text = text.replace("                \"application_id\":", "                    \"application_id\":")
    text = text.replace("                \"agent\":", "                    \"agent\":")
    text = text.replace("                \"phase\":", "                    \"phase\":")
    text = text.replace("                \"risk_score\":", "                    \"risk_score\":")
    text = text.replace("                \"risk_band\":", "                    \"risk_band\":")
    text = text.replace("                \"decision\":", "                    \"decision\":")
    text = text.replace("                \"worst_dscr\":", "                    \"worst_dscr\":")
    text = text.replace("                \"survival_verdict\":", "                    \"survival_verdict\":")
    text = text.replace("                \"alert_count\":", "                    \"alert_count\":")
    text = text.replace("                \"status\":", "                    \"status\":")
    text = text.replace("                \"verdict\":", "                    \"verdict\":")
    text = text.replace("                \"pan\":", "                    \"pan\":")
    text = text.replace("                \"model_used\":", "                    \"model_used\":")
    text = text.replace("            }", "                }")
    # but the closing parenthesis for upsert was also 8 spaces
    text = text.replace("\n        )\n", "\n            )\n")
    # the return { was restored as "        return {"
    text = text.replace("\n        return {", "\n            return {")

    with open(file, "w") as f:
        f.write(text)
