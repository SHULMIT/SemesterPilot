from __future__ import annotations

import html
import re
import sqlite3
import smtplib
import threading
import webbrowser
from datetime import date, datetime
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tasks.db"
ENV_PATH = BASE_DIR / ".env"
HOST, PORT = "127.0.0.1", 5000


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            UNIQUE(course_id, number, due_date),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)


def upsert_course(conn: sqlite3.Connection, code: str, name: str) -> int:
    conn.execute(
        "INSERT INTO courses(code,name) VALUES(?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name", (code, name)
    )
    return int(conn.execute("SELECT id FROM courses WHERE code=?", (code,)).fetchone()["id"])


def add_assignment(conn: sqlite3.Connection, course_id: int, number: str, due_date: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO assignments(course_id,number,due_date) VALUES(?,?,?)", (course_id, number, due_date)
    )


def seed_data() -> None:
    data = {
        ("10645", "תכנון, ניתוח ועיצוב מערכות מידע"): [
            ("01", "2026-07-30"),
            ("02", "2026-08-08"),
            ("03", "2026-08-15"),
            ("04", "2026-08-22"),
            ("05", "2026-08-29"),
            ("06", "2026-09-05"),
        ],
        ("20120", "צפונות היקום: אשנב לאסטרונומיה"): [("01", "2026-08-08"), ("02", "2026-08-22"), ("03", "2026-09-12")],
        ("61134", "אנגלית לצרכים אקדמיים: בסיסי"): [
            ("01", "2026-08-09"),
            ("02", "2026-08-16"),
            ("03", "2026-08-23"),
            ("04", "2026-09-01"),
            ("21", "2026-09-10"),
            ("05", "2026-09-14"),
        ],
    }
    with db() as conn:
        for (code, name), tasks in data.items():
            cid = upsert_course(conn, code, name)
            for number, due in tasks:
                add_assignment(conn, cid, number, due)


def setting(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def tasks() -> list[dict]:
    today = date.today()
    with db() as conn:
        rows = conn.execute("""
            SELECT a.id,a.number,a.due_date,a.completed,a.notes,c.code,c.name
            FROM assignments a JOIN courses c ON c.id=a.course_id
            ORDER BY a.completed, a.due_date, c.name
        """).fetchall()
    result = []
    for r in rows:
        due = datetime.strptime(r["due_date"], "%Y-%m-%d").date()
        days = (due - today).days
        urgency = (
            "הושלם"
            if r["completed"]
            else "באיחור"
            if days < 0
            else "דחוף מאוד"
            if days <= 3
            else "השבוע"
            if days <= 7
            else "בקרוב"
            if days <= 14
            else "בהמשך"
        )
        result.append({**dict(r), "due_display": due.strftime("%d/%m/%Y"), "days_left": days, "urgency": urgency})
    return result


def weekly_tasks() -> list[dict]:
    return [t for t in tasks() if not t["completed"] and 0 <= t["days_left"] <= 7]


def parse_ics(text: str) -> list[tuple[str, str, str, str]]:
    found = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        if 'מועד אחרון להגשת ממ"ן' not in block and "מועד אחרון להגשת ממ" not in block:
            continue
        desc_match = re.search(r"DESCRIPTION[^:]*:(.*)", block)
        date_match = re.search(r"DTSTART[^:]*:(\d{8})", block)
        if not desc_match or not date_match:
            continue
        desc = desc_match.group(1)
        m = re.search(r"קורס\s+(.+?)\s*\((\d+)\).*?מטלה\s+(\d+)", desc)
        if m:
            name, code, number = m.groups()
            raw = date_match.group(1)
            found.append((code, name.strip(), number.zfill(2), f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"))
    return found


def import_default_ics() -> int:
    path = BASE_DIR / "open_university_calendar.ics"
    if not path.exists():
        return 0
    events = parse_ics(path.read_text(encoding="utf-8-sig", errors="replace"))
    with db() as conn:
        for code, name, number, due in events:
            cid = upsert_course(conn, code, name)
            add_assignment(conn, cid, number, due)
    return len(events)


def email_body() -> str:
    current = weekly_tasks()
    if not current:
        return "אין מטלות שמועד ההגשה שלהן חל בשבעת הימים הקרובים."
    lines = ["סיכום המטלות לשבוע הקרוב", ""]
    for t in current:
        lines += [
            f"• {t['name']} ({t['code']}) — מטלה {t['number']}",
            f"  מועד אחרון: {t['due_display']} | נשארו {t['days_left']} ימים | {t['urgency']}",
            "",
        ]
    lines.append("כדי לסמן מטלה כבוצעה, פתחי את המערכת ולחצי על ✓.")
    return "\n".join(lines)


def send_weekly_email() -> tuple[bool, str]:
    env = load_env()
    recipient = setting("email_to")
    user, password = env.get("GMAIL_USER", ""), env.get("GMAIL_APP_PASSWORD", "")
    if not recipient or not user or not password:
        return False, "חסרים פרטי Gmail בקובץ .env או כתובת יעד במערכת"
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = "סיכום מטלות שבועי", user, recipient
    msg.set_content(email_body())
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        set_setting("last_email_sent", datetime.now().strftime("%d/%m/%Y %H:%M"))
        return True, "המייל נשלח בהצלחה"
    except Exception as exc:
        return False, f"שליחת המייל נכשלה: {exc}"


CSS = """
body{font-family:Arial,sans-serif;background:#f5f7fb;color:#202124;margin:0}*{box-sizing:border-box}.container{max-width:1050px;margin:auto;padding:28px 18px 60px}header{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:24px}h1{margin:0 0 6px}.badge,.panel{background:#fff;border-radius:18px;box-shadow:0 6px 22px #19284612}.badge{padding:12px 18px;font-weight:bold}.panel{padding:22px;margin-bottom:20px}.task{display:flex;justify-content:space-between;align-items:center;gap:16px;border:1px solid #e6e9ef;padding:16px;border-radius:14px;margin:10px 0}.task-main{display:grid;gap:5px;flex:1}.task small{color:#667085}.done{width:44px;height:44px;border-radius:50%;font-size:24px;background:#e8f5e9}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.stack{display:grid;gap:10px}input,button{font:inherit;padding:10px 12px;border-radius:10px;border:1px solid #d7dce5}button{cursor:pointer}.primary{background:#111827;color:white}.flash{background:#fff8db;padding:12px 16px;border-radius:12px;margin-bottom:16px}.notes{display:flex;gap:8px;margin-top:8px}.completed{opacity:.75}@media(max-width:760px){header{flex-direction:column;align-items:flex-start}.grid{grid-template-columns:1fr}}
"""


def page(message: str = "") -> str:
    all_tasks = tasks()
    weekly = weekly_tasks()
    pending = [t for t in all_tasks if not t["completed"]]
    completed = [t for t in all_tasks if t["completed"]]

    def card(t: dict) -> str:
        notes = html.escape(t["notes"] or "")
        return f'''<div class="task"><div class="task-main"><strong>{html.escape(t["name"])} ({t["code"]})</strong><span>מטלה {t["number"]} · {t["due_display"]}</span><small>{t["urgency"]} · {t["days_left"]} ימים</small><form class="notes" method="post" action="/notes"><input type="hidden" name="id" value="{t["id"]}"><input name="notes" value="{notes}" placeholder="הערה אישית"><button>שמור</button></form></div><form method="post" action="/toggle"><input type="hidden" name="id" value="{t["id"]}"><button class="done">✓</button></form></div>'''

    weekly_html = "".join(card(t) for t in weekly) or "<p>אין מטלות בשבעת הימים הקרובים.</p>"
    pending_html = "".join(card(t) for t in pending) or "<p>כל המטלות הושלמו.</p>"
    completed_html = "".join(
        f'''<div class="task completed"><span>{html.escape(t["name"])} — מטלה {t["number"]}</span><form method="post" action="/toggle"><input type="hidden" name="id" value="{t["id"]}"><button>החזרה לפתוחות</button></form></div>'''
        for t in completed
    )
    flash = f'<div class="flash">{html.escape(message)}</div>' if message else ""
    return f'''<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>מנהל המטלות שלי</title><style>{CSS}</style></head><body><main class="container"><header><div><h1>מנהל המטלות שלי</h1><p>כל הקורסים, תאריכי ההגשה והסימון במקום אחד.</p></div><div class="badge">השבוע: {len(weekly)} מטלות</div></header>{flash}<section class="panel"><h2>מה צריך לעשות השבוע?</h2>{weekly_html}</section><section class="panel"><h2>כל המטלות הפתוחות</h2>{pending_html}</section><section class="grid"><div class="panel"><h2>הוספת מטלה</h2><form class="stack" method="post" action="/add"><input name="course_name" placeholder="שם הקורס" required><input name="course_code" placeholder="מספר הקורס" required><input name="number" placeholder="מספר המטלה" required><input type="date" name="due_date" required><button class="primary">הוספה</button></form></div><div class="panel"><h2>ייבוא הלוח המצורף</h2><p>מייבא מחדש את הקובץ open_university_calendar.ics שבתיקייה.</p><form method="post" action="/import"><button class="primary">ייבוא עכשיו</button></form></div></section><section class="panel"><h2>מייל שבועי</h2><form class="stack" method="post" action="/settings"><input type="email" name="email_to" value="{html.escape(setting("email_to"))}" placeholder="כתובת המייל שלך" required><button class="primary">שמירת כתובת</button></form><form method="post" action="/send"><button>שליחת מייל בדיקה עכשיו</button></form><small>שליחה אחרונה: {html.escape(setting("last_email_sent", "טרם נשלח"))}</small></section>{f'<section class="panel"><h2>מטלות שהושלמו</h2>{completed_html}</section>' if completed else ""}</main></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_html(self, content: str, status: int = 200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, message: str = ""):
        target = "/" + (("?message=" + message.replace(" ", "+")) if message else "")
        self.send_response(303)
        self.send_header("Location", target)
        self.end_headers()

    def form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        return {k: v[0] for k, v in parse_qs(body).items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            msg = parse_qs(parsed.query).get("message", [""])[0]
            self.send_html(page(msg))
            return
        self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path).path
        f = self.form()
        try:
            if p == "/toggle":
                with db() as conn:
                    conn.execute("UPDATE assignments SET completed=1-completed WHERE id=?", (int(f["id"]),))
                self.redirect()
                return
            if p == "/notes":
                with db() as conn:
                    conn.execute("UPDATE assignments SET notes=? WHERE id=?", (f.get("notes", ""), int(f["id"])))
                self.redirect("ההערה נשמרה")
                return
            if p == "/add":
                with db() as conn:
                    cid = upsert_course(conn, f["course_code"].strip(), f["course_name"].strip())
                    add_assignment(conn, cid, f["number"].strip(), f["due_date"].strip())
                self.redirect("המטלה נוספה")
                return
            if p == "/settings":
                set_setting("email_to", f.get("email_to", "").strip())
                self.redirect("כתובת המייל נשמרה")
                return
            if p == "/import":
                count = import_default_ics()
                self.redirect(f"יובאו {count} מטלות")
                return
            if p == "/send":
                _, msg = send_weekly_email()
                self.redirect(msg)
                return
        except Exception as exc:
            self.redirect(f"שגיאה: {exc}")
            return
        self.send_error(404)


def run_server(open_browser: bool = True):
    init_db()
    seed_data()
    import_default_ics()
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    print(f"המערכת פועלת בכתובת http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    run_server()
