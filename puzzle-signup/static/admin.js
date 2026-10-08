const $ = (id) => document.getElementById(id);
let users = [];

function say(text, kind = "") { $("msg").textContent = text; $("msg").className = "msg " + kind; }
function show(which) {
  ["disabled", "login", "list"].forEach((id) => ($(id).hidden = id !== which));
}

function render() {
  const q = $("search").value.trim().toLowerCase();
  const shown = users.filter((u) => u.username.toLowerCase().includes(q));
  const tbody = $("rows");
  tbody.innerHTML = "";
  for (const u of shown) {
    const tr = document.createElement("tr");
    for (const value of [u.id, u.username, u.created_at]) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  $("count").textContent = `${shown.length} of ${users.length} account${users.length === 1 ? "" : "s"}`;
}

async function loadUsers() {
  const res = await fetch("/api/admin/users");
  if (!res.ok) { show("login"); return; }
  users = (await res.json()).users;
  show("list");
  render();
}

async function start() {
  say("");
  const me = await (await fetch("/api/admin/me")).json();
  if (!me.enabled) return show("disabled");
  if (me.admin) return loadUsers();
  show("login");
}

$("login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const res = await fetch("/api/admin/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: $("a-user").value, password: $("a-pass").value }),
  });
  const data = await res.json().catch(() => ({}));
  if (res.ok) { $("a-pass").value = ""; say(""); loadUsers(); }
  else say(data.error || "Login failed.", "err");
});

$("logout").addEventListener("click", async () => {
  await fetch("/api/admin/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  users = []; show("login"); say("Logged out.", "ok");
});
$("search").addEventListener("input", render);

start();
