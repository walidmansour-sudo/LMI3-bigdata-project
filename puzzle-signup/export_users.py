"""
Export the accounts in users.db to an Excel file (users.xlsx) on demand.
The server already does this automatically after every sign-up; this script is
only needed if you want to force a fresh export.

  Without Docker:  python export_users.py
  With Docker:     docker compose exec web python export_users.py   (file appears in ./exports)
"""
import os
import sys
from pathlib import Path

from exporter import export_from_db

data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent))
export_dir = Path(os.environ.get("EXPORT_DIR", data_dir))
db_path = data_dir / "users.db"
out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else export_dir / "users.xlsx"

if not db_path.exists():
    sys.exit(f"No database found at {db_path}. Create an account first.")
print(f"Exported {export_from_db(db_path, out_path)} account(s) to {out_path}")
