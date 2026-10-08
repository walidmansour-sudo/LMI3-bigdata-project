# Puzzle Signup

A local website where a new user must solve a sliding puzzle (3x3) before they can
create an account. Accounts are saved in a local SQLite database (`users.db`).

## Run with Docker (recommended)
    docker compose up --build
Open http://127.0.0.1:8000

- Stop: `Ctrl+C`, or `docker compose down` (accounts are kept).
- Run in background: `docker compose up -d --build`
- See accounts: `docker compose exec web python list_users.py`
- Excel copy of the accounts: `exports/users.xlsx` (see "Excel copy" below)
- Delete everything including accounts: `docker compose down -v`

The database lives in a Docker volume (`users-data`), so it survives rebuilds.
The port is published on 127.0.0.1 only: nobody else on your network can reach it.

## Excel copy of the accounts
The server rewrites an Excel file after **every new account** (and once at startup).
It contains id, username and creation date. Password hashes are never exported.

- With Docker: the file is `exports/users.xlsx`, in the `exports` folder next to `docker-compose.yml`.
- Without Docker: the file is `users.xlsx` next to `server.py`.
- Close the file in Excel (or open a copy) if you want updates to go through. While Excel has it
  open on Windows, the update is skipped and a message appears in the logs. The account is still
  saved, and the file catches up on the next sign-up.
- The file is only a copy. Editing it does not change the real accounts (they live in `users.db`).
- Force a fresh export any time: `docker compose exec web python export_users.py`
  (or `python export_users.py` without Docker).
- On Linux, create the folder yourself before the first start (`mkdir exports`), otherwise Docker
  creates it as root and the app cannot write in it.
- After updating an existing Docker setup, rebuild once: `docker compose up -d --build`.

## Admin page (see the accounts from the site)
Open http://localhost:8000/admin after setting an admin password:

1. Copy `.env.example` to `.env` (same folder as `docker-compose.yml`).
2. Edit `.env`: choose `ADMIN_USERNAME` and a long `ADMIN_PASSWORD`.
3. Start or rebuild: `docker compose up -d --build`
4. Go to http://localhost:8000/admin and log in.

The page lists id, username and creation date, with a search box. Passwords are hashed,
so even the admin cannot read them. The admin account is not in the database: it only exists
through the two settings above. Without `ADMIN_PASSWORD` the admin page stays disabled.
Five wrong attempts lock the login for one minute, and the admin session lasts one hour.
Without Docker: set `ADMIN_USERNAME` and `ADMIN_PASSWORD` as environment variables before
`python server.py`. Never share your `.env` file.

## Run without Docker
Python 3.8+ only, nothing to install:

    python server.py
Open http://127.0.0.1:8000

## Files
- `server.py`            web server + API + SQLite database + puzzle check
- `static/`              the pages (`index.html`, `admin.html`, `style.css`, `app.js`, `admin.js`)
- `list_users.py`        prints the accounts stored in the database
- `exporter.py`          writes the Excel file (no extra package needed)
- `export_users.py`      forces a manual export to `users.xlsx`
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`   container setup

## Settings (environment variables)
| Variable          | Default     | Meaning                                              |
|-------------------|-------------|------------------------------------------------------|
| `PUZZLE_SHUFFLES` | `8`         | Difficulty: 6 very easy, 8 easy, 20 medium, 80 hard  |
| `PORT`            | `8000`      | Port inside the app                                  |
| `HOST`            | `127.0.0.1` | Set to `0.0.0.0` inside Docker (already done)        |
| `ADMIN_USERNAME`  | `admin`     | Admin login name (Docker: set in `.env`)             |
| `ADMIN_PASSWORD`  | empty       | Admin password. Empty = admin page disabled          |
| `DATA_DIR`        | project dir | Folder where `users.db` is stored                    |
| `EXPORT_DIR`      | `DATA_DIR`  | Folder where `users.xlsx` is written (Docker: `/exports`) |

With Docker, change `PUZZLE_SHUFFLES` in `docker-compose.yml`, then `docker compose up -d --build`.

## How it works
1. The browser asks `/api/puzzle`; the server shuffles a board and keeps it.
2. The player solves it; the browser records every move.
3. On "Create account", the browser sends username, password, puzzle token and moves.
4. The server replays the moves itself. If the board is not solved, no account is created.
5. Passwords are hashed with scrypt and a random salt, never stored in clear text.
