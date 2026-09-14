---
name: rag
type: block
location: openharness/knowledge/rag.py, .openharness/chroma/
interfaces: [rag.ingest, rag.search, rag.as_context]
---
# Block: rag

## Purpose
Local-first RAG (Retrieval-Augmented Generation) for project knowledge. Stores chunks in ChromaDB (PersistentClient) at `.openharness/chroma` with the all-MiniLM-L6-v2 sentence-transformer embedding model. Single collection `"knowledge"`.

## Invariants
- **Local only.** No network calls during embedding or search. (D002 local-first.)
- Chunking: `1000` chars per chunk, `900` char stride (overlap ~90%). Last chunk is padded from the end to avoid truncation.
- IDs: `<source>:<i>` where `<source>` is the file path or provided source string.
- `ingest` uses `upsert` — re-ingesting the same source updates existing chunks.
- `search(query, k=5) -> list[str]` returns documents only (no scores, no metas).
- `as_context(query, k=5) -> str` returns empty string when no hits; otherwise `"## Relevant Knowledge\n"` + `"---\n"`-joined chunks. This is designed to be prepended directly into prompts.
- Embedding function is `sentence-transformers/all-MiniLM-L6-v2` (small, fast, English).

## How to Extend
- To ingest: call `rag.ingest(path=..., text=..., metadata={...})` from any skill or command that produces a `.md` artifact. `/map-architecture` and `/strangler-plan` do this.
- To search: use `python -m openharness ask "query"` (CLI) or `GET /api/knowledge?q=` (API).
- To replace the embedding model: change the import/assignment in `rag.py` and drop the existing `.openharness/chroma/` directory so Chroma re-ingests with the new dims.
