import re

def update_agent(path, setup_code, usage_code, before_return=True):
    try:
        with open(path, "r") as f:
            content = f.read()
        if "VectorAIClient" in content:
            return
        
        # Add import
        content = content.replace(
            "from shared.agent_base import BaseAgent",
            "from shared.agent_base import BaseAgent\nfrom shared.vectorai_client import VectorAIClient\n\nvectorai = VectorAIClient()"
        )
        
        if before_return:
            # Find return inside process()
            parts = content.split("return {")
            if len(parts) > 1:
                content = parts[0] + usage_code + "\n        return {" + parts[1]
                
        with open(path, "w") as f:
            f.write(content)
        print(f"Updated {path}")
    except Exception as e:
        print(f"Error {path}: {e}")

# Risk Agent
risk_usage = """
        # Actian VectorAI
        normalized_features = self.normalize_financials(applicant, financials)
        feature_text = " ".join([f"{k}={v:.4f}" for k, v in normalized_features.items()])
        vectorai.upsert(
            collection="risk_decisions",
            doc_id=f"{application_id}_risk",
            text=f"Risk decision: score={score}, band={band}, decision={decision}. Features: {feature_text}",
            metadata={
                "application_id": application_id,
                "agent": "risk-agent",
                "risk_score": score,
                "risk_band": band,
                "decision": decision,
            }
        )
"""
update_agent("agents/risk-agent/main.py", "", risk_usage)

# Bias Agent
bias_usage = """
        vectorai.upsert(
            collection="application_summaries",
            doc_id=f"{application_id}_bias",
            text=f"Bias check: {len(flip_features)} flips",
            metadata={
                "application_id": application_id,
                "agent": "bias-agent",
                "phase": "bias",
            }
        )
"""
update_agent("agents/bias-agent/main.py", "", bias_usage)

# Stress Agent
stress_usage = """
        vectorai.upsert(
            collection="stress_scenarios",
            doc_id=f"{application_id}_stress",
            text=f"Stress test: worst_dscr={worst_dscr:.4f}, verdict={survival_verdict}",
            metadata={
                "application_id": application_id,
                "agent": "stress-agent",
                "worst_dscr": worst_dscr,
                "survival_verdict": survival_verdict,
            }
        )
"""
update_agent("agents/stress-agent/main.py", "", stress_usage)

# CAM Agent
cam_usage = """
        vectorai.upsert(
            collection="application_summaries",
            doc_id=f"{application_id}_cam",
            text=f"CAM generated for application",
            metadata={
                "application_id": application_id,
                "agent": "cam-agent",
                "phase": "cam",
            }
        )
"""
update_agent("agents/cam-agent/main.py", "", cam_usage)

# Monitor Agent
monitor_usage = """
        vectorai.upsert(
            collection="audit_events",
            doc_id=f"{application_id}_audit_{now.replace(':', '').replace('-', '')}",
            text=f"Health check for {application_id}: {len(alerts)} alerts",
            metadata={
                "application_id": application_id,
                "agent": "monitor-agent",
                "alert_count": len(alerts),
            }
        )
"""
update_agent("agents/monitor-agent/main.py", "", monitor_usage)

# GST Agent
gst_usage = """
        vectorai.upsert(
            collection="gst_patterns",
            doc_id=f"{application_id}_gst",
            text=f"GST reconciliation: status={status}",
            metadata={
                "application_id": application_id,
                "agent": "gst-agent",
                "status": status,
            }
        )
"""
update_agent("agents/gst-agent/main.py", "", gst_usage)

# Bank Recon Agent
bank_usage = """
        vectorai.upsert(
            collection="bank_recon_profiles",
            doc_id=f"{application_id}_bank_recon",
            text=f"Bank reconciliation: verdict={verdict}",
            metadata={
                "application_id": application_id,
                "agent": "bank-recon-agent",
                "verdict": verdict,
            }
        )
"""
update_agent("agents/bank-recon-agent/main.py", "", bank_usage)

# PAN Agent
pan_usage = """
        vectorai.upsert(
            collection="pan_profiles",
            doc_id=f"{application_id}_pan",
            text=f"PAN verification: {pan}",
            metadata={
                "application_id": application_id,
                "agent": "pan-verification-agent",
                "pan": pan,
            }
        )
"""
update_agent("agents/pan-agent/main.py", "", pan_usage)

# PD Agent
pd_usage = """
        vectorai.upsert(
            collection="pd_transcripts",
            doc_id=f"{application_id}_pd",
            text=transcript_text[:2000],
            metadata={
                "application_id": application_id,
                "agent": "pd-transcript-agent",
            }
        )
"""
update_agent("agents/pd-agent/main.py", "", pd_usage)

# Compliance Agent
comp_usage = """
        vectorai.upsert(
            collection="application_summaries",
            doc_id=f"{application_id}_compliance",
            text=f"Compliance check",
            metadata={
                "application_id": application_id,
                "agent": "compliance-agent",
                "phase": "compliance",
            }
        )
"""
update_agent("agents/compliance-agent/main.py", "", comp_usage)

# Model Selector Agent
model_usage = """
        vectorai.upsert(
            collection="application_summaries",
            doc_id=f"{application_id}_model_selection",
            text=f"Model selected: {model_name}",
            metadata={
                "application_id": application_id,
                "agent": "model-selector-agent",
                "model_used": model_name,
                "phase": "model_selection",
            }
        )
"""
update_agent("agents/model-selector-agent/main.py", "", model_usage)

