"""Print every account stored in users.db (passwords are hashed, never shown).
In Docker:  docker compose exec web python list_users.py
"""
import os
import sqlite3
from pathlib import Path

data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent))
db = sqlite3.connect(data_dir / "users.db")
rows = db.execute("SELECT id, username, created_at FROM users ORDER BY id").fetchall()
if not rows:
    print("No accounts yet.")
for r in rows:
    print(f"#{r[0]:<3} {r[1]:<22} created {r[2]}")
