import json
import os
import random
import time
from urllib import request

from config import ACTIAN_CLOUD_API_URL, ACTIAN_API_KEY, ACTIAN_LOCAL_DIR


class EdgeCloudSyncWorker:
    """
    Lightweight sync worker for Actian edge mode.

    Reads append-only local event log and pushes unsynced records to cloud endpoint.
    """

    def __init__(self):
        self.event_log_path = os.path.join(ACTIAN_LOCAL_DIR, "event_log.jsonl")

    def _post_event(self, event: dict) -> bool:
        if not ACTIAN_CLOUD_API_URL:
            return False

        payload = json.dumps(event).encode("utf-8")
        req = request.Request(
            f"{ACTIAN_CLOUD_API_URL.rstrip('/')}/sync/events",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ACTIAN_API_KEY}",
            },
        )

        try:
            with request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False

    def run_once(self, max_retries: int = 3) -> dict:
        if not os.path.exists(self.event_log_path):
            return {"synced": 0, "pending": 0}

        with open(self.event_log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        events = [json.loads(line) for line in lines]
        synced = 0

        for event in events:
            if event.get("synced"):
                continue

            attempt = 0
            pushed = False
            while attempt < max_retries and not pushed:
                pushed = self._post_event(event)
                if not pushed:
                    sleep_s = (2 ** attempt) + random.uniform(0.0, 0.5)
                    time.sleep(sleep_s)
                    attempt += 1

            if pushed:
                event["synced"] = True
                synced += 1

        with open(self.event_log_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

        pending = len([e for e in events if not e.get("synced")])
        return {"synced": synced, "pending": pending}
