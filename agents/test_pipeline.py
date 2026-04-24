"""
Trinetra Test Pipeline
Injects Redis events and monitors agent progress.
"""
import json
import time
import os
import uuid
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

def get_client():
    return redis.from_url(REDIS_URL, decode_responses=True)

def get_subscriber(topics):
    client = get_client()
    pubsub = client.pubsub()
    pubsub.subscribe(*topics)
    return pubsub

def trigger_event(topic, app_id, data=None):
    client = get_client()
    payload = {"application_id": app_id}
    if data:
        payload.update(data)

    client.publish(topic, json.dumps(payload))
    print(f" [TEST] Triggered event '{topic}' for app {app_id}")

def monitor_pipeline(app_id, timeout=60):
    topics = ["agent_status", "cam_generated", "compliance_failed"]
    subscriber = get_subscriber(topics)

    start_time = time.time()
    _completed_agents = set()

    print(f" [TEST] Monitoring pipeline for app {app_id}...")

    try:
        while time.time() - start_time < timeout:
            msg = subscriber.get_message(timeout=1.0)
            if msg is None or msg.get("type") != "message":
                continue

            payload = json.loads(msg["data"])
            if payload.get("application_id") != app_id:
                continue

            topic = msg["channel"]

            if topic == "agent_status":
                agent = payload.get("agent")
                status = payload.get("status")
                print(f" [AGENT] {agent}: {status}")
                if status == "COMPLETED":
                    _completed_agents.add(agent)

            if topic == "cam_generated":
                print(f" [SUCCESS] CAM generated! Pipeline complete.")
                break

            if topic == "compliance_failed":
                print(f" [FAIL] Compliance check failed: {payload.get('missing_documents')}")
                break

    finally:
        subscriber.close()

if __name__ == "__main__":
    # Example usage
    test_app_id = str(uuid.uuid4())
    print(f"Starting test for application: {test_app_id}")
    
    # 1. Start monitoring in a separate process or just run sequentially if testing single agents
    # For a full test, trigger 'application_created'
    trigger_event("application_created", test_app_id)
    
    # In a real test, you'd feed actual files to the mock backend first
    
    monitor_pipeline(test_app_id)
