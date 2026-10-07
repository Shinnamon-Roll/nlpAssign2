"""Scrape ready-to-sell bikes + shop info from https://www.dbigbike.com/ into scraped/*.md (raw input for make_data.py).

Stdlib only. Re-runnable: rewrites scraped/bike_*.md, inventory_summary.md, shop_*.md, article_*.md.
Usage: python3 scrape.py          (scrape)
       python3 scrape.py --test   (parser self-check, no network)
"""
import datetime
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.dbigbike.com"
READY = "/category/2720/บิ๊กไบค์พร้อมขาย"
DATA = Path(__file__).parent / "scraped"  # raw dbigbike text, gitignored; data/ is built by make_data.py
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
# python.org builds on macOS ship without CA certs; use the system bundle when present.
CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if os.path.exists("/etc/ssl/cert.pem") else None
# Customer-relevant articles from /categorycontent/2300 (care, tyres, oil, E-Clutch, an in-stock model).
ARTICLES = [6960, 7312, 7315, 7212, 6947, 6959, 6971, 7402, 7403, 7122]
# /purchasingdepartment is a single image with no HTML text; transcribed verbatim from it.
BUY_IMAGE = "https://image.makewebcdn.com/makeweb/m_1920x0/GKsm2kwBS/APromotion/Promotion.jpg"
BUY_IMAGE_TEXT = """ดีเจริญยนต์ รับซื้อ BIGBIKE ทั่วประเทศ
รับซื้อ BIGBIKE ทั่วไทย พร้อมปิดหนี้ไฟแนนซ์ ปิดภาระให้คุณทันที
เช็คราคาเบื้องต้น โดยการส่งรูปและรายละเอียดของรถที่อยากขาย
มาที่ LINE OFFICIAL ID @dbigbike
โทรด่วน 066-160-1119
ต้องการความเร่งด่วน สามารถขี่มาที่หน้าร้านได้เลย
พิมพ์คำว่า Dbigbike ที่ Google Maps
National Bigbike Purchase Service
Best price offered , instand payment , Home pickup service , buy-sell-trade option , Available for all major bike models Send photographs , documentation and bike information to obtain a fast pricing quote."""


def get(path):
    """GET a site path (or absolute URL); 1 s politeness delay; None on HTTP error."""
    url = path if path.startswith("http") else BASE + urllib.parse.quote(path)
    time.sleep(1)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"  skip {path}: HTTP {e.code}")
        return None


def to_lines(fragment):
    t = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", fragment, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ")
    return [re.sub(r"\s+", " ", l).strip() for l in t.split("\n") if l.strip()]


def page_body(h):
    """Main text of a MakeWebEasy page: after the nav menu, before the 'Page-->' sidebar."""
    ls = to_lines(h)
    start = max([i for i, l in enumerate(ls) if l in ("EN", "เพิ่มเติม", "หมวกกันน็อคยี่ห้อ KYT")] + [-1]) + 1
    end = next((i for i, l in enumerate(ls) if l.startswith("Page-->")), len(ls))
    return [l for l in ls[start:end] if l not in ("-->",)]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def money(n):
    return f"{int(float(n)):,}"


def kv(line):
    """'•ขนาด : 889 ซีซี' -> ('ขนาด', '889 ซีซี')"""
    k, _, v = line.lstrip("•").partition(":")
    return k.strip(), v.strip()


def parse_listing(lines):
    """Split the tab-description lines of one product into fields + sections."""
    f = {"spec": [], "finance": [], "desc": []}
    head = lines[0]
    if m := re.search(r"(?<!ทะเบียน)ปี\s*(\d{4})", head):
        f["year"] = m.group(1)
    if m := re.search(r"จดทะเบียน\s*ปี\s*(\d{4})", head):
        f["reg_year"] = m.group(1)
    if m := re.search(r"ไมล์\s*([\dxX,]+)", head):
        f["mileage"] = m.group(1).rstrip(",")
    f["headline"] = head
    stage = "spec"
    for l in lines[1:]:
        if m := re.match(r"(?:รถ)?ราคา\s*:?\s*([\dxX,]*\d|[xX,]{3,})\s*(?:บาท)?\s*(.*)", l):
            # masked prices exist, e.g. "ราคา xxx,xxx บาท (ราคาพิเศษสอบถามเซลล์ได้เลย)"
            f["price"], stage = " ".join(filter(None, m.groups())), "after"
        elif m := re.match(r"ส่[วง]นลด\s*:?\s*([\d,]+)", l):  # site has a 'ส่งนลด' typo
            f["discount"], stage = m.group(1), "after"
        elif m := re.match(r"สถานะปัจจุบัน\s*:\s*(.+)", l):
            f["status"], stage = m.group(1).strip(), "after"
        elif re.fullmatch(r"[-–_\s]+", l):
            continue
        elif re.match(r"สนใจ|เข้ามาชมรถ|Line\s*:|#", l):
            break  # shop boilerplate, plate number, hashtags follow
        elif stage == "spec":
            k, v = kv(l)
            f["spec"].append((k, v))
            if k == "ขนาด" and (m := re.search(r"([\d,.]+)\s*ซีซี", v)):
                f["cc"] = m.group(1)
            if k == "สไตล์รถ":
                f["style"] = v
        elif re.match(r"ราคาหลังหักส่วนลด|ดาวน์|ผ่อน|ค่าใช้จ่ายออกรถ", l):
            f["finance"].append(l)
        else:
            f["desc"].append(l)
    return f


def parse_product(h, url):
    ld = None
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try:
            d = json.loads(block, strict=False)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            ld = d
            break
    m = re.search(r'<div class="tab-description[^>]*>(.*?)<!-- ', h, re.S)
    if not ld or not m:
        return None
    f = parse_listing(to_lines(m.group(1)))
    title = re.sub(r"\s+", " ", html.unescape(ld["name"]).replace("\xa0", " ")).strip()
    cat = ld.get("category", "").split("/")
    f.update(title=title, url=url, category=cat[0], brand=cat[1].strip() if len(cat) > 1 else title.split()[0])
    imgs = ld.get("image") or []
    f["images"] = ([imgs] if isinstance(imgs, str) else imgs)[:3]
    offer = (ld.get("offers") or {}).get("price")
    if offer and f.get("discount"):
        f["net_price"] = money(offer)
        p, d = (int(f[k].replace(",", "")) for k in ("price", "discount"))
        if int(float(offer)) != p - d:
            print(f"  warn {title}: site net price {offer} != {p}-{d}")
    return f


def bike_md(f):
    rows = [
        ("ชื่อรุ่น", f["title"]), ("ยี่ห้อ", f["brand"]), ("ปี", f.get("year")),
        ("ปีจดทะเบียน", f.get("reg_year")), ("ราคาขาย (บาท)", f.get("price")),
        ("ส่วนลด (บาท)", f.get("discount")), ("ราคาหลังหักส่วนลด (บาท)", f.get("net_price")),
        ("เลขไมล์ (กม.)", f.get("mileage")), ("ขนาดเครื่องยนต์ (cc)", f.get("cc")),
        ("สไตล์รถ", f.get("style")), ("สถานะ", f.get("status")), ("ลิงก์ประกาศ", f["url"]),
        ("รูปภาพ", ", ".join(f["images"]) or None),
    ]
    out = [f"# {f['title']} ปี {f.get('year', '-')}", ""]
    out += [f"{k}: {v}" for k, v in rows if v]
    out += ["", "## สเปค", f"- {f['headline']}"]
    out += [f"- {k}: {v}" if v else f"- {k}" for k, v in f["spec"]]
    if f["finance"]:
        out += ["", "## ไฟแนนซ์ (ตามประกาศ)"] + [f"- {l}" for l in f["finance"]]
    out += ["", "## รายละเอียด/สภาพรถ"] + [f"- {l}" for l in f["desc"]]
    return "\n".join(out) + "\n"


def write(name, text):
    (DATA / name).write_text(text, encoding="utf-8")
    print(f"  wrote scraped/{name} ({len(text)} chars)")


def scrape_bikes(today):
    links = []
    for page in (READY, "/"):
        h = get(page) or ""
        links += re.findall(r'href="(?:https://www\.dbigbike\.com)?(/product/[^"]+)"', h)
    links = list(dict.fromkeys(links))
    print(f"{len(links)} product links")
    bikes, boilerplate = [], []
    for path in links:
        h = get(path)
        f = h and parse_product(h, BASE + path)
        # some listings write the status in English ("For Sale"); sold/reserved bikes are excluded
        if not f or f.get("status") not in ("พร้อมขาย", "For Sale") or f["category"] != "บิ๊กไบค์พร้อมขาย":
            if h:
                print(f"  skip {path}: status={f and f.get('status')}")
            continue
        bikes.append(f)
        if not boilerplate:  # shop lines repeated under every listing -> shop_contact.md
            ls = to_lines(re.search(r'<div class="tab-description[^>]*>(.*?)<!-- ', h, re.S).group(1))
            i = next(i for i, l in enumerate(ls) if l.startswith("สนใจ"))
            j = next(j for j, l in enumerate(ls) if l.startswith("ค้นหาใน Google Map"))
            boilerplate = [l for l in ls[i:j + 1] if not re.fullmatch(r"[-\s]+", l)]
    for old in DATA.glob("bike_*.md"):
        old.unlink()
    rows = []
    for n, f in enumerate(bikes, 1):
        model = slug(f["title"]).removeprefix(slug(f["brand"]) + "-") or slug(f["title"])
        f["file"] = f"bike_{n:02d}_{slug(f['brand'])}_{model}_{f.get('year', 'na')}.md"
        write(f["file"], bike_md(f))
        rows.append(f"| {f['title']} | {f['brand']} | {f.get('year', '-')} | {f.get('price', '-')} | "
                    f"{f.get('discount', '-')} | {f.get('net_price', f.get('price', '-'))} | {f.get('mileage', '-')} | "
                    f"{f.get('cc', '-')} | {f.get('style', '-')} | {f['file']} |")
    write("inventory_summary.md", "\n".join([
        "# สรุปรถพร้อมขาย", "",
        f"ข้อมูล ณ วันที่: {today}",
        f"แหล่งข้อมูล: {BASE}{READY} (เฉพาะรถที่หน้าประกาศระบุ สถานะปัจจุบัน : พร้อมขาย หรือ For Sale)",
        f"จำนวนรถพร้อมขาย: {len(bikes)} คัน",
        "หมายเหตุ: ราคาหลังหักส่วนลด นำมาจากราคาที่เว็บไซต์แสดง; คันที่ไม่มีส่วนลดแสดงราคาขายเดิม",
        "",
        "| รุ่น | ยี่ห้อ | ปี | ราคา (บาท) | ส่วนลด (บาท) | ราคาหลังหักส่วนลด (บาท) | เลขไมล์ (กม.) | cc | สไตล์ | ไฟล์ |",
        "|---|---|---|---|---|---|---|---|---|---|",
        *rows,
    ]) + "\n")
    return bikes, boilerplate


def scrape_shop(bikes, boilerplate):
    home = get("/") or ""
    footer = list(dict.fromkeys(l for l in to_lines(home) if re.search(r"ซื้อ ขาย", l) and "DBigbike" in l))
    social = sorted(set(re.findall(r'https?://(?:www\.)?(?:facebook\.com/dbigbike|youtube\.com/c/dbigbike|line\.me/ti/p/~@dbigbike)', home)))
    junk = re.compile(r"Do not close|ข้อความของคุณ|\*$|กรุณากรอก|ฉันรับทราบ|ส่งข้อความ")
    contact = [l for l in page_body(get("/contactus") or "") if not junk.search(l)]
    shopmap = page_body(get("/map") or "")

    def split_buy(ls):  # purchasing-department block vs sales block
        i = next((i for i, l in enumerate(ls) if l.startswith("ติดต่อเพื่อขายรถให้ร้าน")), len(ls))
        j = next((j for j in range(i + 1, len(ls)) if ls[j].startswith("ติดต่อแผนกเซล")), len(ls))
        return ls[:i] + ls[j:], ls[i:j]

    contact_sales, contact_buy = split_buy(contact)
    map_sales, map_buy = split_buy(shopmap)
    write("shop_contact.md", "\n".join([
        "# ติดต่อร้าน ที่ตั้ง และเวลาเปิด-ปิด: ดีเจริญยนต์ (DBigbike)", "",
        f"เว็บไซต์: {BASE}/",
        *[f"ช่องทางออนไลน์: {u}" for u in social], "",
        f"## หน้าติดต่อเรา ({BASE}/contactus)", *contact_sales, "",
        f"## หน้าแผนที่ร้าน ({BASE}/map)", *map_sales, "",
        "## ข้อความประจำท้ายประกาศขายรถทุกคัน (ติดต่อ เวลาเปิด-ปิด ที่ตั้ง)", *boilerplate,
    ]) + "\n")
    write("shop_buy_bike.md", "\n".join([
        "# รับซื้อบิ๊กไบค์ (ขายรถให้ร้าน ดีเจริญยนต์ DBigbike)", "",
        f"## หน้ารับซื้อบิ๊กไบค์ ({BASE}/purchasingdepartment)",
        f"ถอดข้อความจากภาพประกาศในหน้าเว็บ: {BUY_IMAGE}", *BUY_IMAGE_TEXT.split("\n"), "",
        f"## ฝ่ายจัดซื้อ จากหน้าติดต่อเรา ({BASE}/contactus)", *contact_buy, "",
        f"## ฝ่ายจัดซื้อ จากหน้าแผนที่ร้าน ({BASE}/map)", *map_buy,
    ]) + "\n")
    # Description lines shared by most listings = the shop's stated standard for every bike.
    counts = {}
    for b in bikes:
        for l in set(b["desc"]):
            counts[l] = counts.get(l, 0) + 1
    common = [f"- {l} (พบใน {c} จาก {len(bikes)} ประกาศ)" for l, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= len(bikes) // 2]
    finance = [f"- {b['title']} ปี {b.get('year', '-')} ({b['file']}): " + " / ".join(b["finance"]) for b in bikes if b["finance"]]
    write("shop_services.md", "\n".join([
        "# บริการของร้าน: ซื้อ ขาย แลกเปลี่ยน จัดไฟแนนซ์ รับประกัน บริการหลังการขาย", "",
        "## ข้อความจากเว็บไซต์", *[f"- {l}" for l in footer], "",
        "## มาตรฐานรถและการรับประกันที่ระบุในประกาศขาย", *common, "",
        "## ตัวอย่างเงื่อนไขผ่อนที่ระบุในประกาศขาย (เฉพาะบางคัน)", *(finance or ["- ไม่มีประกาศที่ระบุ"]), "",
        "## หัวข้อที่เว็บไซต์ไม่ได้ระบุรายละเอียด (ต้องสอบถามร้านโดยตรง)",
        "- ระยะเวลาและเงื่อนไขการรับประกัน (วารันตี): เว็บไซต์ระบุเพียงว่า \"มีประกันวารันตี และService บริการหลังการขาย\"",
        "- อัตราดอกเบี้ยไฟแนนซ์ และเอกสารที่ใช้สมัครไฟแนนซ์",
        "- เงื่อนไขและวิธีประเมินราคาการเทิร์น/แลกเปลี่ยนรถ",
        "- ขั้นตอน เอกสาร และค่าใช้จ่ายในการโอนเล่มทะเบียน",
    ]) + "\n")


def scrape_articles():
    for old in DATA.glob("article_*.md"):
        old.unlink()
    for aid in ARTICLES:
        h = get(f"/content/{aid}/x")
        m = h and re.search(r'class="contentDetail[^"]*"[^>]*>(.*?)<div class="customcontent-navigation', h, re.S)
        if not m:
            print(f"  skip article {aid}")
            continue
        title = html.unescape(re.search(r'<meta property="og:title" content="([^"]*)"', h).group(1)).strip()
        url = re.search(r'<meta property="og:url" content="([^"]*)"', h).group(1)
        body = [l for l in to_lines(m.group(1)) if l != "|" and "จำนวนผู้เข้าชม" not in l and not l.startswith("#")]
        write(f"article_{aid}.md", "\n".join([f"# บทความ: {title}", "", f"ลิงก์บทความ: {url}", "", *body]) + "\n")


def selftest():
    f = parse_listing([
        "Harley-Davidson Sportster S รถปี2024 จดทะเบียนปี2024 เลขไมล์ 8,xxx กิโลเมตร",
        "•เครื่องยนต์ : Revolution Max 1250T", "• ขนาด : 1,252 ซีซี", "โหมดการขับขี่ : Rain , Road",
        "•สไตล์รถ : Cruiser", "ราคา : 439,000 บาท", "ส่งนลด : 10,000 บาท", "สถานะปัจจุบัน : พร้อมขาย",
        "-------------------", "ราคาหลังหักส่วนลด 429,000 บาท", "ดาวน์เริ่มต้น 15%", "-------------------",
        "รถบ้านคัดสภาพ", "สนใจจับจองโทร 066-160-1119", "2กล8694",
    ])
    assert (f["year"], f["reg_year"], f["mileage"]) == ("2024", "2024", "8,xxx"), f
    assert (f["price"], f["discount"], f["status"], f["cc"], f["style"]) == ("439,000", "10,000", "พร้อมขาย", "1,252", "Cruiser"), f
    assert f["finance"] == ["ราคาหลังหักส่วนลด 429,000 บาท", "ดาวน์เริ่มต้น 15%"] and f["desc"] == ["รถบ้านคัดสภาพ"], f
    assert ("โหมดการขับขี่", "Rain , Road") in f["spec"]
    g = parse_listing(["Kawasaki Z400 ปี2019 จดทะเบียนปี2020 ไมล์ 12,xxx", "•ขนาด : 399 ซีซี", "รถราคา 99,000 บาท"])
    assert (g["year"], g["reg_year"], g["mileage"], g["price"]) == ("2019", "2020", "12,xxx", "99,000") and "discount" not in g, g
    x = parse_listing(["Ducati Streetfighter V4 รถปี 2023", "ราคา xxx,xxx บาท (ราคาพิเศษสอบถามเซลล์ได้เลย)", "สถานะปัจจุบัน : พร้อมขาย"])
    assert x["price"] == "xxx,xxx (ราคาพิเศษสอบถามเซลล์ได้เลย)" and x["spec"] == [], x
    assert parse_listing(["a", "ราคาหลังหักส่วนลด 1 บาท"])["spec"] == [("ราคาหลังหักส่วนลด 1 บาท", "")]  # not a price line
    print("selftest ok")


if __name__ == "__main__":
    selftest()
    if "--test" not in sys.argv:
        DATA.mkdir(exist_ok=True)
        bikes, boilerplate = scrape_bikes(datetime.date.today().isoformat())
        scrape_shop(bikes, boilerplate)
        scrape_articles()
        print(f"done: {len(bikes)} bikes")
