# พี่ไมล์ ผู้ช่วยเลือกบิ๊กไบค์ (แชตบอต RAG ร้านบิ๊กไบค์มือสอง)

"พี่ไมล์" คือผู้ช่วย AI ของร้าน **ไมล์แท้ บิ๊กไบค์ (MileTae Bigbike)** ร้านบิ๊กไบค์มือสอง **สมมติ** ที่สร้างขึ้นสำหรับเดโมงานวิชา NLP
ตอบคำถามลูกค้าเรื่องรถในสต็อก (ราคา ปี เลขไมล์ สี เกรดสภาพ สเปค ค่างวด) และนโยบายร้าน
(รับประกัน ไฟแนนซ์ เทิร์นรถ โอนเล่ม จอง/ทดลองขับ ส่งรถ)
โดยตอบจากเอกสารของร้านเท่านั้น แสดงเอกสารอ้างอิงทุกคำตอบ และตอบว่า "ไม่พบข้อมูลในเอกสาร" เมื่อเอกสารไม่มีคำตอบ

- เว็บแอป (Streamlit Community Cloud): _TODO: ใส่ URL หลัง deploy_
- GitHub: https://github.com/Shinnamon-Roll/nlpAssign2

## แนวคิดของ Domain
ร้านรถมือสองมีรถเข้าออกทุกสัปดาห์ และลูกค้ามักถามคำถามซ้ำๆ ทาง LINE หรือโทรศัพท์ เช่น "MT-09 ยังอยู่ไหม ราคาเท่าไร",
"งบไม่เกิน 3 แสนมีรุ่นไหนบ้าง" หรือ "ร้านเปิดกี่โมง"
แชตบอตนี้ช่วยตอบคำถามเหล่านี้ได้ทันทีจากข้อมูลประกาศขายจริงของร้าน
คำตอบทุกข้ออ้างอิงไฟล์ต้นทาง ลูกค้าจึงตรวจสอบได้ และกดไปดูประกาศจริงบนเว็บร้านได้

บอทถูกบังคับให้ตอบจากเอกสารเท่านั้น เรื่องที่ไม่มีในเอกสาร (เช่น เช่ารถรายวัน หรือซ่อมรถยนต์) บอทจะตอบว่าไม่พบข้อมูล
แล้วแนะนำให้ติดต่อร้านโดยตรง

## แหล่งที่มาของเอกสาร
> ร้าน "ไมล์แท้ บิ๊กไบค์" เป็นร้านสมมติ ราคา เลขไมล์ สภาพรถ นโยบายร้าน และข้อมูลติดต่อทั้งหมดเป็นข้อมูลจำลองสำหรับเดโม

- **รูปรถ** และข้อมูลพื้นฐานของรุ่น (ยี่ห้อ รุ่น ปี cc สเปค) มาจาก https://www.dbigbike.com/
  - เป็นเว็บของผู้จัดทำเอง จึงได้รับอนุญาตให้ใช้ ดึงข้อมูลเมื่อ **2026-10-07**
  - รูปเก็บเป็น URL เท่านั้น ไม่โหลดไฟล์รูปเข้า repo
- **ขั้นตอนสร้างข้อมูล**
  1. `scrape.py` ดึงประกาศลง `scraped/` (ไม่ขึ้น git) ใช้ Python stdlib ส่ง request ทีละครั้งและเว้นช่วง 1 วินาที
  2. `python3 make_data.py --from-scraped` สร้าง `data/bikes.csv` เป็นสต็อกสมมติ 44 คัน (seed คงที่) เก็บแค่รุ่น/สเปค/รูปจากของจริง ส่วนราคา ไมล์ สี เกรด และของแต่งสุ่มใหม่
  3. `python3 make_data.py` สร้าง `bike_*.md` และ `inventory_summary.md` จาก `bikes.csv` พร้อมตรวจว่าทุกไฟล์ตรงกัน
- เอกสารนโยบายร้านและคู่มือเขียนขึ้นเองทั้งหมด
- รวม 56 ไฟล์ .md มากกว่า 110,000 ตัวอักษร

| ไฟล์ใน `data/` | เนื้อหา |
|---|---|
| `bikes.csv` | สต็อกหลัก 44 คัน (แก้ที่ไฟล์นี้ แล้วรัน `make_data.py`) |
| `bike_*.md` (44 ไฟล์) | รถ 1 คันต่อ 1 ไฟล์: รหัสสต็อก ราคา ส่วนลด เลขไมล์ สี เกรดสภาพ สถานะ สเปค ของแต่ง การรับประกัน ตัวอย่างค่างวด และ URL รูป |
| `inventory_summary.md` | ตารางสรุปรถทุกคัน สำหรับคำถามเปรียบเทียบ กรองราคา และนับจำนวน |
| `shop_*.md` (8 ไฟล์) | ข้อมูลร้าน, รับประกัน, ไฟแนนซ์, เทิร์นรถ, โอนเล่ม, จอง/ทดลองขับ, ส่งรถ/บริการหลังการขาย, FAQ |
| `guide_*.md` (3 ไฟล์) | คู่มือเลือกบิ๊กไบค์มือสอง, เลือกคันแรกตามงบ, การดูแลรถเบื้องต้น |

## RAG Pipeline (`rag.py`)
1. **Document Loading & Cleaning**
   - อ่าน `data/*.md` แล้วแยกบรรทัด `รูปภาพ:` และ `ลิงก์ประกาศ:` ออกเป็น metadata เพื่อไม่ให้ URL ปนใน embedding
   - normalize ข้อความไทยด้วย `pythainlp`, ลบ zero-width char และเส้นคั่น
2. **Chunking**
   - ตัดตามหัวข้อ Markdown ก่อน แล้วตัดตามความยาว (≤800 ตัวอักษร, overlap 100) ที่ขอบประโยคด้วย `pythainlp.sent_tokenize`
   - ทุก chunk ขึ้นต้นด้วยชื่อรถหรือชื่อเอกสาร (contextual header) จึงค้นเจอแม้เนื้อหาใน chunk ไม่มีชื่อรุ่น
   - ตารางสต็อกตัดทีละ 6 แถว และใส่หัวตารางซ้ำทุก chunk
3. **Embedding & Vector Search**
   - ใช้ `intfloat/multilingual-e5-small` (รองรับไทยและอังกฤษ, ขนาดเล็ก เหมาะกับ RAM ของ Streamlit Cloud)
   - ใส่ prefix `passage:` ตอนสร้าง index และ `query:` ตอนค้นหา
   - ใช้ `normalize_embeddings=True` คู่กับ `faiss.IndexFlatIP` จึงได้คะแนนเป็น cosine similarity
   - top-k = 5 (ไม่เกิน 2 chunk ต่อไฟล์) ถ้าคะแนนสูงสุดต่ำกว่า threshold 0.78 ตอบ "ไม่พบข้อมูลในเอกสาร" ทันทีโดยไม่เรียก LLM
   - ไฟล์รถและตารางสต็อกที่ค้นเจอจะส่งทั้งไฟล์ให้ LLM จึงตอบคำถามแบบ "ถูกที่สุด" หรือ "คันนี้ผ่อนเท่าไร" ได้
   - ผลกับ `test_questions.csv`: hit@5 = 96% (25/26 ข้อที่ตอบได้)
4. **คำถามต่อเนื่อง:** ค้นหาทั้งจากคำถามปัจจุบัน และจากคำถามก่อนหน้ารวมกับคำถามปัจจุบัน แล้วส่งประวัติแชต 3 turn ล่าสุดให้ LLM
5. **LLM:** Google Gemini (`gemini-3.8-flash` ถ้าโมเดลไม่ว่างจะลอง `gemini-3.5-flash-lite` แทน) ผ่าน SDK `google-genai`
6. **Prompt Engineering:** ใช้ system instruction ด้านล่าง และแนบ context พร้อมชื่อไฟล์ของทุก chunk

```text
คุณคือพี่ไมล์ ผู้ช่วยขายของร้านไมล์แท้ บิ๊กไบค์ (MileTae Bigbike) ร้านบิ๊กไบค์มือสอง
กติกา:
1. ตอบจากข้อมูลใน "เอกสารอ้างอิง" ที่ให้มาในข้อความล่าสุดเท่านั้น ห้ามใช้ความรู้ภายนอก
2. อ้างอิงแหล่งที่มาทุกข้อเท็จจริงด้วยชื่อไฟล์ในวงเล็บเหลี่ยม ตรงตามที่ให้มา
3. ห้ามเดาหรือแต่งราคา สเปค เลขไมล์ เงื่อนไขไฟแนนซ์ อัตราดอกเบี้ย ระยะเวลารับประกัน หรือนโยบายร้านที่ไม่มีในเอกสาร
4. ถ้าเอกสารไม่มีคำตอบ ให้ตอบขึ้นต้นด้วย "ไม่พบข้อมูลในเอกสาร"
5. คำถามต่อเนื่อง ("คันนี้", "รุ่นนี้") ให้ดูจากประวัติแชต แต่ข้อเท็จจริงต้องมาจากเอกสารอ้างอิงเท่านั้น
6. ตอบภาษาเดียวกับคำถาม
7. ตอบกระชับ สุภาพ แบบพนักงานขาย
```

## หน้าเว็บ (`app.py`)
- แชตคุยต่อเนื่องได้ ประวัติเก็บใน `st.session_state`
- โหลดโมเดลและ index ครั้งเดียวด้วย `@st.cache_resource`
- ทุกคำตอบมีส่วน "เอกสารอ้างอิง" แสดงชื่อไฟล์ หัวข้อ score และข้อความของ chunk
- รถที่ถูกอ้างอิงในคำตอบแสดงเป็นการ์ด มีรูป ป้ายราคา เลขไมล์ และลิงก์ไปประกาศบนเว็บร้าน
- มีปุ่มตัวอย่างคำถาม, ข้อมูลติดต่อร้าน และปุ่มล้างแชต

## วิธีใช้งาน
### รันบนเครื่อง
```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p .streamlit && echo 'GEMINI_API_KEY = "ใส่ key ของคุณ"' > .streamlit/secrets.toml   # ไฟล์นี้อยู่ใน .gitignore
.venv/bin/streamlit run app.py
```
- ทดสอบ retrieval กับ `test_questions.csv` โดยไม่เรียก LLM: `.venv/bin/python rag.py`
- แก้สต็อก: แก้ไฟล์ `data/bikes.csv` แล้วรัน `python3 make_data.py`

### Deploy บน Streamlit Community Cloud
1. เข้า https://share.streamlit.io แล้วกด Create app และเลือก repo นี้ พร้อม main file `app.py`
2. ใน Advanced settings เลือก Python 3.12 แล้วใส่ Secrets เป็น `GEMINI_API_KEY = "..."`
3. กด Deploy (ครั้งแรกโหลดโมเดล embedding ประมาณ 1–2 นาที)

## ไฟล์คำถามทดสอบ
`test_questions.csv` มี 31 ข้อ ตอบได้ 26 ข้อ และไม่มีคำตอบในเอกสาร 5 ข้อ โดยมีคอลัมน์ `question,expected_answer,answerable,source`
คำถามที่ไม่มีคำตอบ ได้แก่ เช่ารถรายวัน, ซ่อมรถยนต์, บริษัทประกันภัย, สาขาต่างประเทศ และพยากรณ์อากาศ บอทต้องตอบ "ไม่พบข้อมูลในเอกสาร"

## ตัวอย่าง Prompt ที่ใช้สั่ง AI
พัฒนาโดยใช้ Claude Code เป็นผู้ช่วยเขียนโปรแกรม แบ่งงานให้ agent 3 ตัว คือ research/scraper, backend และ frontend ตัวอย่าง prompt ที่ใช้:

1. วางแผนโปรเจกต์
   > read NLP-SubTest2.ipynb and make claude.md to summarize and then create claude agent backend, frontend, research for help me to build this project if you have question from NLP-SubTest2.ipynb pls ask me
2. สั่งเริ่มสร้าง
   > Okay we will build website follow md that we just talk read docs again and if you have some question ask me
3. ดึงข้อมูลจากเว็บร้าน
   > สร้าง agent ขึ้นมา 1 ตัว เพื่อ scraping ข้อมูลจากเว็บต้นฉบับ เพื่อดึงข้อมูลทั่วไป เช่น ราคา สเปค และลิงก์รูปของรถ รุ่นรถ เพื่อนำมาสร้างเว็บไซต์นี้ สร้าง directory ไว้สำหรับ data แล้วเก็บข้อมูลต่างๆ ไว้ในนั้น แล้วรันทิ้งไว้ระหว่างที่ agent ตัวอื่นกำลัง build website
4. เปลี่ยนเป็นข้อมูลร้านสมมติ
   > ดึงข้อมูลออกมาแล้วเก็บไว้ที่เรา ต้องการให้ปั้นข้อมูลขึ้นมาใหม่ได้เลย ไม่ต้องตามเป๊ะ เพราะตอนนี้ยังเป็น demo make ไฟล์ข้อมูล csv ขึ้นมาเองได้เลย แค่อยากให้เอารูปมาจากเว็บนั้นกับข้อมูลบางส่วนเท่านั้น
5. คำสั่งให้ scraper agent (ย่อ)
   > Scrape ALL bikes whose product page says "สถานะปัจจุบัน : พร้อมขาย"… Shop policy: use ONLY what the site states. Never invent warranty length, down payment, interest rate… Store image URLs only, never download images. Write test_questions.csv with at least 3 unanswerable questions.
6. คำสั่งให้ backend agent (ย่อ)
   > Chunk by `##` heading, then ~500–800 chars with ~100 overlap on sentence boundaries; prefix every chunk with the doc title. Embed with multilingual-e5-small (passage:/query: prefixes), faiss.IndexFlatIP. If top score < SCORE_THRESHOLD return "ไม่พบข้อมูลในเอกสาร" without calling Gemini. Always return the retrieved sources.
7. คำสั่งให้ frontend agent (ย่อ ใช้แนวทาง frontend-design)
   > Light "showroom" theme… The one bold element is the bike card: price tag slightly rotated like a sticker on a windshield, odometer digits in small dark boxes. Every assistant answer shows its sources in an expander.
