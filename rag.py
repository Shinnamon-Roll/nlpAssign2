"""RAG backend for the D Bigbike chatbot: load -> clean -> chunk -> embed -> FAISS -> Gemini.

No streamlit import here, so it runs from the CLI; app.py caches build_index() with @st.cache_resource.
`python rag.py` checks retrieval against test_questions.csv without calling the LLM.
"""
import csv
import re
import sys
from pathlib import Path

import faiss
import numpy as np
from google import genai
from google.genai import errors, types
from pythainlp.tokenize import sent_tokenize
from pythainlp.util import normalize
from sentence_transformers import SentenceTransformer

NOT_FOUND = "ไม่พบข้อมูลในเอกสาร"
GEMINI_MODEL = "gemini-3.8-flash"  # free tier; 2.5 models are closed to new keys
FALLBACK_MODEL = "gemini-3.5-flash-lite"  # used once when GEMINI_MODEL answers 503 (busy) or 429 (quota)
EMBED_MODEL = "intfloat/multilingual-e5-small"
SCORE_THRESHOLD = 0.80  # e5 cosine scores sit in ~0.75-0.9; tuned with `python rag.py`, the prompt does the finer refusing
TOP_K = 5
MAX_CHARS = 800  # per chunk body; ~800 Thai chars stays under e5's 512-token limit
OVERLAP = 100
TABLE_ROWS = 6  # inventory rows per chunk, header repeated; 8 rows hit ~600 tokens and got truncated
HISTORY_TURNS = 3
INVENTORY = "inventory_summary.md"

IMAGE_KEY = "รูปภาพ"
URL_KEYS = ("ลิงก์ประกาศ", "ลิงก์บทความ")
ZERO_WIDTH = re.compile("[​-‍⁠﻿]")
RULE = re.compile(r"^[-=_*~]{3,}$")  # "-----" separator lines
TABLE_SEP = re.compile(r"^\|[\s:|-]+\|$")

SYSTEM_PROMPT = f"""คุณคือผู้ช่วยขายของร้านดีเจริญยนต์ (D Bigbike) ร้านรถบิ๊กไบค์มือสอง
กติกา:
1. ตอบจากข้อมูลใน "เอกสารอ้างอิง" ที่ให้มาในข้อความล่าสุดเท่านั้น ห้ามใช้ความรู้ภายนอก
   แต่เปรียบเทียบ เรียงลำดับ นับ หรือกรองข้อมูลในเอกสารได้ เช่น หาคันที่ถูกที่สุด/ไมล์น้อยที่สุด หรือรถงบไม่เกิน 300,000 บาท
   จากตารางใน [{INVENTORY}] (ตารางนี้คือรายการรถพร้อมขายทั้งหมด)
2. อ้างอิงแหล่งที่มาด้วยชื่อไฟล์ในวงเล็บเหลี่ยม สะกดตรงตามที่ให้มา เช่น [bike_38_yamaha_mt09_2022.md]
   อ้างแต่ละไฟล์ครั้งเดียว ท้ายประโยคหรือท้ายกลุ่ม bullet ที่ไฟล์นั้นรองรับ ไม่ต้องใส่ซ้ำทุก bullet
   ถ้าไฟล์ bike_*.md กับ {INVENTORY} ให้ข้อมูลเดียวกัน ให้อ้างเฉพาะไฟล์ bike_*.md
3. ห้ามเดาหรือแต่งราคา สเปค เลขไมล์ เงื่อนไขไฟแนนซ์ อัตราดอกเบี้ย ระยะเวลารับประกัน หรือนโยบายร้านที่ไม่มีในเอกสาร
   เลขไมล์ที่ปิดบางหลัก (เช่น 2x,xxx) ให้แสดงตามเอกสาร ห้ามเติมตัวเลขเอง
4. ถ้าเอกสารไม่มีคำตอบ ให้ตอบขึ้นต้นด้วย "{NOT_FOUND}" ทันที ไม่ต้องอธิบายอย่างอื่น
   ถ้ามีคำตอบเพียงบางส่วน ให้ตอบส่วนที่มี แล้วบอกว่าส่วนที่เหลือ{NOT_FOUND}
5. คำถามต่อเนื่อง (เช่น "คันนี้", "รุ่นนี้") ให้ดูจากประวัติแชตว่าหมายถึงรถคันไหน แต่ข้อเท็จจริงต้องมาจากเอกสารอ้างอิงเท่านั้น
6. ตอบภาษาเดียวกับคำถาม (ถามไทยตอบไทย, ask in English -> answer in English;
   for a missing answer in English, still start with "{NOT_FOUND}" then add "(No information found in the documents.)")
7. ตอบกระชับ สุภาพ แบบพนักงานขาย ใช้ bullet เมื่อเทียบหลายคัน"""


# ---------- load + clean ----------
def _clean(line):
    line = normalize(ZERO_WIDTH.sub("", line))  # per line: normalize() also merges newlines
    return re.sub(r"\s+", " ", line).strip()


def _kv(line):
    """'- **ราคาขาย (บาท):** 289,000' -> ('ราคาขาย (บาท)', '289,000'); None if not a key: value line."""
    key, sep, value = line.replace("**", "").lstrip("-* ").partition(":")
    key = key.strip()
    if not sep or not key or len(key) > 40 or key.startswith("http"):
        return None
    return key, value.strip()


def _load(path):
    """One .md file -> doc dict. Image/link lines become metadata and are dropped from the text."""
    doc = {"source": path.name, "title": path.stem, "images": [], "url": None, "meta": {},
           "sections": [["ภาพรวม", []]], "lines": []}
    has_title = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = _clean(raw)
        if not line or RULE.match(line):
            continue
        kv = _kv(line)
        if kv and kv[0] == IMAGE_KEY:
            doc["images"] = [u for u in re.split(r"[,\s]+", kv[1]) if u.startswith("http")]
            continue
        if kv and kv[0] in URL_KEYS:
            doc["url"] = kv[1] or None
            continue
        doc["lines"].append(line)
        if line.startswith("# ") and not has_title:
            doc["title"], has_title = line[2:].strip(), True
        elif re.match(r"^#{2,}\s", line):
            doc["sections"].append([line.lstrip("#").strip(), []])
        else:
            doc["sections"][-1][1].append(line)
            if kv and len(doc["sections"]) == 1 and path.name.startswith("bike_"):
                doc["meta"][kv[0]] = kv[1]
    return doc


# ---------- chunk ----------
def _pack(units, sep, limit=MAX_CHARS, overlap=OVERLAP):
    """Greedily join units up to `limit` chars; each new chunk repeats trailing units up to `overlap` chars."""
    chunks, cur = [], []
    for u in units:
        if cur and len(sep.join(cur + [u])) > limit:
            chunks.append(sep.join(cur))
            tail = []
            for prev in reversed(cur):
                if len(sep.join([prev] + tail)) > overlap:
                    break
                tail.insert(0, prev)
            cur = tail if len(sep.join(tail + [u])) <= limit else []
        cur.append(u)
    if cur:
        chunks.append(sep.join(cur))
    return chunks


def _units(line):
    """A line, or sentence-packed pieces of an over-long line (crfcut keeps trailing spaces, so join with '')."""
    if len(line) <= MAX_CHARS:
        return [line]
    sents = [s[i:i + MAX_CHARS] for s in sent_tokenize(line) for i in range(0, len(s), MAX_CHARS)]
    return _pack(sents, "")


def _chunk_doc(doc):
    blocks = []  # (heading, text) pieces, each <= MAX_CHARS
    for heading, lines in doc["sections"]:
        table = [l for l in lines if l.startswith("|")]
        prose = [l for l in lines if not l.startswith("|")]
        head = f"## {heading}\n" if heading != "ภาพรวม" else ""
        units = [u for l in prose for u in _units(l)]
        blocks += [(heading, head + part) for part in _pack(units, "\n", MAX_CHARS - len(head))]
        if table:  # table: N rows per chunk, header repeated, never merged with prose
            header = table[:2] if len(table) > 1 and TABLE_SEP.match(table[1]) else table[:1]
            rows = table[len(header):]
            for i in range(0, len(rows), TABLE_ROWS):
                part = rows[i:i + TABLE_ROWS]
                blocks.append((f"ตาราง แถว {i + 1}-{i + len(part)}", "\n".join(header + part)))
    merged = []  # glue adjacent small prose blocks, so a short bike file is 1-2 chunks
    for heading, text in blocks:
        prev = merged[-1] if merged else None
        if prev and not text.startswith("|") and not prev[1].startswith("|") \
                and len(prev[1]) + 1 + len(text) <= MAX_CHARS:
            merged[-1] = (f"{prev[0]} / {heading}", f"{prev[1]}\n{text}")
        else:
            merged.append((heading, text))
    return [{"source": doc["source"], "title": doc["title"], "heading": heading,
             "text": f"# {doc['title']}\n{text}",  # contextual header: every chunk names its bike/doc
             "images": doc["images"], "url": doc["url"], "meta": doc["meta"]}
            for heading, text in merged]


# ---------- index + retrieve ----------
def build_index(data_dir="data"):
    docs = [_load(p) for p in sorted(Path(data_dir).glob("*.md"))]
    chunks = [c for d in docs for c in _chunk_doc(d)]
    model = SentenceTransformer(EMBED_MODEL)
    emb = model.encode([f"passage: {c['text']}" for c in chunks], normalize_embeddings=True, batch_size=32)
    index = faiss.IndexFlatIP(emb.shape[1])  # inner product on unit vectors = cosine
    index.add(np.asarray(emb, dtype="float32"))
    full_text = {d["source"]: "\n".join(d["lines"]) for d in docs}  # inventory goes to the LLM whole
    return {"model": model, "index": index, "chunks": chunks, "full_text": full_text}


def retrieve(store, query, k=TOP_K):
    q = store["model"].encode([f"query: {query}"], normalize_embeddings=True)
    scores, ids = store["index"].search(np.asarray(q, dtype="float32"), k)
    return [dict(store["chunks"][i], score=float(s)) for s, i in zip(scores[0], ids[0]) if i != -1]


def search(store, question, history=(), k=TOP_K):
    """Retrieve for the question alone and, for follow-ups, for previous user question + question.
    Merge by best score per chunk so "คันนี้ผ่อนเท่าไร" still finds the bike from the previous turn."""
    prev = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    hits = retrieve(store, question, k)
    if prev:
        best = {}
        for h in retrieve(store, f"{prev} {question}", k) + hits:
            key = (h["source"], h["text"])
            if key not in best or h["score"] > best[key]["score"]:
                best[key] = h
        hits = sorted(best.values(), key=lambda h: -h["score"])[:k]
    return hits


# ---------- prompt + LLM ----------
def _context(store, sources):
    parts, seen = [], set()
    for c in sources:
        if c["source"] == INVENTORY:  # whole table so "cheapest / how many / under 300k" work
            if INVENTORY in seen:
                continue
            seen.add(INVENTORY)
            text = store["full_text"][INVENTORY]
        else:
            text = c["text"]
        parts.append(f"[{c['source']}]\n{text}")
    return "\n\n---\n\n".join(parts)


def answer(store, question, history, api_key):
    """-> (answer text, retrieved chunks). Sources are returned even for NOT_FOUND.
    Gemini errors (google.genai.errors.APIError, e.code == 429 for quota) propagate to the caller."""
    sources = search(store, question, history)
    if not sources or sources[0]["score"] < SCORE_THRESHOLD:
        return NOT_FOUND, sources
    turns = [m for m in history if m.get("content")][-2 * HISTORY_TURNS:]
    while turns and turns[0]["role"] != "user":  # Gemini history should open with a user turn
        turns = turns[1:]
    contents = [types.Content(role="model" if m["role"] == "assistant" else "user",
                              parts=[types.Part.from_text(text=m["content"])]) for m in turns]
    prompt = (f"เอกสารอ้างอิง:\n\n{_context(store, sources)}\n\n=====\n"
              f"คำถาม (ตอบเป็นภาษาเดียวกับคำถามนี้ / reply in the language of this question): {question}")
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
    # temperature left at default 1.0: Gemini 3 docs warn low values can cause looping
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        thinking_config=types.ThinkingConfig(thinking_level="low"),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # no tools; silences SDK warning
    )
    client = genai.Client(api_key=api_key)
    for model in (GEMINI_MODEL, FALLBACK_MODEL):
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config)
            break
        except errors.APIError as e:
            if model == FALLBACK_MODEL or e.code not in (429, 503):
                raise
    return (resp.text or NOT_FOUND).strip(), sources


# ---------- retrieval check (no LLM call unless --live) ----------
if __name__ == "__main__":
    root = Path(__file__).parent
    store = build_index(root / "data")
    lens = [len(c["text"]) for c in store["chunks"]]
    print(f"{len(store['chunks'])} chunks from {len(store['full_text'])} files, "
          f"chars min/avg/max {min(lens)}/{sum(lens) // len(lens)}/{max(lens)}")
    tok = store["model"].tokenizer
    over = sum(len(tok(f"passage: {c['text']}")["input_ids"]) > store["model"].max_seq_length for c in store["chunks"])
    print(f"chunks over {store['model'].max_seq_length} tokens (truncated): {over}")

    csv_path = root / "test_questions.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig"))) if csv_path.exists() else []
    if not rows:
        print("test_questions.csv not found, using sample queries")
        rows = [{"question": q, "answerable": a, "source": s} for q, a, s in [
            ("Yamaha MT09 ราคาเท่าไร", "yes", "bike_35_yamaha_mt09_2022.md"),
            ("ร้านเปิดกี่โมง", "yes", "shop_contact.md"),
            ("รถคันไหนถูกที่สุด", "yes", INVENTORY),
            ("ดอกเบี้ยผ่อนกี่เปอร์เซ็นต์", "no", ""),
            ("ร้านมีบริการล้างรถฟรีไหม", "no", ""),
            ("What is the weather in Tokyo today?", "no", ""),
        ]]
    hits, n_ans, unans = 0, 0, []
    for r in rows:
        # "(ถามต่อจากคำถามเรื่อง X) Q" rows run through the real follow-up path with X as the previous turn
        m = re.match(r"^\(ถามต่อจากคำถามเรื่อง (.+?)\)\s*(.+)$", r["question"])
        q, hist = (m[2], [{"role": "user", "content": m[1]}]) if m else (r["question"], [])
        res = search(store, q, hist)
        top = res[0]["score"] if res else 0.0
        answerable = str(r.get("answerable", "")).strip().lower() not in {"no", "false", "0", "n", "ไม่"}
        expected = {s for s in re.split(r"[;|,\s]+", r.get("source", "") or "") if s.endswith(".md")}
        got = [h["source"] for h in res]
        if answerable:
            n_ans += 1
            ok = bool(expected & set(got))
            hits += ok
            mark = "HIT " if ok else "MISS"
        else:
            unans.append(top)
            mark = "PASS" if top < SCORE_THRESHOLD else "LLM "  # LLM = above threshold, prompt must refuse
        print(f"\n[{mark}] {r['question']}  (expected: {', '.join(sorted(expected)) or '-'})")
        for h in res[:3]:
            print(f"    {h['score']:.3f}  {h['source']}  | {h['heading']}")
    if n_ans:
        print(f"\nhit@{TOP_K} (answerable): {hits}/{n_ans} = {hits / n_ans:.0%}")
    if unans:
        print(f"unanswerable top scores: {', '.join(f'{s:.3f}' for s in unans)} (threshold {SCORE_THRESHOLD})")

    if "--live" in sys.argv:  # Gemini smoke test; key read from secrets.toml, never printed
        import tomllib
        key = tomllib.loads((root / ".streamlit" / "secrets.toml").read_text())["GEMINI_API_KEY"]
        history = []
        for q in ["Yamaha MT09 ราคาเท่าไร", "คันนี้ผ่อนเดือนละเท่าไร", "ดอกเบี้ยผ่อนกี่เปอร์เซ็นต์",
                  "Which bike is the cheapest?"]:
            text, src = answer(store, q, history, key)
            print(f"\n>>> {q}\n{text}\n    sources: {[(h['source'], round(h['score'], 3)) for h in src]}")
            history += [{"role": "user", "content": q}, {"role": "assistant", "content": text}]
