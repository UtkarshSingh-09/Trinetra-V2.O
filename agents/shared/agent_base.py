"""
Trinetra Agent Base Class
Base class for all 13 agents. Handles Redis Pub/Sub consumption, status publishing,
and the standard agent lifecycle.

Migration: Kafka → Redis Pub/Sub (March 2026)
- confluent_kafka.Consumer → redis.pubsub.subscribe()
- confluent_kafka.Producer → redis.publish()
- process() interface is 100% unchanged — all 13 agent main.py files work as-is.
"""
import os
import json
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env from agents/ directory (auto-loads API keys for all agents)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from .vault import load_vault_secrets

load_vault_secrets()

import redis
from .logger import get_logger, trace_id_var
from .ucso_client import UcsoClient


class AgentBase:
    """
    Base class providing Redis Pub/Sub boilerplate for every Trinetra agent.

    Subclasses must implement:
        - process(self, application_id: str, ucso: dict) -> dict
          Returns the namespace data to PATCH.

    Class attributes that subclasses must set:
        - AGENT_NAME: str          e.g., "compliance-agent"
        - LISTEN_TOPICS: list[str] e.g., ["application_created"]
        - OUTPUT_NAMESPACE: str    e.g., "compliance"
        - OUTPUT_EVENT: str        e.g., "compliance_passed"
    """

    AGENT_NAME = "base-agent"
    LISTEN_TOPICS = []
    OUTPUT_NAMESPACE = ""
    OUTPUT_EVENT = ""

    def __init__(self):
        self.logger = get_logger(self.AGENT_NAME)
        self.ucso_client = UcsoClient()
        self.running = True

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = None

        # Graceful shutdown
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        self.logger.info(f"{self.AGENT_NAME} received shutdown signal.")
        self.running = False

    def publish_event(self, topic: str, application_id: str, extra: dict = None):
        """Publish an event to a Redis Stream after successful processing."""
        trace_id = trace_id_var.get()
        message = {
            "application_id": application_id,
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": topic,
            "source_agent": self.AGENT_NAME,
            "trace_id": trace_id or None,
            **(extra or {}),
        }
        self.redis_client.xadd(name=f"stream:{topic}", fields={"payload": json.dumps(message)})
        self.logger.info(
            f"Published event to stream 'stream:{topic}'",
            extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
        )

    def publish_status(self, application_id: str, status: str, error_code: str = None):
        """Publish agent status to the agent_status channel for WebSocket broadcast (Pub/Sub)."""
        # Prevent infinite loop: monitor-agent listens to agent_status, so it shouldn't publish its own status
        if self.AGENT_NAME == "monitor-agent":
            return

        trace_id = trace_id_var.get()
        message = {
            "application_id": application_id,
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "agent_status",
            "agent": self.AGENT_NAME,
            "status": status,
            "error_code": error_code,
            "trace_id": trace_id or None,
        }
        self.redis_client.publish("agent_status", json.dumps(message))

    def process(self, application_id: str, ucso: dict) -> dict:
        """
        Core processing logic. Must be overridden by each agent.

        Args:
            application_id: UUID of the loan application.
            ucso: The full UCSO dictionary.

        Returns:
            A dictionary containing the data to PATCH into OUTPUT_NAMESPACE.
        """
        raise NotImplementedError("Subclasses must implement process()")

    def run(self):
        """Main event loop consuming from Redis Streams with Consumer Groups (PEL crash-recovery)."""
        import socket
        max_retries = 999  # Effectively infinite
        retry_count = 0

        group_name = self.AGENT_NAME
        consumer_name = f"{self.AGENT_NAME}_{socket.gethostname()}"

        while self.running and retry_count < max_retries:
            try:
                # 1. Initialize streams and consumer groups for each topic
                for topic in self.LISTEN_TOPICS:
                    stream_name = f"stream:{topic}"
                    try:
                        self.redis_client.xgroup_create(
                            name=stream_name, 
                            groupname=group_name, 
                            id="0", 
                            mkstream=True
                        )
                        self.logger.info(f"Consumer group '{group_name}' created/verified for stream '{stream_name}'")
                    except redis.exceptions.ResponseError as err:
                        if "BUSYGROUP" not in str(err):
                            self.logger.warning(f"Failed to create consumer group for {stream_name}: {err}")

                self.logger.info(
                    f"{self.AGENT_NAME} started on host {socket.gethostname()}. Listening on streams: {[f'stream:{t}' for t in self.LISTEN_TOPICS]}"
                )
                retry_count = 0  # Reset on successful connection

                while self.running:
                    # 2. Check Pending Entries List (PEL) first for crash recovery (ID '0')
                    # We query each stream for unacknowledged messages delivered to this consumer
                    msg_found = False
                    for topic in self.LISTEN_TOPICS:
                        stream_name = f"stream:{topic}"
                        try:
                            # Read any pending message (ID='0')
                            pending_res = self.redis_client.xreadgroup(
                                groupname=group_name,
                                consumername=consumer_name,
                                streams={stream_name: "0"},
                                count=1
                            )
                            if pending_res:
                                # Verify there are messages returned (sometimes empty lists are returned)
                                if pending_res[0][1]:
                                    msg_found = True
                                    self._process_stream_response(pending_res, group_name, consumer_name)
                                    break  # Process one message per loop iteration
                        except Exception as e:
                            self.logger.error(f"Error checking pending messages for {stream_name}: {e}")

                    if msg_found:
                        continue  # Keep checking PEL until empty

                    # 3. Read new messages from Stream (ID='>')
                    try:
                        streams = {f"stream:{topic}": ">" for topic in self.LISTEN_TOPICS}
                        res = self.redis_client.xreadgroup(
                            groupname=group_name,
                            consumername=consumer_name,
                            streams=streams,
                            count=1,
                            block=1000  # block for 1s
                        )
                        if res:
                            self._process_stream_response(res, group_name, consumer_name)
                    except Exception as e:
                        # Redis stream read failure
                        raise e

            except Exception as e:
                retry_count += 1
                self.logger.error(
                    f"Redis connection/stream error ({type(e).__name__}: {e}). "
                    f"Reconnecting in 5s... (attempt {retry_count})"
                )
                time.sleep(5)

                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                self.redis_client = redis.from_url(redis_url, decode_responses=True)

        self.redis_client.close()
        self.logger.info(f"{self.AGENT_NAME} shut down gracefully.")

    def _process_stream_response(self, response, group_name: str, consumer_name: str):
        for stream_name, messages in response:
            for msg_id, data in messages:
                payload_str = data.get("payload")
                if not payload_str:
                    # Acknowledge empty payloads to purge them
                    self.redis_client.xack(stream_name, group_name, msg_id)
                    continue

                payload = {}
                try:
                    payload = json.loads(payload_str)
                    application_id = payload.get("application_id")
                    if not application_id:
                        self.logger.warning(f"Received message without application_id on stream {stream_name}, skipping.")
                        self.redis_client.xack(stream_name, group_name, msg_id)
                        continue

                    trace_id = payload.get("trace_id", "")
                    token = trace_id_var.set(trace_id)
                    try:
                        self.logger.info(
                            f"Processing application {application_id} (msg: {msg_id}) from stream {stream_name}",
                            extra={"agent_name": self.AGENT_NAME, "application_id": application_id},
                        )
                        self.publish_status(application_id, "PROCESSING")

                        # Simulate delay
                        delay = float(os.getenv("AGENT_PROCESSING_DELAY", "0"))
                        if delay > 0:
                            self.logger.info(f"Simulating pipeline delay of {delay}s...")
                            time.sleep(delay)

                        # Fetch current UCSO state
                        ucso = self.ucso_client.get_ucso(application_id)

                        # Run agent process logic
                        result = self.process(application_id, ucso)
                        
                        if result is False:
                            self.logger.info(f"Skipping completion/publishing for {application_id} (prerequisites not met).")
                            self.redis_client.xack(stream_name, group_name, msg_id)
                            continue

                        # PATCH the result into the correct namespace
                        if result and self.OUTPUT_NAMESPACE:
                            if isinstance(result, list):
                                result = {"data": result}
                            self.ucso_client.patch_namespace(
                                application_id, self.OUTPUT_NAMESPACE, result
                            )

                        # Publish success event
                        if self.OUTPUT_EVENT:
                            self.publish_event(self.OUTPUT_EVENT, application_id)

                        self.publish_status(application_id, "COMPLETED")
                        
                        # Acknowledge message on successful execution
                        self.redis_client.xack(stream_name, group_name, msg_id)
                    finally:
                        trace_id_var.reset(token)

                except Exception as e:
                    self.logger.error(
                        f"Error processing message: {e}",
                        exc_info=True,
                        extra={"agent_name": self.AGENT_NAME, "application_id": payload.get("application_id", "unknown")},
                    )
                    self.publish_status(
                        payload.get("application_id", "unknown"),
                        "FAILED",
                        error_code=type(e).__name__,
                    )
                    # Acknowledge to prevent getting permanently stuck on code/validation crashes
                    self.redis_client.xack(stream_name, group_name, msg_id)

