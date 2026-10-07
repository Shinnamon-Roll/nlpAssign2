# CLAUDE.md — nlpAssign2: RAG Chatbot ร้านบิ๊กไบค์มือสอง (D Bigbike)

สื่อสารกับผู้ใช้เป็น **ภาษาไทย** เสมอ (ศัพท์เทคนิค / โค้ด / ชื่อไลบรารี ใช้ภาษาอังกฤษได้)

## โจทย์ (จาก `Source/NLP-SubTest2.ipynb`)

แบบทดสอบเก็บคะแนนครั้งที่ 2 (10 คะแนน): สร้าง Web App แชตบอต RAG ตอบคำถามจากคลังเอกสาร (ไทย/อังกฤษ)
deploy บน **Streamlit Community Cloud** + โค้ดอยู่บน **GitHub repo ส่วนตัว**

**หัวข้อที่เลือก:** ผู้ช่วย AI ร้านขายรถบิ๊กไบค์มือสอง — ลูกค้าถามเรื่องรถในสต็อก
(ราคา ปี เลขไมล์ สภาพ สเปค) และข้อมูลร้าน (รับประกัน ผ่อน เทิร์นรถ โอนเล่ม ติดต่อ/เวลาเปิด-ปิด)

**แหล่งข้อมูล:** ร้านสมมติ **ไมล์แท้ บิ๊กไบค์ (MileTae Bigbike)** ผู้ช่วยชื่อ "พี่ไมล์" — ข้อมูลจำลองสำหรับ demo
(ผู้ใช้สั่งเมื่อ 2026-10-07). จาก https://www.dbigbike.com/ (เว็บของผู้ใช้ อนุญาตแล้ว) ใช้เฉพาะ **รูปภาพ** + ข้อมูลฐานของรุ่น/ปี/สเปค;
ราคา เลขไมล์ สภาพ และนโยบายร้านทั้งหมดแต่งขึ้นเอง ห้ามใส่ข้อความ/เบอร์/ลิงก์ของ dbigbike ใน `data/`

### ข้อกำหนดเทคนิค (ต้องครบทุกข้อ)
1. **Document Loading & Chunking** — โหลดเอกสาร ทำความสะอาดข้อความ แบ่ง chunk ที่เหมาะสม
2. **Embedding & Vector Search** — sentence embedding + vector DB (FAISS)
3. **Prompt Engineering** — ตอบจาก context เท่านั้น, อ้างอิงแหล่งที่มา, ตอบ "ไม่พบข้อมูล" เมื่อเอกสารไม่มีคำตอบ
4. **LLM ผ่าน API** — ใช้ Google Gemini
5. **Chatbot Interface** — คุยต่อเนื่องได้ + แสดงเอกสารอ้างอิงที่ใช้ตอบ **ทุกครั้ง**

### ไฟล์ที่ repo ต้องมี
- `app.py` — Streamlit app หลัก
- `requirements.txt` — เช่น streamlit, sentence-transformers, faiss-cpu, google-genai, pythainlp
- `README.md` — วิธีใช้งาน, แนวคิด domain, แหล่งที่มาเอกสาร, ตัวอย่าง prompt ที่ใช้สั่ง AI
- `data/` — เอกสารความรู้ **≥ 10 ไฟล์** หรือรวม **≥ 15,000 ตัวอักษร** (ทำให้ได้ทั้งสองเงื่อนไข)
- `test_questions.csv` — **≥ 10 ข้อ** พร้อมคำตอบที่ถูก, มีคำถามที่ **ไม่มีคำตอบในเอกสาร ≥ 2 ข้อ**

### เกณฑ์ให้คะแนน
| ข้อ | คะแนน |
|---|---|
| ไฟล์เอกสารความรู้ + ไฟล์คำถามทดสอบ | 1 |
| โค้ดบน GitHub + เว็บ Streamlit ใช้งานได้จริง | 2 |
| ความคิดสร้างสรรค์หัวข้อ + ความเหมาะสมของเอกสาร | 2 |
| RAG ถูกต้อง: Chunking, Retrieval, Prompt | 3 |
| ตอบอิงเอกสาร, แสดงแหล่งอ้างอิง, ปฏิเสธเมื่อไม่มีข้อมูล | 1 |
| หน้าเว็บใช้งานง่าย | 1 |

## กฎเหล็ก
- **ห้าม commit API key เด็ดขาด** (โดนหักคะแนน) — อ่าน key ผ่าน `st.secrets["GEMINI_API_KEY"]` เท่านั้น
- `.streamlit/secrets.toml` ต้องอยู่ใน `.gitignore` — ก่อน commit ทุกครั้ง grep หา key ใน diff
- Streamlit Cloud RAM จำกัด (~1GB): ใช้ embedding model เล็ก, โหลด model + index **ครั้งเดียว** ด้วย `@st.cache_resource`
- ร้านสมมติ → แต่งนโยบายร้านได้ แต่ต้อง **สอดคล้องกันทุกไฟล์** และระบุใน README/หน้าเว็บว่าเป็นร้านสมมติ
- บอทยังต้องตอบจากเอกสารเท่านั้น — หัวข้อที่สงวนไว้เป็นคำถาม "ไม่พบข้อมูล" (เช่า รถยนต์ บริษัทประกัน สาขาต่างประเทศ) ห้ามเขียนลง `data/`
- ทดสอบ URL จริงในโหมด Incognito ก่อนส่ง

## Stack
- UI: Streamlit (`st.chat_message`, `st.chat_input`, `st.session_state`)
- Embedding: `intfloat/multilingual-e5-small` (sentence-transformers)
  - e5 ต้องใส่ prefix: `"query: ..."` ตอน search, `"passage: ..."` ตอน index
  - `normalize_embeddings=True` + `faiss.IndexFlatIP` = cosine similarity
- Vector DB: FAISS (`faiss-cpu`), build ตอน start จาก `data/` (corpus เล็ก ไม่ต้อง persist index)
- Thai text: `pythainlp` (sentence/word tokenize ตอน chunk)
  - `sent_tokenize` engine default `crfcut` ต้องใช้ `python-crfsuite` — ติดตั้งเพิ่ม หรือใช้ `engine="whitespace+newline"`
- LLM: Google Gemini ผ่าน SDK `google-genai` (`from google import genai`) — ไม่ใช่ `google-generativeai` ตัวเก่าที่ deprecated
  - model default `gemini-3.8-flash` (ตรวจเมื่อ 2026-10-07; `gemini-2.5-flash` ใช้ได้เฉพาะ key ที่เคยใช้มาก่อน) — fallback `gemini-3.5-flash-lite`
  - Gemini 3 ไม่ควรตั้ง temperature ต่ำ (เสี่ยง looping) — ใช้ค่า default
  - history role ต้องเป็น `"model"` ไม่ใช่ `"assistant"`; quota error = `google.genai.errors.APIError` ที่ `code == 429`
- Streamlit Cloud: ติดตั้งด้วย uv, เลือก Python 3.12 ตอน deploy, แอป sleep หลังไม่มีคนเข้า 12 ชม. (เปิดปลุกก่อนส่งงาน)

## โครงสร้างไฟล์
```
app.py                 # frontend: Streamlit chat UI (agent: frontend)
rag.py                 # backend: load → clean → chunk → embed → FAISS → prompt → Gemini (agent: backend)
requirements.txt
README.md
test_questions.csv     # question,expected_answer,answerable,source (agent: research)
scrape.py              # ดึงประกาศ dbigbike → scraped/ (gitignored) ใช้ครั้งเดียวเป็นฐาน
make_data.py           # data/bikes.csv → bike_*.md + inventory_summary.md
data/
  bikes.csv            # master สต็อกรถ (แก้ที่นี่ แล้วรัน make_data.py)
  inventory_summary.md # ตารางสรุปรถทุกคัน (generated)
  bike_*.md            # 1 ไฟล์ต่อรถ 1 คัน (generated), มีบรรทัด `รูปภาพ:` เก็บ URL รูปจาก dbigbike.com
  shop_*.md            # นโยบายร้านสมมติ: profile, รับประกัน, ไฟแนนซ์, เทิร์น, โอนเล่ม, จอง/ทดลองขับ, ส่งรถ/บริการ, FAQ
  guide_*.md           # คู่มือเลือก/ดูแลรถ (เขียนเอง)
.streamlit/secrets.toml  # local only, gitignored
Source/NLP-SubTest2.ipynb  # ไฟล์โจทย์ (ต้องกรอกหัวข้อ + URL แล้วส่งคืน)
```

รูปภาพ: เก็บเป็น URL ในไฟล์ `bike_*.md` (ไม่โหลดรูปเข้า repo) → backend แยก URL ออกจาก text ก่อน embed → frontend แสดงรูปรถที่ถูกอ้างอิง

## แนวทาง RAG
- **Chunking:** แบ่งตามหัวข้อ markdown ก่อน แล้วค่อยตัดตามความยาว (~500–800 ตัวอักษร, overlap ~100)
  แต่ละ chunk ขึ้นต้นด้วยชื่อเอกสาร/ชื่อรถ (contextual header) เพื่อให้ค้นเจอแม้ chunk ไม่มีชื่อรุ่น
- **Retrieval:** top-k ≈ 4–5; ถ้า score สูงสุดต่ำกว่า threshold → ตอบ "ไม่พบข้อมูล" ได้เลย
- **Prompt:** system instruction บังคับตอบจาก context เท่านั้น, อ้าง `[ชื่อไฟล์]`, ไม่มีข้อมูล → "ไม่พบข้อมูลในเอกสาร", ตอบภาษาเดียวกับคำถาม
- **คุยต่อเนื่อง:** ส่งประวัติแชตไม่กี่ turn ล่าสุดไปด้วย; คำถามต่อเนื่อง ("คันนี้ผ่อนเท่าไร") ต้อง retrieval ได้ — รวมคำถามก่อนหน้าเข้า query
- **อ้างอิง:** ทุกคำตอบแสดง source (ชื่อไฟล์ + ข้อความ chunk + score) ใน `st.expander`

## Agents (`.claude/agents/`)
- `research` — ดึงข้อมูลรถ+รูปจาก dbigbike.com เป็น `data/`, `test_questions.csv`, ส่วน domain/แหล่งที่มาใน README, ตรวจชื่อ model/API ล่าสุด
- `backend` — `rag.py`, `requirements.txt`
- `frontend` — `app.py`, `.streamlit/config.toml` (ถ้าต้องการ)

ลำดับงาน: research (data) → backend → frontend → ทดสอบกับ `test_questions.csv` → push GitHub → deploy

## Checklist ส่งงาน
- [ ] `data/` ≥ 10 ไฟล์ และ ≥ 15,000 ตัวอักษร
- [ ] `test_questions.csv` ≥ 10 ข้อ, ไม่มีคำตอบ ≥ 2 ข้อ
- [ ] README ครบ: วิธีใช้, แนวคิด domain, แหล่งที่มา, ตัวอย่าง prompt ที่สั่ง AI
- [ ] ไม่มี API key ใน repo / git history
- [ ] Deploy Streamlit Cloud + ใส่ `GEMINI_API_KEY` ใน Secrets + เปิดใน Incognito ได้
- [ ] กรอกชื่อ-สกุล, หัวข้อ, Streamlit URL, GitHub URL ใน notebook
- [ ] PDF capture หน้าจอการทำงานพร้อมคำอธิบาย
