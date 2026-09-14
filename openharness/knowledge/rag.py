from pathlib import Path

_C, _N = None, None
_CH, _ST = 1000, 900


def _get():
    global _C, _N
    if _C is None:
        import chromadb
        _C = chromadb.PersistentClient(path=str(Path.cwd()/".openharness"/"chroma"))
        _N = _C.get_or_create_collection("knowledge")
    return _C, _N


def _chunks(t: str) -> list[str]:
    if len(t) <= _CH: return [t]
    out, s, L = [], 0, len(t)
    while s < L:
        out.append(t[s:s+_CH])
        s += _ST
    if out and len(out[-1]) < _CH and L > _CH: out[-1] = t[max(0, L-_CH):]
    return out


def ingest(path=None, text=None, metadata=None):
    _, col = _get()
    src = path or (metadata or {}).get("source") or "inline"
    if text is None and path: text = Path(path).read_text()
    if text is None: return
    cs = _chunks(text)
    ids = [f"{src}:{i}" for i in range(len(cs))]
    ms = [dict(metadata or {}, source=src, chunk=i) for i in range(len(cs))]
    col.upsert(documents=cs, ids=ids, metadatas=ms)


def search(query: str, k: int = 5) -> list[str]:
    _, col = _get()
    return (col.query(query_texts=[query], n_results=k).get("documents") or [[]])[0] or []


def as_context(query: str, k: int = 5) -> str:
    d = search(query, k=k)
    return "" if not d else "## Relevant Knowledge\n" + "---\n".join(d)
