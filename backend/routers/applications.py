import os
import json
import random
import glob
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Form, File, UploadFile, Response, Header
from anyio.to_thread import run_sync
from core import storage, redis_broker, ws_manager, ALLOWED_NAMESPACES
from dependencies import get_current_user_or_agent, check_tenant_access
from models import (
    ApplicationCreate,
    ApplicationResponse,
    NoteRequest,
    StressTriggerRequest,
    FeedbackRequest,
    PDTranscriptRequest,
)

router = APIRouter(tags=["Applications"])
logger = logging.getLogger("trinetra-backend.applications")

@router.post("/api/application", response_model=ApplicationResponse)
async def create_application(payload: ApplicationCreate, current_user: dict = Depends(get_current_user_or_agent)):
    """
    Create a new loan application.
    Initializes the UCSO with 14 empty agent namespaces.
    """
    try:
        applicant_data = payload.model_dump()
        tenant_id = current_user.get("tenant_id", "tenant_alpha")
        result = await storage.create_application(applicant_data, tenant_id)

        app_id = result["id"]
        logger.info(f"📋 Application created: {app_id} (tenant: {tenant_id})")

        return ApplicationResponse(
            id=app_id,
            status="CREATED",
            message="Application created. Upload documents to trigger AI pipeline.",
        )
    except Exception as e:
        logger.error(f"Failed to create application: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create application: {str(e)}")

@router.get("/api/application/{application_id}")
async def get_application(application_id: str, current_user: dict = Depends(get_current_user_or_agent)):
    """
    Fetch the full UCSO for an application.
    Used by both frontend (UI rendering) and agents (data fetching).
    """
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)
            
    ucso = app.get("ucso_data", {})
    if not ucso:
        raise HTTPException(status_code=404, detail="Application UCSO data not found")
    return ucso

@router.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    application_id: str = Form(...),
    type: str = Form("DOCUMENT"),
    current_user: dict = Depends(get_current_user_or_agent),
):
    """
    Upload a file (PDF, DOCX, etc.) to configured storage.
    Appends file metadata to the UCSO's documents.files array.
    After upload, publishes 'application_created' event to trigger AI pipeline.
    """
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)

    try:
        file_bytes = await file.read()
        filename = file.filename or "uploaded_file"

        result = await storage.upload_file(application_id, file_bytes, filename, type)
        
        logger.info(
            f"📤 File uploaded: {filename} ({len(file_bytes)} bytes) → "
            f"Storage: {result['storage_path']} | Event queued via Transactional Outbox"
        )

        return {
            "storage_path": result["storage_path"],
            "file_url": result["file_url"],
            "s3_key": result["storage_path"],  # Backward compatibility for agents
            "status": "UPLOADED",
        }
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@router.patch("/api/application/{application_id}/namespace/{namespace}")
async def patch_namespace(
    application_id: str,
    namespace: str,
    data: dict,
    x_idempotency_key: str | None = Header(default=None),
    current_user: dict = Depends(get_current_user_or_agent),
):
    """
    Patch a specific namespace within the UCSO.
    Exclusively used by Python AI agents to inject their results.
    """
    if namespace not in ALLOWED_NAMESPACES:
        raise HTTPException(status_code=400, detail=f"Invalid namespace '{namespace}'")
        
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
        
    check_tenant_access(app, current_user)

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")
    if len(data.keys()) == 0:
        raise HTTPException(status_code=400, detail="Payload cannot be empty")

    try:
        result = await storage.patch_namespace(
            application_id,
            namespace,
            data,
            x_idempotency_key,
        )
        logger.info(f"✏️ PATCH {namespace} for {application_id[:8]}... ({list(data.keys())})")
        return result.get("ucso_data", result) if isinstance(result, dict) else result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Namespace patch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Namespace patch failed: {str(e)}")

@router.get("/api/files/{application_id}")
async def get_file(
    application_id: str,
    filename: str = Query(None, description="Specific filename to download (e.g. CAM.docx)"),
    current_user: dict = Depends(get_current_user_or_agent),
):
    """
    Download a file for an application.
    Default: prioritizes .pdf files.
    """
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)

    try:
        result = await run_sync(storage.get_file, application_id, filename)
        if not result:
            raise HTTPException(status_code=404, detail="File not found")

        file_bytes, actual_filename = result

        content_type = "application/octet-stream"
        if actual_filename.lower().endswith(".pdf"):
            content_type = "application/pdf"
        elif actual_filename.lower().endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={actual_filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File retrieval failed: {str(e)}")

@router.get("/api/files/download")
async def get_file_by_key(
    s3_key: str = Query(..., description="Storage path key, e.g. app_id/TYPE/file.pdf"),
    current_user: dict = Depends(get_current_user_or_agent),
):
    """Download a file by storage path key. Added for PD/audio compatibility."""
    app_id = s3_key.split("/")[0] if "/" in s3_key else None
    if app_id:
        app = await storage.get_application(app_id)
        if app:
            check_tenant_access(app, current_user)

    try:
        result = await run_sync(storage.get_file_by_key, s3_key)
        if not result:
            raise HTTPException(status_code=404, detail="File not found")

        file_bytes, actual_filename = result
        content_type = "application/octet-stream"
        if actual_filename.lower().endswith(".pdf"):
            content_type = "application/pdf"
        elif actual_filename.lower().endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif actual_filename.lower().endswith(".mp3"):
            content_type = "audio/mpeg"

        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={actual_filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File download by key failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"File download by key failed: {str(e)}")

@router.post("/api/application/{application_id}/notes")
async def add_notes(
    application_id: str,
    payload: NoteRequest,
    current_user: dict = Depends(get_current_user_or_agent),
):
    """Add a human note from the credit officer."""
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)

    try:
        ucso = await storage.add_note(application_id, payload.note, payload.author)
        logger.info(f"📝 Note added for {application_id[:8]}... by {payload.author}")
        return {"status": "OK", "note_count": len(ucso.get("human_notes", {}).get("notes", []))}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add note: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add note: {str(e)}")

@router.post("/api/application/{application_id}/stress")
async def trigger_stress_test(
    application_id: str,
    payload: StressTriggerRequest,
    current_user: dict = Depends(get_current_user_or_agent),
):
    """Re-trigger the Stress Agent with custom parameters."""
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)

    try:
        interest_rate_hike = payload.interest_rate_hike
        if payload.interest_rate_hike_bps is not None:
            interest_rate_hike = payload.interest_rate_hike_bps / 100.0

        revenue_drop_pct = payload.revenue_drop_pct
        if payload.revenue_shock_pct is not None:
            revenue_drop_pct = abs(payload.revenue_shock_pct)

        # Queue outbox event
        await storage.add_outbox_event(
            "stress_retrigger",
            {
                "application_id": application_id,
                "interest_rate_hike": interest_rate_hike,
                "revenue_drop_pct": revenue_drop_pct,
            }
        )
        logger.info(
            f"🔄 Stress re-trigger for {application_id[:8]}... (Outbox Queued) "
            f"(rate+{interest_rate_hike}%, rev-{revenue_drop_pct}%)"
        )
        return {"status": "TRIGGERED", "message": "Stress agent will re-process with new parameters"}
    except Exception as e:
        logger.error(f"Stress test trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stress test trigger failed: {str(e)}")

@router.post("/api/application/{application_id}/pd")
async def trigger_pd(
    application_id: str,
    payload: PDTranscriptRequest,
    current_user: dict = Depends(get_current_user_or_agent),
):
    """Re-trigger the PD Transcript Agent with a new transcript."""
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)

    try:
        # Save transcript to human notes first
        await storage.add_note(
            application_id,
            note=payload.transcript,
            author=payload.interviewer or "Officer"
        )
        
        # Queue outbox event
        await storage.add_outbox_event(
            "pd_submitted",
            {
                "application_id": application_id,
            }
        )
        logger.info(f"🎤 PD re-trigger for {application_id[:8]}... (Outbox Queued)")
        return {"status": "TRIGGERED", "message": "PD agent will re-process"}
    except Exception as e:
        logger.error(f"PD transcript trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PD transcript trigger failed: {str(e)}")

@router.post("/api/application/{application_id}/feedback")
async def save_application_feedback(
    application_id: str,
    payload: FeedbackRequest,
    current_user: dict = Depends(get_current_user_or_agent),
):
    """
    Log manual override/actual performance feedback (PAID_BACK or DEFAULTED) for a loan application.
    """
    actual_outcome = payload.actual_outcome
    notes = payload.notes
    
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)
            
    feedback_data = {
        "feedback": {
            "actual_outcome": actual_outcome,
            "notes": notes,
            "updated_by": current_user.get("username", "underwriter"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        result = await storage.patch_namespace(application_id, "risk", feedback_data)
        await storage.append_event(application_id, {
            "event": "human_feedback_submitted",
            "actual_outcome": actual_outcome,
            "updated_by": current_user.get("username", "underwriter"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"🎯 Human feedback submitted for {application_id[:8]}... Outcome: {actual_outcome}")
        return result.get("ucso_data", result) if isinstance(result, dict) else result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")

@router.get("/api/applications")
async def list_applications(current_user: dict = Depends(get_current_user_or_agent)):
    """List all applications (for dashboard)."""
    try:
        is_admin = current_user.get("role") == "admin"
        is_system = current_user.get("role") == "system"
        user_tenant = current_user.get("tenant_id")

        if hasattr(storage, "Session"):
            from storage.postgres_adapter import DBApplication
            from sqlalchemy import select
            
            async with storage.Session() as session:
                stmt = select(DBApplication)
                if not is_admin and not is_system:
                    stmt = stmt.filter_by(tenant_id=user_tenant)
                stmt = stmt.order_by(DBApplication.created_at.desc()).limit(50)
                res = await session.execute(stmt)
                db_apps = res.scalars().all()
                
                records = []
                for app in db_apps:
                    records.append({
                        "id": app.id,
                        "company_name": app.company_name,
                        "pan": app.pan,
                        "status": app.status,
                        "created_at": app.created_at.isoformat() if app.created_at else None,
                        "ucsoData": app.ucso_data or {},
                        "tenant_id": app.tenant_id,
                    })
                return records

        if hasattr(storage, "client") and hasattr(storage.client, "table"):
            result = storage.client.table("applications").select(
                "id, company_name, pan, status, created_at, tenant_id"
            ).order("created_at", desc=True).limit(50).execute()
            data = result.data or []
            if not is_admin and not is_system:
                data = [r for r in data if r.get("tenant_id", "tenant_alpha") == user_tenant]
            return data
        if hasattr(storage, "app_dir"):
            records = []
            for name in os.listdir(storage.app_dir):
                if not name.endswith(".json"):
                    continue
                full_path = os.path.join(storage.app_dir, name)
                try:
                    with open(full_path, "r", encoding="utf-8") as fh:
                        row = json.load(fh)
                except Exception as read_err:
                    logger.warning(f"Skipping corrupted app file {name}: {read_err}")
                    continue
                
                tenant_id = row.get("tenant_id")
                if not tenant_id:
                    tenant_id = "tenant_alpha"

                records.append({
                    "id": row.get("id"),
                    "company_name": row.get("company_name", ""),
                    "pan": row.get("pan", ""),
                    "status": row.get("status", "CREATED"),
                    "created_at": row.get("created_at"),
                    "ucsoData": row.get("ucso_data", {}),
                    "tenant_id": tenant_id,
                })
            records.sort(key=lambda item: item.get("created_at") or "", reverse=True)
            if not is_admin and not is_system:
                records = [r for r in records if r.get("tenant_id") == user_tenant]
            return records[:50]
        return []
    except Exception as e:
        logger.error(f"Failed to list applications: {e}", exc_info=True)
        return []

@router.post("/api/demo/trigger")
async def trigger_demo_application(current_user: dict = Depends(get_current_user_or_agent)):
    """
    Creates a new application seeded with a high-fidelity synthetic company profile.
    Populates all necessary namespaces and triggers the risk agent directly.
    """
    import random
    import glob
    
    # Locate all company JSONs in synthetic_data
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    companies_dir = os.path.join(base_dir, "synthetic_data", "companies")
    companies_path = os.path.join(companies_dir, "*.json")
    files = glob.glob(companies_path)
    if not files:
        raise HTTPException(
            status_code=400, 
            detail=f"No synthetic data found at {companies_dir}. Please run the synthetic dataset generator first."
        )
        
    # Select a random company
    selected_file = random.choice(files)
    try:
        with open(selected_file, "r") as f:
            company_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read synthetic company file: {e}")
        
    comp_id = company_data["company_id"]
    
    # Load corresponding files
    fin_path = os.path.join(base_dir, "synthetic_data", "financials", f"{comp_id}_financials.json")
    gstr_path = os.path.join(base_dir, "synthetic_data", "financials", f"{comp_id}_gstr.json")
    bank_path = os.path.join(base_dir, "synthetic_data", "financials", f"{comp_id}_bank.json")
    
    try:
        with open(fin_path, "r") as f:
            fin_data = json.load(f)
        with open(gstr_path, "r") as f:
            gstr_data = json.load(f)
        with open(bank_path, "r") as f:
            bank_data = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load corresponding financials for company: {comp_id}. Error: {str(e)}"
        )
        
    # Create applicant payload
    applicant_payload = {
        "company_name": company_data["company_name"],
        "industry_sector": company_data["industry_sector"],
        "pan": company_data["pan"],
        "cin": company_data["cin"],
        "gstin": company_data["gstin"],
        "registered_state": company_data["registered_state"],
        "loan_amount_requested": random.randint(10, 50) * 100000, # 10L - 50L
        "turnover_class": company_data["turnover_class"],
        "employee_count": company_data["employee_count"],
        "incorporation_date": company_data["incorporation_date"]
    }
    
    # 1. Create the application in storage
    tenant_id = current_user.get("tenant_id", "tenant_alpha")
    result = await storage.create_application(applicant_payload, tenant_id)
    app_id = result["id"]
    
    # 2. Seed namespaces
    # Derived features
    derived_data = {
        "dscr": fin_data["dscr"],
        "icr": fin_data["icr"],
        "leverage": fin_data["leverage"],
        "current_ratio": fin_data["current_ratio"],
        "revenue_growth": fin_data["revenue_growth_yoy"],
        "ebitda_margin": fin_data["ebitda_margin"],
        "ltv_ratio": fin_data["ltv_ratio"],
        "cibil_score": fin_data["cibil_score"],
        "promoter_holding_pct": fin_data["promoter_holding_pct"],
        "years_in_business": fin_data["years_in_business"]
    }
    await storage.patch_namespace(app_id, "derived_features", derived_data)
    
    # GST Analysis
    gst_status = "OK"
    if gstr_data["overall_discrepancy_pct"] > 10.0:
        gst_status = "WARNING"
    gst_data_payload = {
        "gstr2b_vs_3b_discrepancy_pct": gstr_data["overall_discrepancy_pct"],
        "circular_trade_index": 0.08 if company_data["is_fraudulent"] else 0.0,
        "suspicious_cycles": [],
        "reconciliation_status": gst_status,
        "itc_mismatch_flag": gstr_data["overall_discrepancy_pct"] > 10.0,
        "gstin_verification": {
            "valid": True,
            "status": "ACTIVE",
            "legal_name": company_data["company_name"],
            "business_type": company_data["entity_type"],
            "registration_date": "2018-04-15",
            "source": "DEMO_AUTO_VERIFIED"
        }
    }
    await storage.patch_namespace(app_id, "gst_analysis", gst_data_payload)
    
    # Bank Reconciliation
    bank_status = "OK"
    if bank_data["bounce_count"] > 3:
        bank_status = "WARNING"
    bank_data_payload = {
        "reconciliation_verdict": bank_status,
        "bounce_rate": fin_data["bounce_rate"],
        "bank_divergence_pct": fin_data["bank_divergence_pct"],
        "avg_monthly_balance": bank_data["avg_monthly_balance"],
        "ending_balance": bank_data["ending_balance"],
        "bounce_count": bank_data["bounce_count"],
        "bounce_count_last_12m": bank_data["bounce_count"],
        "reconciliation_status": bank_status,
        "turnover_divergence_pct": fin_data["bank_divergence_pct"],
        "revenue_inflation_flag": fin_data["bank_divergence_pct"] > 10.0,
        "bank_credit_turnover": fin_data.get("revenue_annual", [0])[-1] if fin_data.get("revenue_annual") else 0,
        "gst_reported_turnover": fin_data.get("revenue_annual", [0])[-1] if fin_data.get("revenue_annual") else 0,
        "itr_reported_income": fin_data.get("net_profit_annual", [0])[-1] if fin_data.get("net_profit_annual") else 0,
        "round_trip_transactions": [],
    }
    await storage.patch_namespace(app_id, "bank_reconciliation", bank_data_payload)
    
    # Web Intelligence
    web_data_payload = {
        "promoter_news": [
            {
                "headline": f"Industry report reviews {company_data['company_name']} growth projections",
                "source_url": "https://example.com/industry-news",
                "credibility_score": 4,
                "sentiment_score": fin_data["web_sentiment_avg"],
                "risk_contribution": round((1 - fin_data["web_sentiment_avg"]) / 2, 4),
                "published_at": "2026-03-01T12:00:00Z",
                "entity_tags": [company_data["company_name"]]
            }
        ],
        "litigation_records": [],
        "regulatory_flags": [],
        "sector_headwinds": [],
        "kb_query_timestamp": datetime.now(timezone.utc).isoformat(),
        "kb_freshness_hours": 24
    }
    await storage.patch_namespace(app_id, "web_intel", web_data_payload)
    
    # PD Intelligence
    await storage.patch_namespace(app_id, "pd_intelligence", {"risk_adjustment": 0.0})
    
    # Financials (needed by CAM report and derived features display)
    financials_payload = {
        "revenue_annual": fin_data.get("revenue_annual", []),
        "ebitda_annual": fin_data.get("ebitda_annual", []),
        "net_profit_annual": fin_data.get("net_profit_annual", []),
        "total_debt": fin_data.get("total_debt", 0),
        "net_worth": fin_data.get("net_worth", 0),
        "interest_expense": fin_data.get("interest_expense", 0),
        "principal_repayment": fin_data.get("principal_repayment") or (fin_data.get("total_debt", 0) * 0.12),
        "operating_expenses": fin_data.get("operating_expenses") or (
            (fin_data.get("revenue_annual", [0])[-1] if fin_data.get("revenue_annual") else 0)
            - (fin_data.get("ebitda_annual", [0])[-1] if fin_data.get("ebitda_annual") else 0)
        ),
        "itr_taxable_income": fin_data.get("itr_taxable_income") or (
            fin_data.get("net_profit_annual", [0])[-1] if fin_data.get("net_profit_annual") else 0
        ),
        "cibil_score": fin_data.get("cibil_score", 650),
        "promoter_holding_pct": fin_data.get("promoter_holding_pct", 50.0),
        "pledged_shares_pct": round(random.uniform(0, 8), 2),
        "ccc": round(random.uniform(40, 120), 0),
    }
    await storage.patch_namespace(app_id, "financials", financials_payload)
    
    # PAN Intelligence (needed by CAM report KYC section)
    pan_category_map = {"P": "Individual", "C": "Company", "H": "HUF", "F": "Firm", "A": "AOP", "T": "Trust"}
    pan_val = company_data.get("pan", "")
    pan_cat_code = pan_val[3].upper() if len(pan_val) >= 4 else "C"
    await storage.patch_namespace(app_id, "pan_intelligence", {
        "status": "PASS",
        "full_name": company_data.get("company_name", "N/A"),
        "pan_number": pan_val,
        "pan_status": "VALID",
        "category": pan_category_map.get(pan_cat_code, "Company"),
        "aadhaar_linked": True,
        "masked_aadhaar": f"XXXX-XXXX-{random.randint(1000, 9999)}",
        "dob": company_data.get("incorporation_date", ""),
        "email": f"finance@{company_data.get('company_name', 'company').lower().replace(' ', '')}.in",
        "phone_number": f"+91-{random.randint(7000000000, 9999999999)}",
        "address": f"{company_data.get('registered_state', 'Maharashtra')}, India",
        "confidence": round(random.uniform(0.70, 0.85) if company_data.get("is_fraudulent") else random.uniform(0.96, 0.99), 4),
        "extraction_method": "NSDL_API_VERIFIED",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })
    
    # MCA Intelligence (needed by CAM report MCA section)
    directors = company_data.get("directors", [])
    director_changes = []
    director_din_list = []
    
    if directors and isinstance(directors[0], dict):
        director_din_list = [d.get("din", "") for d in directors if d.get("din")]
        for d in directors[:2]:
            director_changes.append({
                "din": d.get("din", ""),
                "name": d.get("name", "Director"),
                "change_type": "APPOINTMENT",
                "date": d.get("appointment_date", company_data.get("incorporation_date", "2020-01-01")),
            })
    else:
        # Directors is a list of strings (names)
        for name in (directors or [])[:2]:
            din = f"{random.randint(10000000, 99999999)}"
            director_din_list.append(din)
            director_changes.append({
                "din": din,
                "name": name if isinstance(name, str) else "Director",
                "change_type": "APPOINTMENT",
                "date": company_data.get("incorporation_date", "2020-01-01"),
            })
            
    if not director_din_list:
        director_din_list = [f"{random.randint(10000000, 99999999)}"]
        
    await storage.patch_namespace(app_id, "mca_intelligence", {
        "company_status": "ACTIVE",
        "director_changes_last_2yr": director_changes,
        "charges_registered": [],
        "new_charge_flag": False,
        "director_din_list": director_din_list,
        "last_agm_date": "2025-09-30",
        "defaulter_flag": company_data.get("is_fraudulent", False),
    })
    
    # Compliance (mark as PASS for demo applications)
    await storage.patch_namespace(app_id, "compliance", {
        "status": "PASS",
        "missing_documents": [],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })

    # 3. Publish event to Risk Agent via Outbox
    await storage.patch_namespace(app_id, "risk", {"model_used": "XGBOOST", "model_version": "v2.1_production"})
    
    await storage.add_outbox_event(
        "model_selected",
        {
            "application_id": app_id,
            "model": "XGBOOST"
        }
    )
    
    logger.info(f"🚀 Demo application {app_id} created and triggered risk scoring!")
    return {
        "application_id": app_id,
        "status": "TRIGGERED",
        "company_name": company_data["company_name"],
        "is_fraudulent": company_data["is_fraudulent"]
    }

@router.post("/api/application/{application_id}/reconcile")
async def reconcile_application_endpoint(
    application_id: str,
    current_user: dict = Depends(get_current_user_or_agent),
):
    """Manually trigger reconciliation for a stuck application."""
    from main import orchestrator
    
    app = await storage.get_application(application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    check_tenant_access(app, current_user)
    
    try:
        res = await orchestrator.reconcile_application(application_id)
        return res
    except Exception as e:
        logger.error(f"Failed to reconcile application {application_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")
