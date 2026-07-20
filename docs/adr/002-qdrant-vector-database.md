# ADR 002: Vector Database Selection (Qdrant)

**Date:** 2026-06-21
**Status:** Accepted

## Context
The platform implements a Retrieval-Augmented Generation (RAG) pipeline for the Web Agent and Doc Agent. We needed a vector database to store document chunks and web scrape embeddings.

## Decision
We selected **Qdrant** as the primary vector database.

## Consequences
**Pros:**
- Written in Rust, offering extremely high performance and low resource consumption.
- Excellent support for payload filtering, allowing us to filter vectors by `application_id` before performing nearest-neighbor searches.
- Provides a comprehensive Python client (`qdrant-client`).

**Cons:**
- Newer ecosystem compared to Pinecone or Milvus.
