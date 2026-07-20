import pytest

def test_compliance_all_files_uploaded(sample_ucso):
    """Verifies compliance passes when all 4 files are present."""
    files = sample_ucso["documents"]["files"]
    required = {"ANNUAL_REPORT", "BANK_STMT", "GST_RETURN", "ITR"}
    uploaded = {f.get("type") for f in files if f.get("status") == "UPLOADED"}
    missing = required - uploaded
    
    status = "PASSED" if not missing else "PARTIAL"
    assert status == "PASSED"
    assert len(missing) == 0

def test_compliance_missing_files(sample_ucso):
    """Verifies compliance flags missing files when documents are partial."""
    # Remove ITR from files
    sample_ucso["documents"]["files"] = [
        f for f in sample_ucso["documents"]["files"] if f["type"] != "ITR"
    ]
    
    files = sample_ucso["documents"]["files"]
    required = {"ANNUAL_REPORT", "BANK_STMT", "GST_RETURN", "ITR"}
    uploaded = {f.get("type") for f in files if f.get("status") == "UPLOADED"}
    missing = required - uploaded
    
    status = "PASSED" if not missing else "PARTIAL"
    assert status == "PARTIAL"
    assert "ITR" in missing
