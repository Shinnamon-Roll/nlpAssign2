"""Build the fictional shop's bike documents for the RAG knowledge base (stdlib only).

data/bikes.csv is the master inventory. This script renders data/bike_*.md and data/inventory_summary.md
from it, then checks that all three agree.

Usage: python3 make_data.py                 render + check
       python3 make_data.py --from-scraped  first rebuild bikes.csv from scraped/ (seeded, reproducible)

ไมล์แท้ บิ๊กไบค์ is a fictional demo shop. From the scraped listings we keep only photos and base facts
(brand, model, year, cc, specs, style); price, mileage, colour, grade, owners, accessories, warranty and
status are generated here.
"""
import csv
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CSV = DATA / "bikes.csv"
AS_OF = "2026-10-07"
SEED = 42
RATE_X100 = 299  # 2.99 %/year flat, same as shop_finance.md
EXT_WARRANTY = "4,900"  # +12 months, same as shop_warranty.md
FIELDS = ["stock_id", "brand", "model", "year", "price", "discount", "mileage_km", "cc", "style", "color",
          "condition_grade", "owners", "accessories", "highlights", "warranty_note", "status",
          "engine", "power", "riding_modes", "seat_height", "weight", "images"]
GRADE_TEXT = {
    "A+": "เกรด A+ สภาพใกล้เคียงรถใหม่ ไม่มีรอยล้ม สีและพลาสติกเดิมสวย",
    "A": "เกรด A สภาพดีมาก มีรอยใช้งานเล็กน้อยตามปกติ ไม่มีรอยล้มหนัก",
    "B+": "เกรด B+ สภาพดี มีรอยตามอายุการใช้งาน เครื่องยนต์และช่วงล่างสมบูรณ์",
}
STYLE_TEXT = {
    "Naked": "รถเนคเก็ต ท่านั่งตัวตรง ขี่ในเมืองคล่องตัว ขี่ทางไกลได้สบาย",
    "Sport": "รถสปอร์ต ท่านั่งก้ม เน้นสมรรถนะและการเข้าโค้ง เหมาะกับคนที่มีประสบการณ์",
    "Touring": "รถทัวริ่ง/แอดเวนเจอร์ ท่านั่งสบาย เหมาะกับการเดินทางไกลและบรรทุกสัมภาระ",
    "Cruiser": "รถครุยเซอร์ เบาะต่ำ ขี่สบายแบบชิล ๆ แรงบิดดีตั้งแต่รอบต่ำ",
    "Classic": "รถสไตล์คลาสสิก/เรโทร ดีไซน์ย้อนยุค ขี่ง่าย เหมาะทั้งมือใหม่และสายแต่ง",
    "Scrambler": "รถสแครมเบลอร์ ลุยทางเรียบและทางฝุ่นเบา ๆ ได้ ท่านั่งตัวตรง",
    "Scooter": "บิ๊กสกู๊ตเตอร์ เกียร์ออโต้ มีที่เก็บของใต้เบาะ เหมาะใช้งานในเมืองทุกวัน",
    "Motard": "รถโมตาร์ด ตัวสูง น้ำหนักเบา คล่องตัวมากในเมืองและทางโค้ง",
    "Mini Bike": "มินิไบค์ ตัวเล็ก เบา ขี่ง่าย เหมาะขี่ในเมืองและเป็นรถคันที่สอง",
}


def money(n):
    return f"{int(n):,}"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def installment(net, down_pct, months):
    """(down, financed, monthly) at 2.99 %/year flat; monthly rounded up to the baht."""
    down = net * down_pct // 100
    financed = net - down
    num = financed * 12 * 10000 + financed * RATE_X100 * months  # financed * (1 + r * months/12), scaled by 120000
    return down, financed, -(-num // (months * 12 * 10000))


def bike_file(n, b):
    return f"bike_{n:02d}_{slug(b['brand'])}_{slug(b['model'])}_{b['year']}.md"


# ---------- bikes.csv from scraped listings (one-off, seeded) ----------
MODEL_FIX = {"Streetfighter V4s": "Streetfighter V4 S", "Scrambler 1200XE": "Scrambler 1200 XE", "Xmax": "XMAX 300",
             "Hypermotrad 950 RVE": "Hypermotard 950 RVE", "XSR 900": "XSR900", "Panigale V4s": "Panigale V4 S",
             "S1000RR Tri-Color": "S1000RR", "R 1250GSA HP": "R 1250 GS Adventure HP", "MT09": "MT-09",
             "Scrambler Nightshift 2G": "Scrambler Nightshift", "Dax ST125": "Dax ST125",
             "Street Fighter 1098s CPO (Certified Pre-Owned)": "Streetfighter 1098 S"}
STYLE_FIX = {"Sport Naked": "Naked", "Neked": "Naked", "สปอร์ต": "Sport", "เรโทร คลาสสิค": "Classic",
             "Motard Naked": "Motard", "Sport Heritage": "Classic", "Tracker": "Classic", "": "Naked"}
COLORS = {"Ducati": ["แดง", "แดง", "ดำด้าน", "เทา"], "Honda": ["แดง", "ดำ", "เทา", "ขาว"],
          "Yamaha": ["น้ำเงิน", "ดำ", "เทา"], "Kawasaki": ["เขียว", "ดำ", "เทา"], "Triumph": ["ดำ", "เทา", "ขาว", "แดง"],
          "BMW": ["ขาว", "ดำ", "เทา"], "Harley-Davidson": ["ดำ", "เทาเข้ม"], "Suzuki": ["เงิน", "ดำ"]}
ACC_COMMON = ["กันล้มข้างเครื่อง", "การ์ดแฮนด์", "ฟิล์มกันรอยถังน้ำมัน", "ที่ชาร์จ USB", "กล้องติดรถหน้า-หลัง"]
ACC_STYLE = {
    "Naked": ["ท่อสลิปออน Akrapovic", "ท้ายสั้น", "กระจกปลายแฮนด์", "ชิลด์หน้าสโมค"],
    "Sport": ["ท่อสลิปออน Akrapovic", "ท้ายสั้น", "ชิลด์หน้าทรงสูง", "เบาะเดี่ยวแต่ง"],
    "Touring": ["กล่องข้าง 2 ใบ", "กล่องท้าย", "แคชบาร์", "ไฟสปอร์ตไลท์", "ชิลด์หน้าทรงสูง"],
    "Cruiser": ["พนักพิงหลัง", "ท่อ Vance & Hines", "กระเป๋าข้างหนัง"],
    "Classic": ["เบาะแต่งทรงคาเฟ่", "กระจกปลายแฮนด์", "การ์ดไฟหน้า"],
    "Scrambler": ["การ์ดไฟหน้า", "แร็คท้าย", "ยางวิบากเบา"],
    "Scooter": ["กล่องท้าย", "ชิลด์หน้าทรงสูง", "ที่วางเท้าแต่ง"],
    "Motard": ["การ์ดแฮนด์ทรงวิบาก", "ท่อสลิปออน Termignoni"],
    "Mini Bike": ["แร็คท้าย", "กระจกทรงกลมแต่ง"],
}
TH_MONTH = "มกราคม กุมภาพันธ์ มีนาคม เมษายน พฤษภาคม มิถุนายน กรกฎาคม สิงหาคม กันยายน ตุลาคม พฤศจิกายน ธันวาคม".split()
SHOP_WARRANTY = "รับประกันเครื่องยนต์และระบบส่งกำลังจากร้าน 6 เดือน หรือ 5,000 กม. (แล้วแต่อย่างใดถึงก่อน)"


def read_scraped(path):
    t = path.read_text(encoding="utf-8")
    kv = dict(re.findall(r"^([^:\n#-][^:\n]*): (.+)$", t, re.M))
    spec = dict(re.findall(r"^- ([^:\n]+): (.+)$", t.split("## สเปค")[1].split("\n## ")[0], re.M))
    return kv, spec


def build_csv():
    rng = random.Random(SEED)
    rows = []
    files = sorted((ROOT / "scraped").glob("bike_*.md"))
    assert files, "scraped/bike_*.md not found; run scrape.py first"
    for i, path in enumerate(files, 1):
        kv, spec = read_scraped(path)
        brand = kv["ยี่ห้อ"].replace("Harley Davidson", "Harley-Davidson")
        model = kv["ชื่อรุ่น"]
        model = re.sub(rf"^{re.escape(brand)}\s+", "", model, flags=re.I)
        model = MODEL_FIX.get(model, model)
        year = int(kv["ปี"])
        style = STYLE_FIX.get(kv.get("สไตล์รถ", ""), kv.get("สไตล์รถ", ""))
        base = kv["ราคาขาย (บาท)"].replace(",", "")
        base = int(base) if base.isdigit() else 619000  # one listing hides its price
        price = round(base * (1 + rng.choice([-1, 1]) * rng.uniform(0.05, 0.10)) / 1000) * 1000
        discount = rng.choice([0, 0, 5000, 10000, 10000, 15000, 20000] if price < 300000 else [0, 10000, 20000, 30000, 50000])
        age = max(2026 - year, 0) + rng.uniform(0.3, 0.9)
        per_year = rng.randint(3500, 7000) if style in ("Touring", "Scooter") else rng.randint(2000, 5500)
        mileage = int(age * per_year) + rng.randint(0, 99)
        grade = "A+" if age < 2 and mileage < 8000 else "A" if age < 5 else "B+"
        if rng.random() < 0.15:  # a little noise so grade is not a pure function of age
            grade = {"A+": "A", "A": "A+" if mileage < 12000 else "B+", "B+": "A"}[grade]
        owners = 1 if age < 3 else rng.choice([1, 1, 2])
        color = "ขาว-น้ำเงิน-แดง (ลาย Motorsport)" if "Tri-Color" in kv["ชื่อรุ่น"] else rng.choice(COLORS[brand])
        pool = ACC_STYLE[style] + ACC_COMMON
        acc = rng.sample(pool, rng.randint(1, 3)) if rng.random() > 0.2 else []
        reg_month = rng.randint(1, 12)
        if (year + 2, reg_month) > (2026, 10):  # factory warranty = 2 years from registration
            warranty = f"ยังอยู่ในประกันศูนย์ผู้ผลิตถึง {TH_MONTH[reg_month - 1]} {year + 2} (ใช้ประกันศูนย์ที่เหลือแทนประกันร้าน)"
        else:
            warranty = SHOP_WARRANTY
        hl = [f"เจ้าของเดิม {owners} คน" + (" (มือเดียว)" if owners == 1 else ""),
              rng.choice(["มีสมุดเช็คระยะครบทุกระยะ", "มีประวัติเข้าศูนย์บริการ", "เช็คระยะตามกำหนดสม่ำเสมอ"]),
              f"ยางหน้า-หลังดอกเหลือประมาณ {rng.choice([60, 70, 80, 90])}%",
              rng.choice(["ไม่มีประวัติรถชนหนักหรือจมน้ำ", "โครงรถเดิม ไม่มีรอยเชื่อมหรือดัด", "ระบบไฟและเซ็นเซอร์ทำงานครบ"])]
        if rng.random() < 0.3:
            hl.append(rng.choice(["เปลี่ยนโซ่-สเตอร์ชุดใหม่แล้ว", "เปลี่ยนผ้าเบรกหน้า-หลังใหม่แล้ว", "เปลี่ยนแบตเตอรี่ใหม่แล้ว"]))
        rows.append({
            "stock_id": f"MT{i:03d}", "brand": brand, "model": model, "year": year, "price": price,
            "discount": discount, "mileage_km": mileage, "cc": kv.get("ขนาดเครื่องยนต์ (cc)", "").replace(",", ""),
            "style": style, "color": color, "condition_grade": grade, "owners": owners,
            "accessories": "; ".join(acc), "highlights": "; ".join(hl), "warranty_note": warranty,
            "status": "พร้อมขาย", "engine": spec.get("เครื่องยนต์", ""), "power": spec.get("แรงม้า", ""),
            "riding_modes": spec.get("โหมดการขับขี่", ""), "seat_height": spec.get("ความสูงเบาะนั่ง", ""),
            "weight": spec.get("น้ำหนักรถ", ""), "images": "|".join(kv.get("รูปภาพ", "").split(", ")),
        })
    for r in rng.sample(rows, 3):
        r["status"] = "ติดจอง"
    with CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {CSV.relative_to(ROOT)} ({len(rows)} bikes)")


# ---------- render ----------
def bike_md(b):
    price, discount = int(b["price"]), int(b["discount"])
    net = price - discount
    title = f"{b['brand']} {b['model']}"
    head = [
        ("รหัสสต็อก", b["stock_id"]), ("ชื่อรุ่น", title), ("ยี่ห้อ", b["brand"]), ("ปี", b["year"]),
        ("ราคาขาย (บาท)", money(price)), ("ส่วนลด (บาท)", money(discount) if discount else None),
        ("ราคาหลังหักส่วนลด (บาท)", money(net) if discount else None),
        ("เลขไมล์ (กม.)", money(b["mileage_km"])), ("ขนาดเครื่องยนต์ (cc)", b["cc"]), ("สไตล์รถ", b["style"]),
        ("สี", b["color"]), ("เกรดสภาพ", b["condition_grade"]), ("จำนวนเจ้าของเดิม", b["owners"]),
        ("สถานะ", b["status"]), ("รูปภาพ", ", ".join(u for u in b["images"].split("|") if u)),
    ]
    out = [f"# {title} ปี {b['year']}", ""] + [f"{k}: {v}" for k, v in head if v]
    out += ["", "## สเปค", f"- ขนาดเครื่องยนต์: {b['cc']} ซีซี"]
    out += [f"- {k}: {b[f]}" for k, f in [("เครื่องยนต์", "engine"), ("แรงม้า", "power"), ("โหมดการขับขี่", "riding_modes"),
                                         ("ความสูงเบาะนั่ง", "seat_height"), ("น้ำหนักรถ", "weight")] if b[f]]
    out += [f"- สไตล์รถ: {b['style']} ({STYLE_TEXT[b['style']]})"]
    out += ["", "## สภาพรถ/จุดเด่น", f"- {GRADE_TEXT[b['condition_grade']]}",
            f"- เลขไมล์ {money(b['mileage_km'])} กม. เป็นเลขไมล์แท้ ตรวจสอบย้อนหลังได้",
            *[f"- {h}" for h in b["highlights"].split("; ") if h],
            "- ผ่านการตรวจเช็ค 100 จุดตามมาตรฐานร้าน และเปลี่ยนน้ำมันเครื่องพร้อมไส้กรองก่อนส่งมอบ"]
    if b["status"] == "ติดจอง":
        out.append("- ตอนนี้คันนี้ติดจอง มีลูกค้าวางมัดจำแล้ว หากการจองถูกยกเลิกจะกลับมาเป็นพร้อมขาย")
    acc = [a for a in b["accessories"].split("; ") if a]
    out += ["", "## ของแต่ง"] + ([f"- {a}" for a in acc] or ["- ไม่มีของแต่ง สภาพเดิมจากโรงงาน"])
    out += ["", "## การรับประกันของคันนี้", f"- {b['warranty_note']}",
            "- ไม่ครอบคลุมยาง ผ้าเบรก แบตเตอรี่ อุบัติเหตุ และความเสียหายจากการดัดแปลง",
            f"- ซื้อประกันขยายเพิ่มได้อีก 12 เดือน ราคา {EXT_WARRANTY} บาท"]
    out += ["", "## ตัวอย่างค่างวด",
            f"- คำนวณจากราคา {money(net)} บาท ดอกเบี้ยเริ่มต้น 2.99% ต่อปี (flat rate) ตัวเลขประมาณการ อัตราจริงขึ้นกับผลอนุมัติ"]
    for pct in (10, 20):
        down, financed, _ = installment(net, pct, 48)
        terms = ", ".join(f"{m} งวด งวดละ {money(installment(net, pct, m)[2])} บาท" for m in (36, 48, 60))
        out.append(f"- ดาวน์ {pct}% ({money(down)} บาท) ยอดจัด {money(financed)} บาท: {terms}")
    return "\n".join(out) + "\n"


def render():
    bikes = list(csv.DictReader(CSV.open(encoding="utf-8")))
    for old in DATA.glob("bike_*.md"):
        old.unlink()
    rows = []
    for n, b in enumerate(bikes, 1):
        name = bike_file(n, b)
        (DATA / name).write_text(bike_md(b), encoding="utf-8")
        price, discount = int(b["price"]), int(b["discount"])
        rows.append(f"| {b['stock_id']} | {b['brand']} {b['model']} | {b['year']} | {money(price)} | "
                    f"{money(discount) if discount else '-'} | {money(price - discount)} | {money(b['mileage_km'])} | "
                    f"{b['cc']} | {b['style']} | {b['color']} | {b['status']} | {name} |")
    ready = sum(b["status"] == "พร้อมขาย" for b in bikes)
    (DATA / "inventory_summary.md").write_text("\n".join([
        "# สรุปรถในสต็อก ร้านไมล์แท้ บิ๊กไบค์", "",
        f"ข้อมูล ณ วันที่: {AS_OF}",
        f"จำนวนรถทั้งหมด: {len(bikes)} คัน (พร้อมขาย {ready} คัน, ติดจอง {len(bikes) - ready} คัน)",
        "หมายเหตุ: ราคาหลังหักส่วนลด = ราคาขาย - ส่วนลด; คันที่ไม่มีส่วนลดแสดงราคาขายเดิม; รถติดจองยังไม่สามารถจองซ้ำได้",
        "",
        "| รหัส | รุ่น | ปี | ราคา (บาท) | ส่วนลด (บาท) | ราคาหลังหักส่วนลด (บาท) | เลขไมล์ (กม.) | cc | สไตล์ | สี | สถานะ | ไฟล์ |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
        *rows,
    ]) + "\n", encoding="utf-8")
    print(f"rendered {len(bikes)} bike files + inventory_summary.md")
    return bikes


def check(bikes):
    """bikes.csv == bike_*.md header lines == inventory_summary.md rows."""
    inv = (DATA / "inventory_summary.md").read_text(encoding="utf-8")
    table = [[c.strip() for c in l.strip("|").split("|")] for l in inv.splitlines() if l.endswith(".md |")]
    files = sorted(DATA.glob("bike_*.md"))
    assert len(bikes) == len(files) == len(table), (len(bikes), len(files), len(table))
    for n, (b, row) in enumerate(zip(bikes, table), 1):
        name = bike_file(n, b)
        kv = dict(re.findall(r"^([^:\n#-][^:\n]*): (.+)$", (DATA / name).read_text(encoding="utf-8"), re.M))
        price, discount = int(b["price"]), int(b["discount"])
        assert kv["รหัสสต็อก"] == row[0] == b["stock_id"], name
        assert kv["ราคาขาย (บาท)"] == row[3] == money(price), name
        assert kv.get("ส่วนลด (บาท)", "-") == row[4] == (money(discount) if discount else "-"), name
        assert kv.get("ราคาหลังหักส่วนลด (บาท)", kv["ราคาขาย (บาท)"]) == row[5] == money(price - discount), name
        assert kv["เลขไมล์ (กม.)"] == row[6] == money(b["mileage_km"]), name
        assert kv["ปี"] == row[2] == b["year"] and kv["สี"] == row[9] == b["color"], name
        assert kv["สถานะ"] == row[10] == b["status"] and row[11] == name, name
        assert 1 <= len(kv["รูปภาพ"].split(", ")) <= 3, name
        assert "ลิงก์ประกาศ" not in kv, name
    assert installment(200000, 10, 48) == (20000, 180000, 4199), installment(200000, 10, 48)  # shop_finance.md example
    print(f"check ok: {len(bikes)} bikes consistent across bikes.csv, bike_*.md, inventory_summary.md")


if __name__ == "__main__":
    if "--from-scraped" in sys.argv:
        build_csv()
    check(render())
