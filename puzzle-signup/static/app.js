const SOLVED = [1, 2, 3, 4, 5, 6, 7, 8, 0];
let board = [], token = "", moves = [], solved = false;

const $ = (id) => document.getElementById(id);
const boardEl = $("board"), movesEl = $("moves"), msg = $("msg");
const signup = $("signup"), login = $("login");

function say(text, kind = "") { msg.textContent = text; msg.className = "msg " + kind; }

function neighbors(i) {
  const r = Math.floor(i / 3), c = i % 3, out = [];
  if (r > 0) out.push(i - 3);
  if (r < 2) out.push(i + 3);
  if (c > 0) out.push(i - 1);
  if (c < 2) out.push(i + 1);
  return out;
}

function render() {
  boardEl.innerHTML = "";
  boardEl.classList.toggle("done", solved);
  board.forEach((value, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "tile" + (value === 0 ? " gap" : "");
    b.textContent = value || "";
    b.setAttribute("aria-label", value ? `Tile ${value}` : "Empty space");
    b.disabled = solved || value === 0;
    b.addEventListener("click", () => move(i));
    boardEl.appendChild(b);
  });
  movesEl.textContent = `${moves.length} move${moves.length === 1 ? "" : "s"}`;
}

function setLocked(locked) {
  signup.classList.toggle("locked", locked);
  ["su-user", "su-pass", "su-btn"].forEach((id) => ($(id).disabled = locked));
  if (!locked) $("su-user").focus();
}

function move(i) {
  const blank = board.indexOf(0);
  if (solved || !neighbors(blank).includes(i)) return;
  [board[blank], board[i]] = [board[i], board[blank]];
  moves.push(i);
  solved = board.every((v, k) => v === SOLVED[k]);
  render();
  if (solved) { setLocked(false); say("Puzzle solved. Choose a username and password.", "ok"); }
}

async function loadPuzzle() {
  say("");
  solved = false; moves = [];
  setLocked(true);
  try {
    const res = await fetch("/api/puzzle");
    const data = await res.json();
    token = data.token; board = data.board;
    render();
  } catch {
    say("Could not reach the server. Is server.py running?", "err");
  }
}

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return { ok: res.ok, data: await res.json().catch(() => ({})) };
}

signup.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!solved) return;
  const { ok, data } = await post("/api/register", {
    username: $("su-user").value, password: $("su-pass").value, token, moves,
  });
  if (ok) {
    say(data.message, "ok");
    signup.reset();
    await loadPuzzle();
    say(data.message + " You can now log in.", "ok");
  } else {
    say(data.error || "Something went wrong.", "err");
  }
});

login.addEventListener("submit", async (e) => {
  e.preventDefault();
  const { ok, data } = await post("/api/login", { username: $("li-user").value, password: $("li-pass").value });
  say(ok ? data.message : data.error, ok ? "ok" : "err");
});

function showTab(which) {
  const isSignup = which === "signup";
  signup.hidden = !isSignup; login.hidden = isSignup;
  $("tab-signup").classList.toggle("active", isSignup);
  $("tab-login").classList.toggle("active", !isSignup);
  $("tab-signup").setAttribute("aria-selected", isSignup);
  $("tab-login").setAttribute("aria-selected", !isSignup);
  say("");
}
$("tab-signup").addEventListener("click", () => showTab("signup"));
$("tab-login").addEventListener("click", () => showTab("login"));
$("reset").addEventListener("click", loadPuzzle);

loadPuzzle();
