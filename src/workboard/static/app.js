"use strict";
// All user-supplied text is inserted via textContent / value, never as HTML.

const STATUSES = ["New", "Planning", "In progress", "Finished"];
const POLL_MS = 10000;
const $ = (id) => document.getElementById(id);

const state = { me: null, team: null, items: [], members: [], teams: [], editing: null, dragging: false, timer: null };

class AuthError extends Error {}

async function api(method, url, body) {
  const resp = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (resp.status === 401 && url !== "/api/login") throw new AuthError();
  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    const detail = data && data.detail;
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return data;
}

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "text") node.textContent = value;
    else node[key] = value;
  }
  node.append(...children);
  return node;
}

const canWrite = () => state.me && state.team === state.me.team;

function showLogin() {
  clearInterval(state.timer);
  state.me = null;
  $("board-view").hidden = true;
  $("login-view").hidden = false;
  $("item-dialog").open && $("item-dialog").close();
}

async function showBoard() {
  $("login-view").hidden = true;
  $("board-view").hidden = false;
  $("whoami").textContent = `${state.me.username} (${state.me.team})`;
  state.teams = await api("GET", "/api/teams");
  const select = $("team-select");
  select.replaceChildren(...state.teams.map((t) => el("option", { value: t, text: t })));
  state.team = state.me.team;
  select.value = state.team;
  await loadTeam();
  clearInterval(state.timer);
  state.timer = setInterval(() => refresh(), POLL_MS);
}

async function loadTeam() {
  [state.items, state.members] = await Promise.all([
    api("GET", `/api/teams/${encodeURIComponent(state.team)}/items`),
    api("GET", `/api/teams/${encodeURIComponent(state.team)}/members`),
  ]);
  render();
}

async function refresh() {
  if (state.dragging) return;
  try {
    state.items = await api("GET", `/api/teams/${encodeURIComponent(state.team)}/items`);
    render();
  } catch (err) {
    if (err instanceof AuthError) showLogin();
  }
}

function render() {
  const writable = canWrite();
  $("readonly-banner").hidden = writable;
  $("new-item-btn").disabled = !writable;
  const board = $("board");
  board.replaceChildren(
    ...STATUSES.map((status) => {
      const column = el("div", { className: "column" }, el("h2", { text: status }));
      column.dataset.status = status;
      for (const item of state.items.filter((i) => i.status === status)) column.append(card(item, writable));
      if (writable) {
        column.addEventListener("dragover", (e) => { e.preventDefault(); column.classList.add("over"); });
        column.addEventListener("dragleave", () => column.classList.remove("over"));
        column.addEventListener("drop", (e) => onDrop(e, status));
      }
      return column;
    }),
  );
}

function card(item, writable) {
  const node = el(
    "div",
    { className: "card", draggable: writable },
    el("div", { className: "title", text: item.title }),
    el("div", { className: "assignee", text: item.assigned_to ? `→ ${item.assigned_to}` : "Unassigned" }),
  );
  node.addEventListener("click", () => openDialog(item));
  node.addEventListener("dragstart", (e) => {
    state.dragging = true;
    e.dataTransfer.setData("text/plain", String(item.id));
  });
  node.addEventListener("dragend", () => { state.dragging = false; });
  return node;
}

async function onDrop(event, status) {
  event.preventDefault();
  state.dragging = false;
  const id = Number(event.dataTransfer.getData("text/plain"));
  const item = state.items.find((i) => i.id === id);
  if (!item || item.status === status) return render();
  try {
    await api("PATCH", `/api/items/${id}`, { status });
    await loadTeam();
  } catch (err) {
    handleError(err);
  }
}

function handleError(err) {
  if (err instanceof AuthError) showLogin();
  else $("item-error").textContent = err.message;
}

function openDialog(item) {
  const writable = canWrite();
  state.editing = item;
  $("dialog-heading").textContent = item ? (writable ? "Edit item" : "Item (read-only)") : "New item";
  $("item-title").value = item ? item.title : "";
  $("item-description").value = item ? item.description : "";
  $("item-assignee").replaceChildren(
    el("option", { value: "", text: "Unassigned" }),
    ...state.members.map((m) => el("option", { value: m, text: m })),
  );
  $("item-assignee").value = item && item.assigned_to ? item.assigned_to : "";
  $("item-status").replaceChildren(...STATUSES.map((s) => el("option", { value: s, text: s })));
  $("item-status").value = item ? item.status : "New";
  $("status-label").hidden = !item;
  for (const id of ["item-title", "item-description", "item-assignee", "item-status", "item-save"]) $(id).disabled = !writable;
  $("item-error").textContent = "";
  $("item-dialog").showModal();
}

async function saveItem(event) {
  event.preventDefault();
  const assigned = $("item-assignee").value || null;
  try {
    if (state.editing) {
      await api("PATCH", `/api/items/${state.editing.id}`, {
        title: $("item-title").value,
        description: $("item-description").value,
        assigned_to: assigned,
        status: $("item-status").value,
      });
    } else {
      await api("POST", "/api/items", {
        title: $("item-title").value,
        description: $("item-description").value,
        assigned_to: assigned,
      });
    }
    $("item-dialog").close();
    await loadTeam();
  } catch (err) {
    handleError(err);
  }
}

async function login(event) {
  event.preventDefault();
  $("login-error").textContent = "";
  try {
    state.me = await api("POST", "/api/login", {
      username: $("login-username").value,
      password: $("login-password").value,
    });
    $("login-password").value = "";
    await showBoard();
  } catch (err) {
    $("login-error").textContent = err.message;
  }
}

async function logout() {
  await api("POST", "/api/logout").catch(() => {});
  showLogin();
}

$("login-form").addEventListener("submit", login);
$("logout-btn").addEventListener("click", logout);
$("item-form").addEventListener("submit", saveItem);
$("item-cancel").addEventListener("click", () => $("item-dialog").close());
$("new-item-btn").addEventListener("click", () => openDialog(null));
$("team-select").addEventListener("change", async (e) => {
  state.team = e.target.value;
  try { await loadTeam(); } catch (err) { if (err instanceof AuthError) showLogin(); }
});

(async () => {
  try {
    state.me = await api("GET", "/api/me");
    await showBoard();
  } catch (err) {
    showLogin();
  }
})();
