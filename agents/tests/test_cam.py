import os
import importlib.util
import pytest

def load_cam_agent():
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(tests_dir)
    spec_path = os.path.join(agents_dir, "cam-agent", "main.py")
    spec = importlib.util.spec_from_file_location("cam_agent", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_cam_document_generation(sample_ucso):
    """Tests compiling the underwriting profile into both DOCX and PDF formats."""
    cam_agent = load_cam_agent()
    
    # Generate DOCX and PDF
    docx_path, pdf_path = cam_agent.generate_cam_document(sample_ucso, sample_ucso["application_id"])
    
    try:
        # Check DOCX file
        assert os.path.exists(docx_path)
        docx_size = os.path.getsize(docx_path)
        assert docx_size > 1024
        
        # Check PDF file
        assert os.path.exists(pdf_path)
        pdf_size = os.path.getsize(pdf_path)
        assert pdf_size > 1024
    finally:
        # Cleanup
        if os.path.exists(docx_path):
            os.unlink(docx_path)
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)
