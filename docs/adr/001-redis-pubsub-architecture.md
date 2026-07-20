# ADR 001: Event-Driven Architecture via Redis Pub/Sub

**Date:** 2026-06-21
**Status:** Accepted

## Context
The Trinetra platform requires a high-throughput, low-latency messaging backbone to orchestrate 13+ specialized AI agents. Initially, Kafka was considered for event streaming.

## Decision
We elected to use **Redis Pub/Sub** combined with Redis Streams (for the background task queue in the backend). 

## Consequences
**Pros:**
- Significantly lower memory overhead compared to Kafka, which is crucial since we deploy 13+ containers.
- Extremely low latency for real-time WebSocket agent feeds.
- Simplified local development setup (single lightweight `redis:alpine` container).

**Cons:**
- Pub/Sub messages are not persisted. If the WebSocket server restarts, in-flight live feed messages are lost. (Mitigation: we refresh the full application state upon reconnecting).
