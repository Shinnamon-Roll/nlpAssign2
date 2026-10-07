"""Streamlit chat UI for the D Bigbike RAG chatbot. All RAG logic lives in rag.py."""
import html
import re
from pathlib import Path

import streamlit as st

from rag import NOT_FOUND, answer, build_index, retrieve

DATA = Path(__file__).parent / "data"
BOT = ":material/two_wheeler:"
USER = ":material/person:"  # default user avatar is red, which is reserved for NOT_FOUND/error
TH_MONTHS = "ม.ค. ก.พ. มี.ค. เม.ย. พ.ค. มิ.ย. ก.ค. ส.ค. ก.ย. ต.ค. พ.ย. ธ.ค.".split()
EXAMPLES = [
    "มี Yamaha MT-09 ไหม ราคาเท่าไร",
    "รถราคาไม่เกิน 300,000 บาทมีรุ่นไหนบ้าง",
    "ร้านเปิดกี่โมง อยู่ที่ไหน",
    "ผ่อนดอกเบี้ยกี่เปอร์เซ็นต์",
    "มีบริการเช่ารถรายวันไหม",
]
WELCOME = (
    "สวัสดีครับ ผมพี่ไมล์ ผู้ช่วยเลือกรถของร้านไมล์แท้ บิ๊กไบค์ "
    "อยากรู้อะไรเรื่องรถในโชว์รูมถามได้เลย ทั้งราคา ปี เลขไมล์ สภาพรถ และสเปค "
    "รวมถึงเรื่องของร้าน เช่น การรับประกัน ไฟแนนซ์ เทิร์นรถ โอนเล่ม และเวลาเปิด-ปิด\n\n"
    "ผมตอบจากเอกสารของร้านเท่านั้น และบอกทุกครั้งว่าใช้เอกสารไหนตอบ "
    "ถ้าเรื่องไหนไม่มีในข้อมูล ผมจะบอกตรงๆ ครับ"
)
EXT = 'target="_blank" rel="noopener noreferrer"'
HINT = (
    '<p class="db-hint">ถามร้านโดยตรงได้ที่ โทร <a href="tel:021234567">02-123-4567</a> '
    "หรือ LINE @miletae.demo</p>"
)
SIDEBAR = (
    '<div class="db-side">'
    "<p>ร้านบิ๊กไบค์มือสองคัดสภาพ เลขไมล์แท้ทุกคัน ถนนราชพฤกษ์ ฝั่งธนบุรี กรุงเทพฯ</p>"
    "<p>เปิด 10:00–19:00 น. หยุดทุกวันพุธ</p>"
    '<p>โทร <a href="tel:021234567">02-123-4567</a><br>LINE @miletae.demo</p>'
    '<p class="db-muted">ร้านสมมติสำหรับเดโมงานวิชา NLP รูปรถได้รับอนุญาตจาก dbigbike.com '
    "ข้อมูลอื่นเป็นข้อมูลจำลอง</p>"
    "</div>"
)
CSS = """<style>
[data-testid="stChatMessage"] { background: #F7F8F9; border-radius: 8px; padding: 12px 16px; }
.db-stock { margin: -8px 0 8px; }
.db-side p, .db-src p, .db-card p { margin: 0 0 8px; }
.db-muted, .db-src__meta { color: #5E6B78; }
.db-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin: 8px 0; }
.db-card { border: 1px solid rgba(94, 107, 120, .4); border-radius: 8px; overflow: hidden; background: #F7F8F9; }
.db-card__img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; background: #E6E8EB; }
.db-card__body { padding: 10px 12px 4px; }
.db-card__title { font: 600 18px/1.3 'Chakra Petch', sans-serif; }
.db-tag { display: inline-block; transform: rotate(-2deg); background: #F2C230; color: #1B2733;
          font: 600 24px/1.2 'Chakra Petch', sans-serif; padding: 2px 10px; border-radius: 3px; }
.db-tag small { font-size: 15px; }
.db-card__note { color: #5E6B78; }
.db-card__status { display: inline-block; margin: 0 0 6px; padding: 0 8px; border: 1px solid #1B2733;
                   border-radius: 3px; font: 600 15px/1.6 'Chakra Petch', sans-serif; }
.db-odo { display: flex; align-items: center; gap: 2px; margin: 0 0 8px; color: #5E6B78; }
.db-odo__d { display: inline-block; min-width: 1.2em; padding: 1px 3px; border-radius: 2px; text-align: center;
             background: #1B2733; color: #F7F8F9; font: 600 15px/1.4 'Chakra Petch', sans-serif; }
.db-odo__sep { color: #1B2733; font: 600 15px/1.4 'Chakra Petch', sans-serif; }
.db-odo__label { margin-right: 6px; }
.db-odo__unit { margin-left: 6px; }
.db-card a, .db-side a, .db-hint a { color: #1B2733; font-weight: 500; text-decoration: underline; text-underline-offset: 3px; }
.db-card a:focus-visible, .db-side a:focus-visible, .db-hint a:focus-visible { outline: 2px solid #1B2733; outline-offset: 2px; }
[class*="st-key-nf_"] { border-left: 3px solid #B3362C; padding-left: 12px; }
[class*="st-key-nf_"] p { color: #B3362C; }
.db-src { padding-top: 8px; border-top: 1px solid rgba(94, 107, 120, .3); }
.db-src:first-child { border-top: 0; padding-top: 0; }
.db-src__file { font-weight: 500; }
@media (prefers-reduced-motion: reduce) {
  .db-cards *, .db-side *, .db-src * { transition: none !important; animation: none !important; }
}
</style>"""


def esc(v):
    return html.escape(str(v))


def is_http(u):
    return isinstance(u, str) and u.startswith(("https://", "http://"))


def show_html(s):
    # Must stay a single line: a blank line would end the markdown HTML block.
    st.markdown(s, unsafe_allow_html=True)


def field(meta, key):
    v = str(meta.get(key) or "").strip()
    return "" if v in ("-", "0") else v


def stock_line():
    files = list(DATA.glob("bike_*.md"))
    if not files:
        return "กำลังอัปเดตข้อมูลรถในสต็อก"
    reserved = sum("สถานะ: ติดจอง" in f.read_text(encoding="utf-8") for f in files)
    n = f"{len(files) - reserved} คัน" + (f" ติดจอง {reserved} คัน" if reserved else "")
    try:
        text = (DATA / "inventory_summary.md").read_text(encoding="utf-8")
        m = re.search(r"ข้อมูล ณ วันที่:\s*(\d{4})-(\d{2})-(\d{2})", text)
    except OSError:
        m = None
    if not m:
        return f"มีรถพร้อมขาย {n}"
    y, mo, d = map(int, m.groups())
    return f"สต็อกวันที่ {d} {TH_MONTHS[mo - 1]} {y + 543} มีรถพร้อมขาย {n}"


def odometer(v):
    v = v.removesuffix("กม.").strip()
    if not re.search(r"\d", v):
        return f'<p class="db-card__note">เลขไมล์ {esc(v)}</p>'
    cells = "".join(
        f'<span class="db-odo__sep">{esc(c)}</span>' if c in ",." else f'<span class="db-odo__d">{esc(c)}</span>'
        for c in v if not c.isspace()
    )
    return (f'<div class="db-odo" role="img" aria-label="เลขไมล์ {esc(v)} กิโลเมตร">'
            f'<span class="db-odo__label">ไมล์</span>{cells}<span class="db-odo__unit">กม.</span></div>')


def bike_card(s):
    meta = s.get("meta") or {}
    title = s.get("title") or meta.get("ชื่อรุ่น") or s.get("source", "")
    img = next((u for u in s.get("images") or [] if is_http(u)), None)
    out = ['<div class="db-card">']
    if img:
        out.append(f'<img class="db-card__img" src="{esc(img)}" alt="รูปรถ {esc(title)}" loading="lazy">')
    out.append(f'<div class="db-card__body"><p class="db-card__title">{esc(title)}</p>')
    if (status := field(meta, "สถานะ")) and status != "พร้อมขาย":
        out.append(f'<p class="db-card__status">{esc(status)}</p>')
    if price := field(meta, "ราคาขาย (บาท)"):
        out.append(f'<p class="db-tag">{esc(price)} <small>บาท</small></p>')
    if discount := field(meta, "ส่วนลด (บาท)"):
        out.append(f'<p class="db-card__note">ส่วนลด {esc(discount)} บาท</p>')
    if odo := field(meta, "เลขไมล์ (กม.)"):
        out.append(odometer(odo))
    look = " ".join(f"{k}{v}" for k, v in (("สี", field(meta, "สี")), ("เกรดสภาพ ", field(meta, "เกรดสภาพ"))) if v)
    if look:
        out.append(f'<p class="db-card__note">{esc(look)}</p>')
    if is_http(s.get("url")):
        out.append(f'<p><a href="{esc(s["url"])}" {EXT}>ดูประกาศบนเว็บร้าน</a></p>')
    out.append("</div></div>")
    return "".join(out)


def cited_bikes(text, sources):
    """Bike sources whose filename the answer actually cites; deduped, best first, max 3."""
    seen, out = set(), []
    for s in sources:
        src = s.get("source", "")
        if src.startswith("bike_") and src not in seen and Path(src).stem in text:
            seen.add(src)
            out.append(s)
    return out[:3]


def sources_html(sources):
    if not sources:
        return '<p class="db-muted">ไม่มีเอกสารที่เกี่ยวข้องกับคำถามนี้</p>'
    rows = []
    for s in sources:
        heading = f"หัวข้อ {esc(s['heading'])}, " if s.get("heading") else ""
        text = esc(s.get("text", "")).replace("\r", "").replace("\n", "<br>")
        rows.append(
            f'<div class="db-src"><p class="db-src__file">{esc(s.get("source", ""))}</p>'
            f'<p class="db-src__meta">{heading}คะแนนความเกี่ยวข้อง {float(s.get("score", 0)):.2f}</p>'
            f"<p>{text}</p></div>"
        )
    return "".join(rows)


def show_answer(i, m):
    text, sources = m["content"], m.get("sources") or []
    if m.get("error"):
        st.error(text)
    elif text.startswith(NOT_FOUND):  # rag's prompt: a full refusal starts with NOT_FOUND
        with st.container(key=f"nf_{i}"):
            st.markdown(text)
        show_html(HINT)
    else:
        st.markdown(text)
        if cards := cited_bikes(text, sources):
            show_html('<div class="db-cards">' + "".join(map(bike_card, cards)) + "</div>")
        if NOT_FOUND in text:  # partial answer: point to the shop for the missing part
            show_html(HINT)
    with st.expander(f"เอกสารอ้างอิง ({len(sources)})"):
        show_html(sources_html(sources))


def error_text(e):
    code, msg = getattr(e, "code", None), str(e)
    if code == 429:
        return "ตอนนี้ระบบถูกใช้งานเยอะจนเต็มโควตาชั่วคราว รอสักครู่ประมาณ 1 นาที แล้วลองถามใหม่อีกครั้งนะครับ"
    if code == 503:
        return "โมเดลมีผู้ใช้งานมาก ลองส่งอีกครั้งในไม่กี่วินาทีนะครับ"
    if code in (400, 401, 403) and ("API key" in msg or "API_KEY" in msg or code != 400):
        return "GEMINI_API_KEY ใช้งานไม่ได้ ตรวจค่าใน Secrets ว่าถูกต้อง แล้วรีเฟรชหน้านี้ครับ"
    return "ตอนนี้ติดต่อระบบตอบคำถามไม่ได้ ลองถามใหม่อีกครั้งนะครับ ถ้ายังไม่ได้ โทรถามร้านได้ที่ 02-123-4567"


def ask(store, question, history, api_key):
    try:
        text, sources = answer(store, question, history, api_key)
        return {"role": "assistant", "content": text, "sources": sources}
    except Exception as e:  # Gemini quota/network/etc.; never crash the app
        print(f"answer() failed: {type(e).__name__} code={getattr(e, 'code', None)}")
        try:
            sources = retrieve(store, question)
        except Exception:
            sources = []
        return {"role": "assistant", "content": error_text(e), "sources": sources, "error": True}


def chat_history():
    """Previous turns for rag.answer; a failed turn drops both its question and the error."""
    hist = []
    for m in st.session_state.messages:
        if m.get("error"):
            hist.pop()
        else:
            hist.append({"role": m["role"], "content": m["content"]})
    return hist


def pick_example():
    st.session_state.pending = st.session_state.example
    st.session_state.example = None


@st.cache_resource(show_spinner="กำลังเตรียมข้อมูลรถในร้าน ครั้งแรกอาจใช้เวลาประมาณ 1 นาที")
def load_store():
    return build_index(str(DATA))


st.set_page_config(page_title="พี่ไมล์ ผู้ช่วยเลือกบิ๊กไบค์", page_icon=BOT, layout="centered")
st.html(CSS)
st.session_state.setdefault("messages", [])

with st.sidebar:
    st.header("ไมล์แท้ บิ๊กไบค์", anchor=False)
    show_html(SIDEBAR)
    st.button("ล้างแชต", on_click=st.session_state.messages.clear, width="stretch")

st.title("ถามเรื่องรถในร้านได้เลย", anchor=False)
show_html(f'<p class="db-stock">{esc(stock_line())}</p>')

try:
    api_key = str(st.secrets.get("GEMINI_API_KEY") or "").strip()
except Exception:  # no secrets file at all
    api_key = ""
if not api_key:
    st.error(
        "ยังไม่ได้ตั้งค่า GEMINI_API_KEY แชตจึงยังใช้งานไม่ได้\n\n"
        "รันบนเครื่อง: ใส่บรรทัด `GEMINI_API_KEY = \"...\"` ในไฟล์ `.streamlit/secrets.toml`\n\n"
        "บน Streamlit Community Cloud: เปิด App settings แล้วไปที่ Secrets ใส่บรรทัดเดียวกัน จากนั้นรีเฟรชหน้านี้"
    )
    st.stop()

try:
    store = load_store()
except Exception as e:
    print(f"build_index failed: {type(e).__name__}: {e}")
    st.error("ยังโหลดข้อมูลรถไม่สำเร็จ ลองรีเฟรชหน้านี้อีกครั้งในอีกสักครู่ครับ")
    st.stop()

with st.chat_message("assistant", avatar=BOT):
    st.markdown(WELCOME)
    st.pills("ลองถามแบบนี้", EXAMPLES, key="example", on_change=pick_example)

for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"], avatar=BOT if m["role"] == "assistant" else USER):
        if m["role"] == "user":
            st.markdown(m["content"])
        else:
            show_answer(i, m)

question = st.chat_input("พิมพ์คำถาม เช่น MT-09 ราคาเท่าไร") or st.session_state.pop("pending", None)
if question:
    history = chat_history()
    msgs = st.session_state.messages
    msgs.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=USER):
        st.markdown(question)
    with st.chat_message("assistant", avatar=BOT):
        with st.spinner("กำลังหาข้อมูลให้ครับ"):
            msg = ask(store, question, history, api_key)
        msgs.append(msg)
        show_answer(len(msgs) - 1, msg)
