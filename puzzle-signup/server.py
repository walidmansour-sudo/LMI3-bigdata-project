"""
Puzzle Signup - local web server (Python standard library only, no pip install).

Run:   python server.py            (or: docker compose up --build)
Open:  http://127.0.0.1:8000

Accounts are stored in users.db (SQLite) next to this file.
The puzzle is checked on the SERVER: it creates a shuffled board, the browser
sends back the list of moves, and the server replays them. No valid solution,
no account.
"""
import hashlib
import hmac
import json
import mimetypes
import os
import random
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

from exporter import export_from_db

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE))   # where users.db lives (Docker: /data)
DB_PATH = DATA_DIR / "users.db"
EXPORT_DIR = Path(os.environ.get("EXPORT_DIR", DATA_DIR))   # where users.xlsx is written (Docker: /exports)
EXPORT_PATH = EXPORT_DIR / "users.xlsx"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
# Admin account (NOT stored in the database). Admin is disabled until ADMIN_PASSWORD is set.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_SESSION_TTL = 60 * 60        # admin stays logged in for 1 hour
ADMIN_MAX_FAILS, ADMIN_LOCK_SECONDS = 5, 60
# Puzzle difficulty = number of random moves used to shuffle the board.
# 6 = very easy, 8 = easy (default), 20 = medium, 80 = hard.
SHUFFLES = int(os.environ.get("PUZZLE_SHUFFLES", "8"))

SOLVED = [1, 2, 3, 4, 5, 6, 7, 8, 0]  # 0 = empty slot
PUZZLE_TTL = 15 * 60                   # a puzzle expires after 15 minutes
MAX_MOVES = 2000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")

puzzles = {}        # token -> {"board": [...], "expires": timestamp}
puzzles_lock = Lock()
export_lock = Lock()
admin_lock = Lock()
admin_sessions = {}   # token -> expiry timestamp
admin_fails = {}      # client ip -> (failed attempts, locked until)


# ---------- database ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id            INTEGER PRIMARY KEY AUTOINCREMENT,
                   username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                   password_hash TEXT NOT NULL,
                   created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )


def refresh_excel():
    """Rewrite users.xlsx from the database. Never lets an Excel problem break a sign-up."""
    try:
        with export_lock:
            export_from_db(DB_PATH, EXPORT_PATH)
    except Exception as exc:  # e.g. file open in Excel, folder not writable
        print(f"   [excel] could not update {EXPORT_PATH}: {exc} (account was still saved)")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


# ---------- puzzle (3x3 sliding puzzle) ----------
def neighbors(i):
    r, c = divmod(i, 3)
    out = []
    if r > 0: out.append(i - 3)
    if r < 2: out.append(i + 3)
    if c > 0: out.append(i - 1)
    if c < 2: out.append(i + 1)
    return out


def new_puzzle():
    """Shuffle by making random legal moves from the solved board (always solvable)."""
    while True:
        board = SOLVED[:]
        blank, prev = 8, None
        for _ in range(SHUFFLES):
            options = [n for n in neighbors(blank) if n != prev]
            n = random.choice(options)
            board[blank], board[n] = board[n], board[blank]
            prev, blank = blank, n
        if board != SOLVED:
            break
    token = secrets.token_urlsafe(24)
    now = time.time()
    with puzzles_lock:
        for t in [t for t, p in puzzles.items() if p["expires"] < now]:
            del puzzles[t]
        puzzles[token] = {"board": board, "expires": now + PUZZLE_TTL}
    return token, board


def replay_is_solved(board, moves):
    """moves = list of tile positions the player clicked, in order."""
    if not isinstance(moves, list) or not 0 < len(moves) <= MAX_MOVES:
        return False
    board = board[:]
    blank = board.index(0)
    for m in moves:
        if not isinstance(m, int) or isinstance(m, bool) or m not in neighbors(blank):
            return False
        board[blank], board[m] = board[m], board[blank]
        blank = m
    return board == SOLVED


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    server_version = "PuzzleSignup/1.0"

    def log_message(self, fmt, *args):
        print("  ", self.address_string(), fmt % args)

    # helpers
    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return None
        if length <= 0 or length > 20_000:
            return None
        try:
            data = json.loads(self.rfile.read(length))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    # routes
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/puzzle":
            token, board = new_puzzle()
            return self.send_json(200, {"token": token, "board": board})
        if path == "/api/admin/me":
            return self.send_json(200, {"enabled": bool(ADMIN_PASSWORD), "admin": self.is_admin()})
        if path == "/api/admin/users":
            return self.admin_users()
        self.serve_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        data = self.read_json()
        if data is None:
            return self.send_json(400, {"error": "Invalid request."})
        if path == "/api/register":
            return self.register(data)
        if path == "/api/login":
            return self.login(data)
        if path == "/api/admin/login":
            return self.admin_login(data)
        if path == "/api/admin/logout":
            return self.admin_logout()
        self.send_json(404, {"error": "Not found."})

    def register(self, data):
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        token = str(data.get("token", ""))

        if not USERNAME_RE.match(username):
            return self.send_json(400, {"error": "Username must be 3-20 characters: letters, numbers or underscore."})
        if not 6 <= len(password) <= 100:
            return self.send_json(400, {"error": "Password must be 6 to 100 characters."})

        with puzzles_lock:
            puzzle = puzzles.get(token)
        if not puzzle or puzzle["expires"] < time.time():
            return self.send_json(400, {"error": "Puzzle expired. Reload the puzzle and solve it again."})
        if not replay_is_solved(puzzle["board"], data.get("moves")):
            return self.send_json(400, {"error": "Puzzle not solved."})

        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, hash_password(password)),
                )
        except sqlite3.IntegrityError:
            return self.send_json(409, {"error": "That username is already taken."})

        refresh_excel()
        with puzzles_lock:
            puzzles.pop(token, None)  # a puzzle works once
        self.send_json(201, {"message": f"Account created. Welcome, {username}!"})

    def login(self, data):
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        with get_db() as db:
            row = db.execute("SELECT username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return self.send_json(200, {"message": f"Logged in. Welcome back, {row['username']}!"})
        self.send_json(401, {"error": "Wrong username or password."})

    # ----- admin -----
    def is_admin(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        morsel = cookie.get("admin_session")
        if not morsel or not ADMIN_PASSWORD:
            return False
        with admin_lock:
            expires = admin_sessions.get(morsel.value)
            if expires and expires > time.time():
                return True
            admin_sessions.pop(morsel.value, None)
        return False

    def admin_login(self, data):
        if not ADMIN_PASSWORD:
            return self.send_json(503, {"error": "Admin is not set up. Set ADMIN_PASSWORD first (see README)."})
        ip, now = self.client_address[0], time.time()
        with admin_lock:
            fails, locked_until = admin_fails.get(ip, (0, 0))
            if locked_until > now:
                return self.send_json(429, {"error": "Too many attempts. Wait a minute and try again."})
        user_ok = hmac.compare_digest(str(data.get("username", "")).encode(), ADMIN_USERNAME.encode())
        pass_ok = hmac.compare_digest(str(data.get("password", "")).encode(), ADMIN_PASSWORD.encode())
        if not (user_ok and pass_ok):
            with admin_lock:
                fails += 1
                admin_fails[ip] = (0, now + ADMIN_LOCK_SECONDS) if fails >= ADMIN_MAX_FAILS else (fails, 0)
            return self.send_json(401, {"error": "Wrong admin username or password."})
        token = secrets.token_urlsafe(32)
        with admin_lock:
            admin_fails.pop(ip, None)
            for t in [t for t, e in admin_sessions.items() if e < now]:
                del admin_sessions[t]
            admin_sessions[token] = now + ADMIN_SESSION_TTL
        cookie = f"admin_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={ADMIN_SESSION_TTL}"
        self.send_json(200, {"message": "Admin logged in."}, {"Set-Cookie": cookie})

    def admin_logout(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            pass
        morsel = cookie.get("admin_session")
        if morsel:
            with admin_lock:
                admin_sessions.pop(morsel.value, None)
        self.send_json(200, {"message": "Logged out."},
                       {"Set-Cookie": "admin_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})

    def admin_users(self):
        if not self.is_admin():
            return self.send_json(401, {"error": "Admin login required."})
        with get_db() as db:
            rows = db.execute("SELECT id, username, created_at FROM users ORDER BY id").fetchall()
        self.send_json(200, {"users": [dict(r) for r in rows]})

    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        elif path == "/admin":
            path = "/admin.html"
        target = (STATIC / path.lstrip("/")).resolve()
        if STATIC not in target.parents or not target.is_file():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        body = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    init_db()
    refresh_excel()
    print(f"Puzzle Signup running at http://{HOST}:{PORT}  (Ctrl+C to stop)")
    print(f"Database: {DB_PATH}")
    print(f"Excel copy: {EXPORT_PATH}")
    print("Admin page: /admin  " + (f"(user: {ADMIN_USERNAME})" if ADMIN_PASSWORD else "(disabled: set ADMIN_PASSWORD to enable)"))
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
