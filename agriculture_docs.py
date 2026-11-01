"""
agriculture_docs.py - Farm Records & Irrigation Reports Document Management Engine.
Manages storage, retrieval, preview, and generation of:
- Irrigation telemetry & water usage reports
- Patta / Chitta (Revenue land ownership records)
- TANGEDCO Agricultural Electricity Board (EB) power bills
- Panchayat Land & Property Tax bills
- Land Survey & FMB (Field Measurement Book) sketches
- PWD / WRD Canal & Borewell Water cess bills
- Mandi Crop Procurement sales receipts & fertilizer bills
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import csv
import io

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "farm_documents")
DB_PATH = "farm_data.db"

CATEGORIES = {
    "irrigation_report": {"label": "💧 Irrigation Report", "badge": "badge-irrigation", "icon": "💧"},
    "patta_chitta": {"label": "📜 Patta / Chitta", "badge": "badge-patta", "icon": "📜"},
    "eb_bill": {"label": "⚡ EB Power Bill", "badge": "badge-eb", "icon": "⚡"},
    "tax_bill": {"label": "🏛️ Land Tax Bill", "badge": "badge-tax", "icon": "🏛️"},
    "survey_fmb": {"label": "🗺️ Survey / FMB Sketch", "badge": "badge-fmb", "icon": "🗺️"},
    "water_bill": {"label": "🌊 Water Cess Bill", "badge": "badge-water", "icon": "🌊"},
    "crop_bill": {"label": "🌾 Crop / Mandi Bill", "badge": "badge-crop", "icon": "🌾"},
    "other": {"label": "📁 Other Farm Record", "badge": "badge-other", "icon": "📁"}
}

GOV_PORTALS = [
    {
        "category": "patta_chitta",
        "name": "Tamil Nadu e-Services (Patta / Chitta)",
        "desc": "Official portal to download digital Patta / Chitta extract using Taluk, Village & Survey No.",
        "url": "https://eservices.tn.gov.in/eservicesnew/land/chitta.html?lan=en",
        "guide": "Select District $\\rightarrow$ Taluk $\\rightarrow$ Village $\\rightarrow$ Survey Number / Sub-division $\\rightarrow$ Submit"
    },
    {
        "category": "survey_fmb",
        "name": "TN Land Records FMB Sketch Download",
        "desc": "Official Field Measurement Book (FMB) survey sketch showing agricultural land boundary coordinates.",
        "url": "https://eservices.tn.gov.in/eservicesnew/land/fmb.html?lan=en",
        "guide": "Enter Survey No & Sub-division to download authorized digital FMB boundary map."
    },
    {
        "category": "eb_bill",
        "name": "TANGEDCO Agricultural Power Services",
        "desc": "Check agricultural service connection status, load sanction, meter readings, and tariff receipts.",
        "url": "https://www.tnebnet.org/qwp/qpay",
        "guide": "Enter 10-digit Service Connection Number with Region Code to view/download power receipt."
    },
    {
        "category": "tax_bill",
        "name": "TN Rural Development & Panchayat Tax Portal",
        "desc": "Pay or download agricultural land tax (Kist), Panchayat cess, and village revenue receipts.",
        "url": "https://tnreginet.gov.in/",
        "guide": "Access guideline values, land tax assessment receipts, and encumbrance certificates."
    },
    {
        "category": "water_bill",
        "name": "Water Resources Department (WRD / PWD)",
        "desc": "Canal irrigation passbook, river basin water cess assessment, and micro-irrigation subsidies.",
        "url": "https://wrd.tn.gov.in/",
        "guide": "View ayacut water distribution schedules and canal cess dues."
    },
    {
        "category": "crop_bill",
        "name": "e-NAM & Agmarknet Mandi Portal",
        "desc": "Download electronic auction sale slips, MSP procurement receipts, and weight bridge vouchers.",
        "url": "https://enam.gov.in/",
        "guide": "Login using Farmer Registration ID to download Mandi e-bill and direct bank transfer vouchers."
    }
]


def init_docs_db():
    """Ensure static/farm_documents directory and SQLite table exist."""
    os.makedirs(DOCS_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farm_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                file_size_kb REAL DEFAULT 0,
                uploaded_at TEXT NOT NULL,
                notes TEXT,
                is_generated INTEGER DEFAULT 0
            )
        """)
    seed_default_documents()


def seed_default_documents():
    """Seed standard official samples and generated reports if the vault is empty."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) as cnt FROM farm_documents").fetchone()["cnt"]
        if count > 0:
            return

    # Create sample official templates
    samples = [
        {
            "doc_type": "irrigation_report",
            "title": "IoT Farm Precision Irrigation & Soil Moisture Audit Report (Oct 2026)",
            "filename": "irrigation_audit_report_oct2026.html",
            "notes": "Real-time automated LoRa sensor telemetry audit. 40.0% moisture threshold compliance verified.",
            "is_generated": 1,
            "content": generate_sample_irrigation_report_html()
        },
        {
            "doc_type": "patta_chitta",
            "title": "Tamil Nadu e-Services Patta / Chitta Extract (Survey No. 142/3A)",
            "filename": "sample_patta_chitta_survey_142_3a.html",
            "notes": "Coimbatore Taluk, Perur Village. Total extent: 4.85 Acres. Ownership verified.",
            "is_generated": 1,
            "content": generate_sample_patta_html()
        },
        {
            "doc_type": "eb_bill",
            "title": "TANGEDCO Agricultural Free Power Service Receipt (Conn No. 03-142-008)",
            "filename": "tangedco_eb_bill_conn_03_142.html",
            "notes": "Tariff IV (Agricultural Pump 7.5 HP). Solar-grid sync active. Bill amount: ₹0.00 (Govt Subsidy).",
            "is_generated": 1,
            "content": generate_sample_eb_bill_html()
        },
        {
            "doc_type": "survey_fmb",
            "title": "FMB Field Measurement Survey Sketch (Subdivision 142/3A)",
            "filename": "fmb_survey_sketch_142_3a.html",
            "notes": "Field boundary measurements with GPS benchmarks and irrigation canal frontage.",
            "is_generated": 1,
            "content": generate_sample_fmb_html()
        },
        {
            "doc_type": "crop_bill",
            "title": "Mandi Crop Procurement Sales Slip - Sugarcane / Cotton (Bill #AGM-8492)",
            "filename": "agmarknet_mandi_sales_slip_8492.html",
            "notes": "Coimbatore APMC Mandi. FRP Rate @ ₹335/qtl. Direct bank credit processed.",
            "is_generated": 1,
            "content": generate_sample_crop_bill_html()
        },
        {
            "doc_type": "tax_bill",
            "title": "Panchayat Agricultural Land Tax & Water Kist Receipt (F.Y. 2025-26)",
            "filename": "panchayat_land_tax_receipt_2025_26.html",
            "notes": "Village Panchayat Land Revenue Kist. Assessment Receipt #TR-2026-9041.",
            "is_generated": 1,
            "content": generate_sample_tax_bill_html()
        }
    ]

    for s in samples:
        filepath = os.path.join(DOCS_DIR, s["filename"])
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(s["content"])
        size_kb = round(os.path.getsize(filepath) / 1024.0, 1)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO farm_documents (
                    doc_type, title, filename, filepath, file_size_kb, uploaded_at, notes, is_generated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["doc_type"],
                s["title"],
                s["filename"],
                s["filename"],
                size_kb,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                s["notes"],
                s["is_generated"]
            ))


def get_all_documents(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all stored farm documents with metadata."""
    init_docs_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if category and category in CATEGORIES and category != "all":
            rows = conn.execute(
                "SELECT * FROM farm_documents WHERE doc_type = ? ORDER BY id DESC",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM farm_documents ORDER BY id DESC").fetchall()

    results = []
    for r in rows:
        item = dict(r)
        cat_info = CATEGORIES.get(item["doc_type"], CATEGORIES["other"])
        item["category_label"] = cat_info["label"]
        item["category_badge"] = cat_info["badge"]
        item["category_icon"] = cat_info["icon"]
        results.append(item)
    return results


def save_uploaded_document(file_obj, doc_type: str, title: str, notes: str = "") -> Dict[str, Any]:
    """Save an uploaded file from user to static/farm_documents and register in DB."""
    init_docs_db()
    if not file_obj or not file_obj.filename:
        raise ValueError("No file provided for upload.")

    orig_name = os.path.basename(file_obj.filename)
    clean_name = "".join(c for c in orig_name if c.isalnum() or c in "._- ").strip()
    if not clean_name:
        clean_name = "uploaded_document.pdf"

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stored_filename = f"{timestamp_str}_{clean_name}"
    target_path = os.path.join(DOCS_DIR, stored_filename)

    file_obj.save(target_path)
    size_kb = round(os.path.getsize(target_path) / 1024.0, 1)
    doc_type_clean = doc_type if doc_type in CATEGORIES else "other"
    doc_title = title.strip() if title and title.strip() else orig_name

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO farm_documents (
                doc_type, title, filename, filepath, file_size_kb, uploaded_at, notes, is_generated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            doc_type_clean,
            doc_title,
            stored_filename,
            stored_filename,
            size_kb,
            now_str,
            notes.strip() if notes else ""
        ))
        new_id = cur.lastrowid

    return {
        "id": new_id,
        "title": doc_title,
        "doc_type": doc_type_clean,
        "filename": stored_filename,
        "size_kb": size_kb,
        "uploaded_at": now_str
    }


def delete_document(doc_id: int) -> bool:
    """Delete a document record and file."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        doc = conn.execute("SELECT * FROM farm_documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            return False

        file_on_disk = os.path.join(DOCS_DIR, doc["filename"])
        if os.path.exists(file_on_disk):
            try:
                os.remove(file_on_disk)
            except Exception:
                pass

        conn.execute("DELETE FROM farm_documents WHERE id = ?", (doc_id,))
    return True


def generate_live_irrigation_report_csv() -> str:
    """Generate a clean CSV report of all stored sensor moisture and irrigation events."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID",
        "Timestamp (UTC)",
        "Root-Zone Soil Moisture (%)",
        "Farm Air Temp (°C)",
        "Farm Humidity (%)",
        "Soil Temp (°C)",
        "Moisture Status",
        "40% Threshold Compliance",
        "Irrigation Action"
    ])

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM sensor_readings ORDER BY id DESC").fetchall()

    for r in rows:
        moisture = r["root_zone_moisture_pct"]
        if moisture is not None:
            status = "Adequate" if moisture >= 40.0 else "Critical - Dry"
            action = "No Irrigation Needed" if moisture >= 40.0 else "IRRIGATION REQUIRED"
            compliance = "Compliant (≥40.0%)" if moisture >= 40.0 else "Below Threshold (<40.0%)"
        else:
            status = "N/A"
            action = "Sensor Telemetry Missing"
            compliance = "N/A"

        writer.writerow([
            r["id"],
            r["received_at"],
            moisture if moisture is not None else "N/A",
            r["farm_air_temp_c"] if r["farm_air_temp_c"] is not None else "N/A",
            r["farm_air_humidity_pct"] if r["farm_air_humidity_pct"] is not None else "N/A",
            r["soil_temp_c"] if r["soil_temp_c"] is not None else "N/A",
            status,
            compliance,
            action
        ])

    return output.getvalue()


# -------------------------------------------------------------
# Document Generators for Official Sample Templates
# -------------------------------------------------------------
def generate_sample_irrigation_report_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Official Irrigation & Soil Moisture Telemetry Report</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 40px; color: #1e293b; background: #fff; }
.header { border-bottom: 2px solid #064e3b; padding-bottom: 16px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: flex-end; }
.logo-title { font-size: 22px; font-weight: 800; color: #064e3b; }
.sub { font-size: 13px; color: #64748b; margin-top: 4px; }
.seal { text-align: right; font-size: 12px; color: #047857; font-weight: 700; }
.meta-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0; }
.meta-item { font-size: 13px; }
.meta-label { color: #64748b; font-size: 11px; text-transform: uppercase; font-weight: 700; margin-bottom: 2px; }
.meta-val { font-weight: 700; color: #0f172a; }
.telemetry-card { background: #ecfdf5; border: 1.5px solid #a7f3d0; border-radius: 10px; padding: 18px; margin-bottom: 24px; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; background: #047857; color: #fff; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #e2e8f0; }
th { background: #f1f5f9; color: #475569; font-weight: 700; }
.footer { margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 14px; font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between; }
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="logo-title">🌱 AI SMART FARMING - PRECISION IRRIGATION AUDIT REPORT</div>
    <div class="sub">Autonomous LoRa Telemetry & 40.0% Moisture Threshold Compliance Verification</div>
  </div>
  <div class="seal">
    <div>OFFICIAL FARM AUDIT</div>
    <div>ISO / ICAR COMPLIANT</div>
  </div>
</div>

<div class="meta-grid">
  <div class="meta-item"><div class="meta-label">Farm Region</div><div class="meta-val">Perur, Coimbatore (11.02°N, 76.96°E)</div></div>
  <div class="meta-item"><div class="meta-label">Survey Extent</div><div class="meta-val">Survey No: 142/3A (4.85 Acres)</div></div>
  <div class="meta-item"><div class="meta-label">Audit Period</div><div class="meta-val">October 2026 Telemetry Cycle</div></div>
</div>

<div class="telemetry-card">
  <span class="badge">✅ THRESHOLD ADHERENCE: ADEQUATE</span>
  <h3 style="margin: 8px 0 4px 0; color: #064e3b;">Root-Zone Moisture: 42.5% (Configured Threshold: 40.0%)</h3>
  <p style="margin: 0; font-size: 13px; color: #047857;">Root-zone moisture (42.5%) strictly exceeds threshold (&ge; 40.0%). Water conservation valve remains safely closed. Zero unneeded power consumption.</p>
</div>

<h3>📡 LoRa On-Field Hardware Telemetry Log</h3>
<table>
  <thead>
    <tr>
      <th>Timestamp</th>
      <th>Root Soil Moisture</th>
      <th>Farm Air Temp</th>
      <th>Humidity</th>
      <th>Soil Temp</th>
      <th>Decision Rule</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>2026-10-15 20:15 UTC</td>
      <td><strong>42.5 %</strong></td>
      <td>24.8 °C</td>
      <td>65.0 %</td>
      <td>23.2 °C</td>
      <td><span style="color:#047857; font-weight:700;">No Irrigation Required</span></td>
    </tr>
    <tr>
      <td>2026-10-15 14:00 UTC</td>
      <td>43.1 %</td>
      <td>27.5 °C</td>
      <td>62.0 %</td>
      <td>24.8 °C</td>
      <td><span style="color:#047857; font-weight:700;">No Irrigation Required</span></td>
    </tr>
    <tr>
      <td>2026-10-15 08:00 UTC</td>
      <td>44.0 %</td>
      <td>22.1 °C</td>
      <td>78.0 %</td>
      <td>21.5 °C</td>
      <td><span style="color:#047857; font-weight:700;">No Irrigation Required</span></td>
    </tr>
  </tbody>
</table>

<div class="footer">
  <div>Certified by Precision Agriculture IoT Controller v2.4</div>
  <div>Signature: Authorized Agronomy Sensor Telemetry Log</div>
</div>
</body>
</html>"""


def generate_sample_patta_html() -> str:
    return """<!DOCTYPE html>
<html lang="ta">
<head>
<meta charset="UTF-8">
<title>Tamil Nadu Government - Patta / Chitta Extract</title>
<style>
body { font-family: "Tamil Sangam MN", -apple-system, sans-serif; margin: 30px; color: #0f172a; line-height: 1.6; }
.banner { text-align: center; border-bottom: 2px solid #854d0e; padding-bottom: 12px; margin-bottom: 20px; }
.emblem { font-size: 28px; }
h2 { margin: 4px 0; color: #713f12; }
.box { border: 1.5px solid #cbd5e1; border-radius: 8px; padding: 16px; margin-bottom: 20px; background: #fffbeb; }
table { width: 100%; border-collapse: collapse; margin-top: 14px; }
th, td { border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; font-size: 13px; }
th { background: #fef08a; color: #713f12; }
.seal { text-align: center; font-size: 12px; color: #15803d; font-weight: 700; margin-top: 20px; }
</style>
</head>
<body>
<div class="banner">
  <div class="emblem">🏛️</div>
  <h2>தமிழ்நாடு அரசு - வருவாய்த்துறை (Government of Tamil Nadu - Revenue Dept)</h2>
  <h3>பட்டா / சிட்டா நகல் (Patta / Chitta Online Extract)</h3>
  <p style="font-size: 12px; color: #64748b;">eservices.tn.gov.in மூலம் பெறப்பட்ட கணினி வழி சான்றிதழ்</p>
</div>

<div class="box">
  <table style="border:none; margin:0;">
    <tr><td><strong>மாவட்டம் (District):</strong> கோயம்புத்தூர் (Coimbatore)</td><td><strong>வட்டம் (Taluk):</strong> பேரூர் (Perur)</td></tr>
    <tr><td><strong>கிராமம் (Village):</strong> தீத்திப்பாளையம் (Theethipalayam)</td><td><strong>பட்டா எண் (Patta No):</strong> 1042</td></tr>
    <tr><td><strong>உரிமையாளர் பெயர் (Owner):</strong> ஆர். சுப்பிரமணியன் (R. Subramanian)</td><td><strong>நில வகைப்பாடு:</strong> நஞ்சை / புஞ்சை (Agricultural)</td></tr>
  </table>
</div>

<h3>புல எண்கள் மற்றும் நிலப்பரப்பு விவரங்கள் (Survey & Area Schedule)</h3>
<table>
  <thead>
    <tr>
      <th>புல எண் (Survey No)</th>
      <th>உட்பிரிவு (Subdivision)</th>
      <th>நில வகை (Land Type)</th>
      <th>பரப்பளவு (Area - Hectare/Acre)</th>
      <th>தீர்வை (Kist Tax - ₹)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>142</td>
      <td>3A</td>
      <td>நஞ்சை (Wetland / Irrigated)</td>
      <td>1.96 Hectare (4.85 Acres)</td>
      <td>₹142.50</td>
    </tr>
  </tbody>
</table>

<div class="seal">
  ✅ தமிழ்நாடு மின்-சேவை சரிபார்க்கப்பட்ட டிஜிட்டல் ஆவணம் (Digitally Verified Tamil Nadu Revenue Document)
</div>
</body>
</html>"""


def generate_sample_eb_bill_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>TANGEDCO Agricultural Electricity Bill</title>
<style>
body { font-family: -apple-system, sans-serif; margin: 30px; color: #0f172a; }
.head { border-bottom: 2px solid #0369a1; padding-bottom: 12px; margin-bottom: 18px; }
.title { font-size: 20px; font-weight: 800; color: #0369a1; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 16px 0; }
th, td { border: 1px solid #e2e8f0; padding: 9px 12px; text-align: left; }
th { background: #e0f2fe; color: #0369a1; }
.subsidy-badge { background: #ecfdf5; border: 1.5px solid #a7f3d0; padding: 12px; border-radius: 8px; font-weight: 700; color: #047857; text-align: center; }
</style>
</head>
<body>
<div class="head">
  <div class="title">⚡ TANGEDCO - TAMIL NADU GENERATION AND DISTRIBUTION CORPORATION</div>
  <div style="font-size: 13px; color: #64748b;">Agricultural Power Service Connection Bill & Telemetry Verification</div>
</div>

<table>
  <tr><td><strong>Service No:</strong> 03-142-008-592</td><td><strong>Region:</strong> Coimbatore West (Section: Perur)</td></tr>
  <tr><td><strong>Consumer Name:</strong> Subramanian R.</td><td><strong>Tariff:</strong> IV (Agricultural Free Power)</td></tr>
  <tr><td><strong>Motor Capacity:</strong> 7.5 HP Submersible Borewell</td><td><strong>Solar Micro-Grid Linked:</strong> Yes (4 kW Rooftop/Field)</td></tr>
</table>

<table>
  <thead>
    <tr>
      <th>Billing Period</th>
      <th>Previous Meter</th>
      <th>Current Meter</th>
      <th>Units Consumed</th>
      <th>Tariff Rate</th>
      <th>Govt Subsidy</th>
      <th>Net Payable</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Aug 2026 - Oct 2026</td>
      <td>14,290 kWh</td>
      <td>15,110 kWh</td>
      <td>820 kWh</td>
      <td>₹4.50 / unit</td>
      <td>-₹3,690.00</td>
      <td><strong style="color:#047857; font-size: 16px;">₹0.00 (PAID IN FULL)</strong></td>
    </tr>
  </tbody>
</table>

<div class="subsidy-badge">
  ✅ 100% FREE AGRICULTURAL POWER APPLIED BY GOVT OF TAMIL NADU
</div>
</body>
</html>"""


def generate_sample_fmb_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Field Measurement Book (FMB) Sketch</title>
<style>
body { font-family: -apple-system, sans-serif; margin: 30px; color: #0f172a; text-align: center; }
.sketch-box { border: 2px dashed #047857; border-radius: 12px; padding: 24px; background: #f0fdf4; margin: 20px auto; max-width: 650px; }
svg { width: 100%; height: 260px; }
</style>
</head>
<body>
<h2>🗺️ FIELD MEASUREMENT BOOK (FMB) SURVEY SKETCH</h2>
<p style="font-size: 13px; color: #64748b;">Survey Subdivision: 142/3A | Village: Perur | District: Coimbatore</p>

<div class="sketch-box">
  <svg viewBox="0 0 500 240">
    <polygon points="50,40 450,40 380,200 80,200" fill="#d1fae5" stroke="#047857" stroke-width="3" />
    <text x="250" y="30" font-size="12" fill="#065f46" font-weight="bold" text-anchor="middle">North Boundary (Canal): 148.5 m</text>
    <text x="250" y="220" font-size="12" fill="#065f46" font-weight="bold" text-anchor="middle">South Boundary (Road): 132.0 m</text>
    <text x="35" y="125" font-size="12" fill="#065f46" font-weight="bold">East: 78.4 m</text>
    <text x="420" y="125" font-size="12" fill="#065f46" font-weight="bold">West: 82.1 m</text>
    <text x="250" y="115" font-size="16" fill="#064e3b" font-weight="bold" text-anchor="middle">Survey No. 142/3A</text>
    <text x="250" y="135" font-size="13" fill="#047857" text-anchor="middle">Extent: 4.85 Acres (Loamy Soil)</text>
    <circle cx="180" cy="150" r="6" fill="#0284c7" />
    <text x="180" y="170" font-size="10" fill="#0369a1" text-anchor="middle">IoT LoRa Sensor Node #1</text>
  </svg>
</div>
<p style="font-size: 12px; color: #64748b;">Survey Dept Benchmark Certified | GPS Coordinates: 11.0214° N, 76.9632° E</p>
</body>
</html>"""


def generate_sample_crop_bill_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>e-NAM / Agmarknet Mandi Crop Sales Slip</title>
<style>
body { font-family: -apple-system, sans-serif; margin: 30px; color: #0f172a; }
.card { border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 20px; max-width: 640px; margin: 0 auto; background: #fff; }
table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }
th, td { padding: 9px 12px; border-bottom: 1px solid #f1f5f9; text-align: left; }
th { background: #f8fafc; color: #475569; }
</style>
</head>
<body>
<div class="card">
  <h2 style="margin: 0; color: #064e3b;">🌾 AGMARKNET & e-NAM CROP PROCUREMENT RECEIPT</h2>
  <p style="font-size: 12px; color: #64748b; margin-top: 4px;">Coimbatore APMC Mandi | Bill No: AGM-2026-8492</p>

  <table>
    <tr><td><strong>Farmer:</strong> Subramanian R.</td><td><strong>Farmer ID:</strong> TN-CBE-2026-4019</td></tr>
    <tr><td><strong>Crop Commodity:</strong> Sugarcane (Co 0238)</td><td><strong>Lot Quality Grade:</strong> Grade A (High Brix)</td></tr>
    <tr><td><strong>Procurement Weight:</strong> 428 Quintals</td><td><strong>Benchmark FRP:</strong> ₹335.00 / quintal</td></tr>
    <tr><td><strong>Gross Settlement:</strong> ₹1,43,380.00</td><td><strong>APMC Cess & Handling:</strong> -₹1,240.00</td></tr>
    <tr><td colspan="2"><strong style="color:#047857; font-size: 16px;">Net Credited to Farmer Account: ₹1,42,140.00 (Direct Bank Transfer)</strong></td></tr>
  </table>
</div>
</body>
</html>"""


def generate_sample_tax_bill_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Panchayat Land Tax Receipt</title>
<style>
body { font-family: -apple-system, sans-serif; margin: 30px; color: #0f172a; }
.card { border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 20px; max-width: 600px; margin: 0 auto; background: #fff; }
</style>
</head>
<body>
<div class="card">
  <h2 style="color:#713f12; margin:0;">🏛️ VILLAGE PANCHAYAT LAND TAX & REVENUE RECEIPT</h2>
  <p style="font-size: 13px; color: #64748b;">Perur Village Panchayat, Coimbatore District | F.Y. 2025-2026</p>
  <hr style="border:none; border-top:1px solid #e2e8f0; margin:16px 0;">
  <p><strong>Receipt Number:</strong> TR-2026-9041</p>
  <p><strong>Pattadar Name:</strong> Subramanian R.</p>
  <p><strong>Assessment:</strong> Survey 142/3A (4.85 Acres Wet Agricultural Land)</p>
  <p><strong>Agricultural Kist Tax:</strong> ₹142.50</p>
  <p><strong>Canal Maintenance Cess:</strong> ₹85.00</p>
  <p style="font-size: 16px; color: #047857; font-weight: bold;">Total Paid: ₹227.50 (Paid Online via e-Challan)</p>
</div>
</body>
</html>"""
