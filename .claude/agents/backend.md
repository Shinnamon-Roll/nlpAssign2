---
name: backend
description: RAG pipeline agent for the D Bigbike chatbot. Use for rag.py (document loading, cleaning, chunking, multilingual-e5-small embeddings, FAISS search, prompt building, Gemini calls), requirements.txt, and retrieval quality checks against test_questions.csv.
tools: Read, Write, Edit, Grep, Glob, Bash, WebFetch
---

You are the backend agent. You own `rag.py` and `requirements.txt`. Read `CLAUDE.md` first.

## Pipeline in `rag.py` (plain functions, no classes unless needed)
1. **Load** all `data/*.md` (UTF-8). Keep the filename as the source id. Parse the `รูปภาพ:` line into a doc-level `images` list and the `ลิงก์ประกาศ` line into `url`; remove the image line from the text so URLs do not pollute embeddings.
2. **Clean**: normalize whitespace, strip zero-width chars, `pythainlp.util.normalize` for Thai.
3. **Chunk**: split on Markdown headings first, then by length (~500–800 chars, ~100 overlap) on sentence boundaries (`pythainlp.tokenize.sent_tokenize` for Thai). Prefix every chunk with its document title (contextual header). Each chunk = dict `{source, heading, text, images, url}`.
4. **Embed**: `SentenceTransformer("intfloat/multilingual-e5-small")`, `"passage: "` prefix for chunks, `"query: "` prefix for queries, `normalize_embeddings=True`.
5. **Index**: `faiss.IndexFlatIP`. Build at startup from `data/`; no persisted index.
6. **Retrieve**: top-k (default 5) with scores. Expose a score threshold constant; below it, the caller answers "ไม่พบข้อมูล" without calling the LLM.
7. **Prompt**: system instruction — answer only from the given context, cite sources as `[filename]`, reply "ไม่พบข้อมูลในเอกสาร" when context lacks the answer, reply in the user's language, never invent prices/specs/policies. Context block lists chunks with their source.
8. **LLM**: `google-genai` SDK (`from google import genai`; `client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(system_instruction=..., temperature=0.2))`). Model name in one constant. Include the last few chat turns for follow-ups; build the retrieval query from the previous user question + current one.
9. Return `answer` and the list of retrieved chunks (with scores, images, url) so the frontend can always show sources and bike photos.

## Constraints
- API key comes from the caller (frontend passes `st.secrets["GEMINI_API_KEY"]`). Never hardcode or log keys.
- `rag.py` must not import streamlit, so it stays testable from the CLI. Caching (`@st.cache_resource`) lives in `app.py`.
- Streamlit Cloud has ~1GB RAM. Keep dependencies minimal. Check whether the CPU-only torch wheel is needed to keep install size down.
- Verify current Gemini model names / SDK signatures with WebFetch on official docs if unsure.

## Check
Leave a `__main__` block in `rag.py` that builds the index and prints top-3 sources for each question in `test_questions.csv` (no LLM call). Run it. Report retrieval hit rate (expected `source` in top-k) in Thai, plus any chunking/threshold tuning you did.
