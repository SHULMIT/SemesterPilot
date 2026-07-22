from app import init_db, seed_data, import_default_ics, send_weekly_email

init_db()
seed_data()
import_default_ics()
ok, message = send_weekly_email()
print(message)
raise SystemExit(0 if ok else 1)
