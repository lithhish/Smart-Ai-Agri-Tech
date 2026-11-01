"""
agriculture_tasks.py - Daily Activity & Farm Task Logbook Engine.
Enables farmers to log, track, and manage field operations:
- Irrigation events, fertilizer applications, pest scouting, spraying, weeding, harvesting, labor & expenses.
- Persistent SQLite storage in farm_data.db.
"""

import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DB_PATH = "farm_data.db"

ACTIVITY_TYPES = {
    "irrigation": {"label": "💧 Irrigation", "badge": "badge-irrigation", "icon": "💧"},
    "fertilizer": {"label": "🧪 Fertilizer / Nutrients", "badge": "badge-patta", "icon": "🧪"},
    "spraying": {"label": "🌿 Pest / Disease Spray", "badge": "badge-disease", "icon": "🌿"},
    "weeding": {"label": "🌱 Weeding & Cultivation", "badge": "badge-crop", "icon": "🌱"},
    "sowing": {"label": "🌾 Sowing / Transplanting", "badge": "badge-fmb", "icon": "🌾"},
    "harvest": {"label": "🧺 Harvesting", "badge": "badge-water", "icon": "🧺"},
    "scouting": {"label": "🔍 Field Inspection", "badge": "badge-eb", "icon": "🔍"},
    "labor": {"label": "👥 Labor & Operations", "badge": "badge-tax", "icon": "👥"},
    "other": {"label": "📝 General Task", "badge": "badge-other", "icon": "📝"}
}


def init_tasks_db():
    """Ensure farm_tasks table exists and seed sample records if empty."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farm_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_date TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'medium',
                cost_inr REAL DEFAULT 0.0,
                revenue_inr REAL DEFAULT 0.0,
                benefit_notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.row_factory = sqlite3.Row
        # Migrate existing tables if revenue_inr / benefit_notes are missing
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(farm_tasks)").fetchall()]
        if "revenue_inr" not in existing_cols:
            conn.execute("ALTER TABLE farm_tasks ADD COLUMN revenue_inr REAL DEFAULT 0.0")
        if "benefit_notes" not in existing_cols:
            conn.execute("ALTER TABLE farm_tasks ADD COLUMN benefit_notes TEXT DEFAULT ''")
        cnt = conn.execute("SELECT COUNT(*) as count FROM farm_tasks").fetchone()["count"]
        if cnt == 0:
            seed_sample_tasks(conn)


def seed_sample_tasks(conn):
    """Seed realistic initial field tasks for farmer."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    sample_tasks = [
        (
            today_str,
            "irrigation",
            "Root-Zone Soil Moisture Check & Drip Flush",
            "Observed moisture at 42.5%. Inspect sub-surface drip lateral lines in North survey plot 142/3A.",
            "completed",
            "high",
            150.0,
            now_str
        ),
        (
            today_str,
            "scouting",
            "Early Blight & Rust Scouting on Lower Canopy",
            "Inspect foliage due to high humidity alert (>85%). Check underside of leaves for early chlorosis.",
            "pending",
            "high",
            0.0,
            now_str
        ),
        (
            today_str,
            "fertilizer",
            "Neem-Coated Urea & Bio-Potash Top Dressing",
            "Apply 25 kg/acre split dose after morning dew clears. Coordinate with soil moisture status.",
            "pending",
            "medium",
            1450.0,
            now_str
        ),
        (
            today_str,
            "labor",
            "Canal Bund Weeding & Ridge Maintenance",
            "Engaged 2 farm hands for south canal embankment clearing to ensure proper monsoon drainage.",
            "completed",
            "medium",
            900.0,
            now_str
        ),
        (
            today_str,
            "spraying",
            "Preventive Cold-Pressed Neem Oil Spray (5 ml/L)",
            "Eco-friendly biological spray on border crop rows to deter whitefly and sucking pests.",
            "pending",
            "medium",
            420.0,
            now_str
        )
    ]

    conn.executemany("""
        INSERT INTO farm_tasks (
            task_date, activity_type, title, description, status, priority, cost_inr, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_tasks)


def get_tasks(status: Optional[str] = None, activity: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve farm tasks with optional filtering."""
    init_tasks_db()
    query = "SELECT * FROM farm_tasks WHERE 1=1"
    params = []

    if status and status != "all":
        query += " AND status = ?"
        params.append(status)

    if activity and activity in ACTIVITY_TYPES and activity != "all":
        query += " AND activity_type = ?"
        params.append(activity)

    query += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id DESC"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    result = []
    for r in rows:
        item = dict(r)
        act = ACTIVITY_TYPES.get(item["activity_type"], ACTIVITY_TYPES["other"])
        item["activity_label"] = act["label"]
        item["activity_badge"] = act["badge"]
        item["activity_icon"] = act["icon"]
        result.append(item)
    return result


def create_task(task_date: str, activity_type: str, title: str, description: str = "",
                priority: str = "medium", cost_inr: float = 0.0,
                revenue_inr: float = 0.0, benefit_notes: str = "") -> Dict[str, Any]:
    """Create a new farm task / daily field activity."""
    init_tasks_db()
    if not title or not title.strip():
        raise ValueError("Task title is required.")

    act_clean = activity_type if activity_type in ACTIVITY_TYPES else "other"
    date_clean = task_date.strip() if task_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO farm_tasks (
                task_date, activity_type, title, description, status, priority, cost_inr, revenue_inr, benefit_notes, created_at
            ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
        """, (date_clean, act_clean, title.strip(), description.strip(), priority, float(cost_inr or 0.0), float(revenue_inr or 0.0), benefit_notes.strip(), now_str))
        new_id = cur.lastrowid

    return {
        "id": new_id,
        "task_date": date_clean,
        "activity_type": act_clean,
        "title": title.strip(),
        "status": "pending",
        "priority": priority,
        "cost_inr": cost_inr,
        "created_at": now_str
    }


def update_task_status(task_id: int, status: str) -> bool:
    """Update task completion status ('pending', 'completed', 'in_progress')."""
    init_tasks_db()
    if status not in ("pending", "in_progress", "completed"):
        return False
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE farm_tasks SET status = ? WHERE id = ?", (status, task_id))
        return cur.rowcount > 0


def delete_task(task_id: int) -> bool:
    """Delete a farm task."""
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM farm_tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0


def get_financial_summary() -> Dict[str, Any]:
    """Calculate total farm operational costs, total revenue/yield sales, and net farmer benefit."""
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_tasks,
                COALESCE(SUM(cost_inr), 0.0) as total_expense_inr,
                COALESCE(SUM(revenue_inr), 0.0) as total_revenue_inr
            FROM farm_tasks
        """).fetchone()

        total_expense = float(row["total_expense_inr"] or 0.0)
        total_revenue = float(row["total_revenue_inr"] or 0.0)
        net_profit = round(total_revenue - total_expense, 2)

        return {
            "total_tasks": int(row["total_tasks"] or 0),
            "completed_tasks": int(row["completed_tasks"] or 0),
            "pending_tasks": int(row["pending_tasks"] or 0),
            "total_expense_inr": total_expense,
            "total_revenue_inr": total_revenue,
            "net_profit_inr": net_profit,
            "roi_pct": round((net_profit / total_expense * 100), 1) if total_expense > 0 else 0.0
        }
