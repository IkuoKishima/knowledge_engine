# knowledge_engine

## Overview
This project builds a cost-safe RAG-style knowledge pipeline.

- Human-curated knowledge (Fruit Basket style)
- Manifest DB for canonical documents
- Vector DB separated from source of truth
- Strict diff detection to prevent duplicate embedding
- Embedding API is used only after pipeline validation

## Pipeline
input/json
  -> index_build.py (manifest.sqlite)
  -> vectors_sync.py (vectors.sqlite, pending)
  -> embed_pending.py (embedded)

## Why this design
- Avoid unexpected API costs
- Make embedding a replaceable, disposable process
- Verify behavior step-by-step before using paid services

## Current status
- Dummy embedding used for pipeline validation
- Real embedding can be plugged in later