import logging
import asyncio
from datetime import datetime, timezone, timedelta
from core import storage, redis_broker
from storage.postgres_adapter import DBApplication, DBOutboxEvent, DBEventLog

logger = logging.getLogger("trinetra-backend.orchestrator")

class WorkflowOrchestrator:
    """
    Central state-machine and pipeline orchestrator.
    Relays transactional outbox events to the Redis message broker
    and reconciles stuck or failed agent pipeline transitions.
    """
    def __init__(self):
        self.running = True
        self.reconcile_interval = 30  # seconds

    async def start(self):
        """Start outbox relay and central workflow reconciliation background tasks."""
        logger.info("🚀 Starting Central Workflow Orchestrator background services...")
        asyncio.create_task(self.outbox_relay_loop())
        asyncio.create_task(self.state_reconciliation_loop())

    async def stop(self):
        self.running = False
        logger.info("Stopping Central Workflow Orchestrator background services...")

    async def outbox_relay_loop(self):
        """Relays pending outbox events to the Redis stream broker."""
        from sqlalchemy import select
        while self.running:
            try:
                async with storage.Session() as session:
                    stmt = select(DBOutboxEvent).filter_by(status="PENDING").order_by(DBOutboxEvent.created_at).limit(20)
                    res = await session.execute(stmt)
                    pending_events = res.scalars().all()
                    
                    events_to_send = []
                    for event in pending_events:
                        events_to_send.append((event.id, event.topic, event.payload))
                
                for event_id, topic, payload in events_to_send:
                    try:
                        logger.info(f"📤 Outbox relay: Publishing event {event_id} ({topic}) to Redis...")
                        await redis_broker.publish(topic, payload)
                        
                        async with storage.Session() as session:
                            try:
                                db_evt = await session.get(DBOutboxEvent, event_id)
                                if db_evt:
                                    db_evt.status = "SENT"
                                    db_evt.processed_at = datetime.now(timezone.utc)
                                    await session.commit()
                            except Exception as ex:
                                logger.error(f"Failed to update outbox event status to SENT: {ex}")
                                await session.rollback()
                                raise
                    except Exception as e:
                        logger.error(f"Failed to relay outbox event {event_id}: {e}")
                        async with storage.Session() as session:
                            try:
                                db_evt = await session.get(DBOutboxEvent, event_id)
                                if db_evt:
                                    db_evt.status = "FAILED"
                                    await session.commit()
                            except Exception as ex:
                                logger.error(f"Failed to update outbox event status to FAILED: {ex}")
                                await session.rollback()
                                raise
            except Exception as e:
                logger.error(f"Outbox relay loop error: {e}")
            await asyncio.sleep(2)

    async def state_reconciliation_loop(self):
        """Periodically scans for stuck agent pipeline states and auto-reconciles them."""
        while self.running:
            try:
                await self.reconcile_all_stuck_applications()
            except Exception as e:
                logger.error(f"State reconciliation loop error: {e}")
            await asyncio.sleep(self.reconcile_interval)

    async def reconcile_all_stuck_applications(self):
        """Find applications that are stuck and trigger a retry/re-publish if needed."""
        from sqlalchemy import select
        async with storage.Session() as session:
            try:
                stmt = select(DBApplication).filter(~DBApplication.status.in_(["APPROVED", "REJECTED"]))
                res = await session.execute(stmt)
                active_apps = res.scalars().all()
                now = datetime.now(timezone.utc)
                stuck_ids = []
                for app in active_apps:
                    if app.updated_at and (now - app.updated_at.replace(tzinfo=timezone.utc) > timedelta(minutes=3)):
                        stuck_ids.append(app.id)
            except Exception as ex:
                logger.error(f"Error querying active applications: {ex}")
                stuck_ids = []
        
        for app_id in stuck_ids:
            await self.reconcile_application(app_id)

    async def reconcile_application(self, application_id: str) -> dict:
        """
        Check state transitions of an application and republish events for missing stages.
        """
        app = await storage.get_application(application_id)
        if not app:
            return {"status": "NOT_FOUND"}
            
        ucso = app.get("ucso_data", {})
        
        # Analyze what is missing based on UCSO data
        files = ucso.get("documents", {}).get("files", [])
        if files:
            uploaded_types = {f.get("type") for f in files}
            is_combined = "COMBINED" in uploaded_types
            has_all_four = all(t in uploaded_types for t in ["ANNUAL_REPORT", "BANK_STMT", "GST_RETURN", "ITR"])
            
            if is_combined or has_all_four:
                # Check if compliance is run
                compliance = ucso.get("compliance", {})
                if not compliance.get("status"):
                    logger.warning(f"Reconciliation: Application {application_id} is stuck before compliance. Re-triggering compliance.")
                    await redis_broker.publish("application_created", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "compliance_stuck"}
                
                # Check if parsing is done
                doc_file_status = [f.get("parsed") for f in files]
                if not all(doc_file_status):
                    logger.warning(f"Reconciliation: Application {application_id} parsing is stuck. Re-triggering parsing.")
                    await redis_broker.publish("docs_uploaded", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "parsing_stuck"}
                    
                # If parsing finished, check if GST, bank reconciliation, and MCA are done
                gst = ucso.get("gst_analysis", {})
                bank = ucso.get("bank_reconciliation", {})
                mca = ucso.get("mca_intelligence", {})
                
                if not gst.get("reconciliation_status") or not bank.get("reconciliation_verdict") or not mca.get("company_status"):
                    logger.warning(f"Reconciliation: Application {application_id} validation is stuck. Re-triggering GST/bank/MCA validation.")
                    await redis_broker.publish("parsing_completed", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "validation_stuck"}
                    
                # If GST/bank recon are done, check if web search is done
                web = ucso.get("web_intel", {})
                if not web or web.get("kb_query_timestamp") is None:
                    logger.warning(f"Reconciliation: Application {application_id} web intel stuck. Re-triggering web agent.")
                    await redis_broker.publish("gst_completed", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "web_intel_stuck"}
                    
                # If web and mca are done, check if model selector run
                risk = ucso.get("risk", {})
                if not risk.get("model_used"):
                    logger.warning(f"Reconciliation: Application {application_id} model selection stuck. Re-triggering model selection.")
                    await redis_broker.publish("web_intel_completed", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "model_selection_stuck"}
                    
                # If model is selected, check if risk score is run
                if risk.get("decision") is None or risk.get("score") is None:
                    logger.warning(f"Reconciliation: Application {application_id} risk assessment stuck. Re-triggering risk agent.")
                    await redis_broker.publish("model_selected", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "risk_assessment_stuck"}
                    
                # If risk generated, check if bias / stress run
                stress = ucso.get("stress_results", {})
                bias = ucso.get("bias_checks", {})
                if not stress.get("survival_verdict") or not bias.get("counterfactual_tested"):
                    logger.warning(f"Reconciliation: Application {application_id} stress/bias checks stuck. Re-triggering stress/bias checks.")
                    await redis_broker.publish("risk_generated", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "stress_bias_stuck"}
                    
                # If stress completed, check if CAM generated
                cam = ucso.get("cam_output", {})
                if not cam.get("s3_key"):
                    logger.warning(f"Reconciliation: Application {application_id} CAM generation stuck. Re-triggering CAM agent.")
                    await redis_broker.publish("stress_completed", {"application_id": application_id})
                    return {"status": "RE_TRIGGERED", "reason": "cam_generation_stuck"}
                    
        return {"status": "OK", "reason": "healthy"}
