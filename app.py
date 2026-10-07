"""Streamlit chat UI for the MileTae Bigbike RAG chatbot (พี่ไมล์). All RAG logic lives in rag.py."""
import csv
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
    "รถราคาไม่เกิน 300,000 บาทมีรุ่นไหนบ้าง",
    "คันไหนถูกที่สุดในร้าน",
    "ผ่อนดอกเบี้ยกี่เปอร์เซ็นต์",
    "รับประกันกี่เดือน",
    "มีบริการเช่ารถรายวันไหม",
]
WELCOME = (
    "สวัสดีครับ ผมพี่ไมล์ ผู้ช่วยประจำโชว์รูมไมล์แท้ บิ๊กไบค์ "
    "ถามได้ทั้งราคา ค่างวด สภาพรถ และเงื่อนไขของร้าน ทุกคำตอบมีเอกสารอ้างอิงให้กดดูครับ"
)
HINT = (
    '<p class="db-hint">ถามร้านโดยตรงได้ที่ โทร <a href="tel:021234567">02-123-4567</a> '
    "หรือ LINE @miletae.demo</p>"
)
SIDEBAR = """<div class="db-side">
<p class="db-side__tag">บิ๊กไบค์มือสองคัดสภาพ เลขไมล์แท้ทุกคัน</p>
<dl>
<dt>ที่ตั้ง</dt><dd>ถนนราชพฤกษ์ ฝั่งธนบุรี กรุงเทพฯ</dd>
<dt>เวลาเปิด</dt><dd>10:00–19:00 น. หยุดทุกวันพุธ</dd>
<dt>โทร</dt><dd><a href="tel:021234567">02-123-4567</a></dd>
<dt>LINE</dt><dd>@miletae.demo</dd>
</dl>
<p class="db-muted">ร้านสมมติสำหรับเดโมงานวิชา NLP รูปรถได้รับอนุญาตจาก dbigbike.com ข้อมูลอื่นเป็นข้อมูลจำลอง</p>
</div>"""
CSS = """<style>
[data-testid="stMainBlockContainer"] { padding-top: 4.5rem; }  /* clear the 3.75rem app header */
/* hero: instrument-cluster band */
.db-hero { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 16px 32px;
           background: #1B2733; color: #F7F8F9; border-radius: 8px; padding: 22px 24px; }
.db-hero h1.db-hero__name { font: 600 32px/1.15 'Chakra Petch', sans-serif; color: #F7F8F9; margin: 0; padding: 0; }
.db-hero__tag { margin: 6px 0 0; color: rgba(247, 248, 249, .8); }
.db-hero__meters { display: flex; gap: 24px; }
.db-meter__label, .db-hero__date { font-size: 13px; color: rgba(247, 248, 249, .8); margin: 4px 0 0; }
.db-hero__date { flex-basis: 100%; margin: -4px 0 0; }
.db-hero .db-odo { margin: 0; }
.db-hero .db-odo__d { background: #F7F8F9; color: #1B2733; font-size: 24px; min-width: 1.1em; }
/* chat bubbles */
[data-testid="stChatMessage"] { background: #F7F8F9; border: 1px solid rgba(94, 107, 120, .25); border-radius: 8px; padding: 12px 16px; }
[data-testid="stChatMessage"]:has([class*="st-key-umsg_"]) { flex-direction: row-reverse; background: transparent; border-color: transparent; }
[class*="st-key-umsg_"] { text-align: right; }
.db-cite { display: inline-block; margin: 0 2px; padding: 0 8px; border-radius: 999px; background: #E6E8EB;
           color: #1B2733; font-size: 13px; line-height: 1.7; white-space: nowrap; }
.db-section { font: 600 18px/1.3 'Chakra Petch', sans-serif; margin: 8px 0 0; }
.db-muted, .db-card__note { color: #5E6B78; }
.db-side p, .db-card p { margin: 0 0 6px; }
/* bike cards: the price tag is a sticker slapped on the photo */
.db-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; margin: 12px 0; }
.db-card { border: 1px solid rgba(94, 107, 120, .35); border-radius: 8px; background: #F7F8F9; overflow: hidden; }
.db-card__media { position: relative; }
.db-card__img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; background: #E6E8EB; }
.db-card__status { position: absolute; top: 10px; left: 10px; padding: 0 8px; border-radius: 3px; background: #1B2733;
                   color: #F7F8F9; font: 600 13px/1.7 'Chakra Petch', sans-serif; }
.db-tag { display: inline-block; transform: rotate(-2deg); background: #F2C230; color: #1B2733;
          font: 600 24px/1.2 'Chakra Petch', sans-serif; padding: 2px 10px; border-radius: 3px; margin: 0 0 6px; }
.db-tag small { font-size: 15px; }
.db-card__media .db-tag { position: absolute; left: 10px; bottom: -16px; margin: 0; box-shadow: 0 1px 0 rgba(27, 39, 51, .25); }
.db-card__body { padding: 12px 14px 8px; }
.db-card__media + .db-card__body { padding-top: 26px; }
.db-card__title { font: 600 18px/1.3 'Chakra Petch', sans-serif; min-height: 2.6em; }  /* 2 lines: rows line up */
.db-odo { display: flex; align-items: center; gap: 2px; margin: 0 0 6px; color: #5E6B78; }
.db-odo__d { display: inline-block; min-width: 1.2em; padding: 1px 3px; border-radius: 2px; text-align: center;
             background: #1B2733; color: #F7F8F9; font: 600 15px/1.4 'Chakra Petch', sans-serif; }
.db-odo__sep { color: inherit; font: 600 15px/1.4 'Chakra Petch', sans-serif; }
.db-odo__label { margin-right: 6px; }
.db-odo__unit { margin-left: 6px; }
/* sources */
.db-src { padding: 10px 0; border-top: 1px solid rgba(94, 107, 120, .3); }
.db-src:first-child { border-top: 0; padding-top: 0; }
.db-src__head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.db-src__title { font-weight: 500; }
.db-src__score { display: flex; align-items: center; gap: 6px; font: 600 13px 'Chakra Petch', sans-serif; white-space: nowrap; }
.db-src__bar { width: 64px; height: 6px; border-radius: 3px; background: #E6E8EB; overflow: hidden; }
.db-src__bar i { display: block; height: 100%; background: #1B2733; }
.db-src__file { margin: 2px 0 6px; font-size: 13px; color: #5E6B78; }
.db-src__text { margin: 0; padding: 8px 10px; border-radius: 6px; background: #E6E8EB; font-size: 13px;
                white-space: pre-wrap; max-height: 160px; overflow: auto; }
/* sidebar */
.db-side__tag { font-weight: 500; }
.db-side dl { margin: 12px 0; }
.db-side dt { font-size: 13px; color: #5E6B78; }
.db-side dd { margin: 0 0 8px; margin-inline-start: 0; padding: 0; }
.db-side dl, .db-side dt { padding: 0; margin-inline-start: 0; }
/* not found */
[class*="st-key-nf_"] { border-left: 3px solid #B3362C; padding-left: 12px; }
[class*="st-key-nf_"] p { color: #B3362C; }
.db-card a, .db-side a, .db-hint a { color: #1B2733; font-weight: 500; text-decoration: underline; text-underline-offset: 3px; }
.db-card a:focus-visible, .db-side a:focus-visible, .db-hint a:focus-visible { outline: 2px solid #1B2733; outline-offset: 2px; }
@media (max-width: 640px) {
  .db-hero { padding: 18px; }
  .db-hero h1.db-hero__name { font-size: 24px; }
}
</style>"""


def esc(v):
    return html.escape(str(v))


def is_http(u):
    return isinstance(u, str) and u.startswith(("https://", "http://"))


def thumb(u):
    # the CDN serves resized copies; 640px wide is ~90 KB instead of ~600 KB
    return u.replace("/m_1920x0/", "/m_640x0/")


def field(meta, key):
    v = str(meta.get(key) or "").strip()
    return "" if v in ("-", "0") else v


def odometer(v, label="ไมล์", unit="กม."):
    v = v.removesuffix(unit).strip()
    if not re.search(r"\d", v):
        return f'<p class="db-card__note">{esc(label)} {esc(v)}</p>'
    cells = "".join(
        f'<span class="db-odo__sep">{esc(c)}</span>' if c in ",." else f'<span class="db-odo__d">{esc(c)}</span>'
        for c in v if not c.isspace()
    )
    lab = f'<span class="db-odo__label">{esc(label)}</span>' if label else ""
    uni = f'<span class="db-odo__unit">{esc(unit)}</span>' if unit else ""
    return f'<div class="db-odo" role="img" aria-label="{esc(label)} {esc(v)} {esc(unit)}">{lab}{cells}{uni}</div>'


def stock():
    """(ready, reserved, Thai date or "") from the bike files and inventory_summary.md."""
    files = list(DATA.glob("bike_*.md"))
    reserved = sum("สถานะ: ติดจอง" in f.read_text(encoding="utf-8") for f in files)
    try:
        m = re.search(r"ข้อมูล ณ วันที่:\s*(\d{4})-(\d{2})-(\d{2})",
                      (DATA / "inventory_summary.md").read_text(encoding="utf-8"))
    except OSError:
        m = None
    date = ""
    if m:
        y, mo, d = map(int, m.groups())
        date = f"{d} {TH_MONTHS[mo - 1]} {y + 543}"
    return len(files) - reserved, reserved, date


def hero_html():
    ready, reserved, date = stock()
    meters = "".join(
        f'<div>{odometer(f"{n:03d}", label="", unit="")}<p class="db-meter__label">{label}</p></div>'
        for n, label in ((ready, "คันพร้อมขาย"), (reserved, "คันติดจอง")) if n or label == "คันพร้อมขาย"
    )
    when = f'<p class="db-hero__date">อัปเดตสต็อก {esc(date)}</p>' if date else ""
    return (
        '<div class="db-hero"><div><h1 class="db-hero__name">ไมล์แท้ บิ๊กไบค์</h1>'
        '<p class="db-hero__tag">คุยกับพี่ไมล์ได้ทุกเรื่องของรถในโชว์รูม</p></div>'
        f'<div class="db-hero__meters">{meters}</div>{when}</div>'
    )


def bike_card(s, compact=False):
    meta = s.get("meta") or {}
    title = s.get("title") or meta.get("ชื่อรุ่น") or s.get("source", "")
    img = next((u for u in s.get("images") or [] if is_http(u)), None)
    price = field(meta, "ราคาขาย (บาท)")
    tag = f'<p class="db-tag">{esc(price)} <small>บาท</small></p>' if price else ""
    status = field(meta, "สถานะ")
    badge = f'<span class="db-card__status">{esc(status)}</span>' if status and status != "พร้อมขาย" else ""
    out = ['<div class="db-card">']
    if img:
        out.append(f'<div class="db-card__media"><img class="db-card__img" src="{esc(thumb(img))}" '
                   f'alt="รูปรถ {esc(title)}" loading="lazy">{badge}{tag}</div>')
        tag = badge = ""
    out.append(f'<div class="db-card__body">{badge}{tag}<p class="db-card__title">{esc(title)}</p>')
    if not compact and (net := field(meta, "ราคาหลังหักส่วนลด (บาท)")):
        out.append(f'<p class="db-card__note">ราคาหลังหักส่วนลด {esc(net)} บาท</p>')
    if odo := field(meta, "เลขไมล์ (กม.)"):
        out.append(odometer(odo))
    if not compact:
        bits = [f"สี{field(meta, 'สี')}" if field(meta, "สี") else "",
                f"เกรดสภาพ {field(meta, 'เกรดสภาพ')}" if field(meta, "เกรดสภาพ") else "",
                f"รหัส {field(meta, 'รหัสสต็อก')}" if field(meta, "รหัสสต็อก") else ""]
        if look := " ".join(b for b in bits if b):
            out.append(f'<p class="db-card__note">{esc(look)}</p>')
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


def doc_name(src, sources):
    """Readable name for a cited file; bikes get their stock id since one model can have several units."""
    s = next((s for s in sources if s.get("source") == src), {})
    title = (s.get("title") or "").lstrip("# ").strip() or Path(src).stem
    sid = field(s.get("meta") or {}, "รหัสสต็อก")
    return f"{sid} {title}" if sid else title


CITE = re.compile(r"\[([^\[\]]*?\.md(?:\s*,\s*[^\[\]]*?\.md)*)\]")


def with_chips(text, sources):
    """Escape the LLM text (it is rendered with unsafe_allow_html) and turn [file.md, …] into name chips.
    Each file gets one chip, at its first citation; the model often repeats a citation on every bullet."""
    seen = set()

    def chips(m):
        files = [f.strip() for f in m.group(1).split(",")]
        new = [f for f in files if f not in seen]
        seen.update(new)
        return "".join(f'<span class="db-cite" title="{esc(f)}">{esc(doc_name(f, sources))}</span>' for f in new)
    return CITE.sub(chips, html.escape(text, quote=False))


def sources_html(sources):
    if not sources:
        return '<p class="db-muted">ไม่มีเอกสารที่เกี่ยวข้องกับคำถามนี้</p>'
    rows = []
    for s in sources:
        score = float(s.get("score", 0))
        pct = max(0, min(100, round((score - 0.7) / 0.25 * 100)))  # e5 cosine scores live in ~0.7–0.95
        heading = f", หัวข้อ {esc(s['heading'])}" if s.get("heading") else ""
        rows.append(
            f'<div class="db-src"><div class="db-src__head"><span class="db-src__title">'
            f'{esc(doc_name(s.get("source", ""), sources))}</span><span class="db-src__score">'
            f'<span class="db-src__bar"><i style="width:{pct}%"></i></span>{score:.2f}</span></div>'
            f'<p class="db-src__file">{esc(s.get("source", ""))}{heading}</p>'
            f'<p class="db-src__text">{esc(s.get("text", ""))}</p></div>'
        )
    return "".join(rows)


def show_answer(i, m):
    text, sources = m["content"], m.get("sources") or []
    if m.get("error"):
        st.error(text)
    elif text.startswith(NOT_FOUND):  # rag's prompt: a full refusal starts with NOT_FOUND
        with st.container(key=f"nf_{i}"):
            st.markdown(with_chips(text, sources), unsafe_allow_html=True)
        st.html(HINT)
    else:
        st.markdown(with_chips(text, sources), unsafe_allow_html=True)
        if cards := cited_bikes(text, sources):
            st.html('<div class="db-cards">' + "".join(map(bike_card, cards)) + "</div>")
        if NOT_FOUND in text:  # partial answer: point to the shop for the missing part
            st.html(HINT)
    with st.expander(f"เอกสารอ้างอิง ({len(sources)})", icon=":material/description:"):
        st.html(sources_html(sources))


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


def ask_about(q):
    st.session_state.pending = q


@st.cache_data
def showroom_bikes(n=6):
    """Newest ready-to-sell bike per riding style, for the empty-state showroom."""
    try:
        with (DATA / "bikes.csv").open(encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("status") == "พร้อมขาย"]
        rows.sort(key=lambda r: (-int(r["year"]), r["stock_id"]))
    except (OSError, KeyError, ValueError):
        return []
    picked, styles = [], set()
    for r in rows:
        if r["style"] not in styles:
            styles.add(r["style"])
            picked.append(r)
    return picked[:n]


def showroom():
    bikes = showroom_bikes()
    if not bikes:
        return
    st.html('<p class="db-section">รถเด่นในโชว์รูม</p><p class="db-muted">กดที่คันไหนก็ได้ พี่ไมล์จะเล่ารายละเอียดให้ฟัง</p>')
    cols = st.columns(3)
    for i, r in enumerate(bikes):
        name = f'{r["brand"]} {r["model"]} ปี {r["year"]}'
        with cols[i % 3]:
            st.html(bike_card({
                "title": name,
                "images": r["images"].split("|"),
                "meta": {"ราคาขาย (บาท)": f'{int(r["price"]):,}', "เลขไมล์ (กม.)": f'{int(r["mileage_km"]):,}'},
            }, compact=True))
            st.button("ถามเรื่องคันนี้", key=f"show_{r['stock_id']}", on_click=ask_about,
                      args=(f"ขอรายละเอียด {name} หน่อยครับ",), width="stretch")


@st.cache_resource(show_spinner="กำลังเตรียมข้อมูลรถในร้าน ครั้งแรกอาจใช้เวลาประมาณ 1 นาที")
def load_store():
    return build_index(str(DATA))


st.set_page_config(page_title="พี่ไมล์ ผู้ช่วยเลือกบิ๊กไบค์", page_icon=BOT, layout="centered")
st.html(CSS)
st.session_state.setdefault("messages", [])

with st.sidebar:
    st.header("ไมล์แท้ บิ๊กไบค์", anchor=False)
    st.html(SIDEBAR)
    st.button("ล้างแชต", on_click=st.session_state.messages.clear, width="stretch", icon=":material/refresh:")

st.html(hero_html())

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

# read the question first (chat_input is pinned to the bottom wherever it is called),
# so the showroom disappears in the same run as the first question
question = st.chat_input("พิมพ์คำถาม เช่น MT-09 ราคาเท่าไร") or st.session_state.pop("pending", None)
if not st.session_state.messages and not question:
    showroom()

for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"], avatar=BOT if m["role"] == "assistant" else USER):
        if m["role"] == "user":
            with st.container(key=f"umsg_{i}"):
                st.markdown(m["content"])
        else:
            show_answer(i, m)

if question:
    history = chat_history()
    msgs = st.session_state.messages
    msgs.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=USER):
        with st.container(key=f"umsg_{len(msgs) - 1}"):
            st.markdown(question)
    with st.chat_message("assistant", avatar=BOT):
        with st.spinner("กำลังหาข้อมูลให้ครับ"):
            msg = ask(store, question, history, api_key)
        msgs.append(msg)
        show_answer(len(msgs) - 1, msg)
