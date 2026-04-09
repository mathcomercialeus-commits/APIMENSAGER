const state = {
  token: localStorage.getItem("token") || "",
  user: null,
  posts: [],
  settings: null,
  uploadedMedia: null
};

const $ = (id) => document.getElementById(id);
const loginView = $("login-view");
const appView = $("app-view");
const loginForm = $("login-form");
const loginError = $("login-error");
const welcome = $("welcome");

const postModal = $("post-modal");
const postForm = $("post-form");
const postError = $("post-error");
const mediaInput = $("media-file");
const mediaPreview = $("media-preview");

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "Erro de API");
  }
  return payload;
}

function setAuthed(authed) {
  loginView.classList.toggle("hidden", authed);
  appView.classList.toggle("hidden", !authed);
}

function badgeStatus(status) {
  return `<span class="badge">${escapeHtml(status)}</span>`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString("pt-BR");
}

function getSelectedNetworks() {
  return [...document.querySelectorAll(".network:checked")].map((input) => input.value);
}

async function loadDashboard() {
  const status = $("status-filter").value;
  const network = $("network-filter").value;
  const searchParams = new URLSearchParams();
  if (status) searchParams.set("status", status);
  if (network) searchParams.set("network", network);

  state.posts = await api(`/api/posts?${searchParams.toString()}`);
  renderStats();
  renderTable();
  renderCalendar();
  renderUpcoming();

  const logs = await api("/api/logs");
  $("logs-list").innerHTML = logs
    .slice(0, 20)
    .map((log) => `<li>[${escapeHtml(log.level)}] ${escapeHtml(log.timestamp)} - ${escapeHtml(log.message)}</li>`)
    .join("");
}

function renderStats() {
  const counts = { agendado: 0, publicando: 0, publicado: 0, erro: 0 };
  state.posts.forEach((post) => {
    counts[post.status] = (counts[post.status] || 0) + 1;
  });

  $("count-agendado").textContent = counts.agendado;
  $("count-publicando").textContent = counts.publicando;
  $("count-publicado").textContent = counts.publicado;
  $("count-erro").textContent = counts.erro;
}

function renderTable() {
  const body = $("posts-table");
  body.innerHTML = "";

  state.posts.forEach((post) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(formatDate(post.scheduledAt))}</td>
      <td>${escapeHtml(post.networks.join(", "))}</td>
      <td>${badgeStatus(post.status)}</td>
      <td>${escapeHtml(post.caption)}</td>
      <td>
        <button data-edit="${post.id}" class="ghost">Editar</button>
        <button data-del="${post.id}" class="ghost">Excluir</button>
      </td>
    `;
    body.appendChild(row);
  });

  body.querySelectorAll("[data-edit]").forEach((button) => {
    button.addEventListener("click", () => openEdit(button.dataset.edit));
  });
  body.querySelectorAll("[data-del]").forEach((button) => {
    button.addEventListener("click", () => removePost(button.dataset.del));
  });
}

function renderUpcoming() {
  const now = Date.now();
  const upcoming = state.posts
    .filter(
      (post) =>
        ["agendado", "publicando", "erro"].includes(post.status) &&
        new Date(post.scheduledAt).getTime() >= now
    )
    .slice(0, 8);

  $("upcoming-list").innerHTML = upcoming.length
    ? upcoming
        .map(
          (post) =>
            `<li><strong>${escapeHtml(formatDate(post.scheduledAt))}</strong><br>${escapeHtml(
              post.caption.slice(0, 85)
            )}<br>${escapeHtml(post.networks.join(", "))} - ${badgeStatus(post.status)}</li>`
        )
        .join("")
    : "<li>Nenhum agendamento futuro.</li>";
}

function renderCalendar() {
  const calendar = $("calendar");
  calendar.innerHTML = "";

  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth();
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const offset = (firstDay.getDay() + 6) % 7;

  for (let index = 0; index < offset; index += 1) {
    const blank = document.createElement("div");
    blank.className = "day";
    calendar.appendChild(blank);
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    const cell = document.createElement("div");
    cell.className = "day";

    const postsInDay = state.posts.filter((post) => {
      const date = new Date(post.scheduledAt);
      return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day;
    });

    cell.innerHTML = `<strong>${day}</strong>${postsInDay
      .slice(0, 2)
      .map(
        (post) =>
          `<div class="badge">${escapeHtml(post.networks[0] || "-")} - ${escapeHtml(post.status)}</div>`
      )
      .join("")}`;
    calendar.appendChild(cell);
  }
}

async function saveSettings(event) {
  event.preventDefault();

  const payload = {
    timezone: $("timezone").value.trim(),
    integrations: {
      instagram: {
        mode: "mock",
        connected: Boolean($("ig-account").value.trim()),
        accountId: $("ig-account").value.trim()
      },
      facebook: {
        mode: "mock",
        connected: Boolean($("fb-page").value.trim()),
        pageId: $("fb-page").value.trim()
      },
      whatsapp: {
        mode: "mock",
        connected: Boolean($("wa-phone").value.trim()),
        phoneNumberId: $("wa-phone").value.trim()
      }
    }
  };

  await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
  alert("Configuracoes salvas.");
}

function fillSettings(settings) {
  $("timezone").value = settings.timezone || "UTC";
  $("ig-account").value = settings.integrations?.instagram?.accountId || "";
  $("fb-page").value = settings.integrations?.facebook?.pageId || "";
  $("wa-phone").value = settings.integrations?.whatsapp?.phoneNumberId || "";
}

function resetModal() {
  $("editing-id").value = "";
  $("modal-title").textContent = "Novo post";
  $("caption").value = "";
  $("scheduled-at").value = "";
  document.querySelectorAll(".network").forEach((checkbox) => {
    checkbox.checked = false;
  });
  mediaInput.value = "";
  state.uploadedMedia = null;
  mediaPreview.innerHTML = "Sem midia selecionada";
  postError.textContent = "";
}

function openNewPost() {
  resetModal();
  postModal.showModal();
}

function openEdit(postId) {
  const post = state.posts.find((item) => item.id === postId);
  if (!post) return;

  resetModal();
  $("editing-id").value = post.id;
  $("modal-title").textContent = "Editar post";
  $("caption").value = post.caption;
  $("scheduled-at").value = new Date(post.scheduledAt).toISOString().slice(0, 16);
  document.querySelectorAll(".network").forEach((checkbox) => {
    checkbox.checked = post.networks.includes(checkbox.value);
  });
  state.uploadedMedia = post.media;
  mediaPreview.innerHTML = post.media?.mime.startsWith("video")
    ? `<video controls src="${post.media.path}"></video>`
    : `<img src="${post.media.path}" alt="preview">`;
  postModal.showModal();
}

async function removePost(postId) {
  if (!confirm("Excluir este agendamento?")) return;
  await api(`/api/posts/${postId}`, { method: "DELETE" });
  await loadDashboard();
}

async function uploadSelectedMedia() {
  const file = mediaInput.files?.[0];
  if (!file) return state.uploadedMedia;

  const maxBytes = 20 * 1024 * 1024;
  const allowed = ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm"];

  if (!allowed.includes(file.type)) throw new Error("Formato nao permitido");
  if (file.size > maxBytes) throw new Error("Arquivo excede 20MB");

  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

  state.uploadedMedia = await api("/api/upload", {
    method: "POST",
    body: JSON.stringify({ fileName: file.name, dataUrl })
  });

  return state.uploadedMedia;
}

async function savePost(event) {
  event.preventDefault();
  postError.textContent = "";

  try {
    const media = await uploadSelectedMedia();
    if (!media) throw new Error("Selecione uma midia");

    const scheduledValue = $("scheduled-at").value;
    if (!scheduledValue) throw new Error("Informe a data e hora");

    const payload = {
      caption: $("caption").value.trim(),
      scheduledAt: new Date(scheduledValue).toISOString(),
      networks: getSelectedNetworks(),
      media
    };

    const editingId = $("editing-id").value;
    if (editingId) {
      await api(`/api/posts/${editingId}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/api/posts", { method: "POST", body: JSON.stringify(payload) });
    }

    postModal.close();
    await loadDashboard();
  } catch (error) {
    postError.textContent = error.message;
  }
}

async function login(event) {
  event.preventDefault();
  loginError.textContent = "";

  try {
    const result = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("username").value.trim(),
        password: $("password").value
      })
    });

    state.token = result.token;
    localStorage.setItem("token", state.token);
    state.user = result.user;
    await initApp();
  } catch (error) {
    loginError.textContent = error.message;
  }
}

async function initApp() {
  setAuthed(true);
  const me = await api("/api/me");
  state.user = me.user;
  welcome.textContent = `Ola, ${state.user.username} (${state.user.role})`;

  state.settings = await api("/api/settings");
  fillSettings(state.settings);
  await loadDashboard();
}

function logout() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("token");
  setAuthed(false);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loginForm.addEventListener("submit", login);
$("logout-btn").addEventListener("click", logout);
$("new-post-btn").addEventListener("click", openNewPost);
$("cancel-modal").addEventListener("click", () => postModal.close());
$("refresh-btn").addEventListener("click", loadDashboard);
$("status-filter").addEventListener("change", loadDashboard);
$("network-filter").addEventListener("change", loadDashboard);
$("settings-form").addEventListener("submit", saveSettings);
postForm.addEventListener("submit", savePost);

mediaInput.addEventListener("change", () => {
  const file = mediaInput.files?.[0];
  if (!file) return;

  const localUrl = URL.createObjectURL(file);
  mediaPreview.innerHTML = file.type.startsWith("video")
    ? `<video controls src="${localUrl}"></video>`
    : `<img src="${localUrl}" alt="preview">`;
});

(async function boot() {
  if (!state.token) {
    setAuthed(false);
    return;
  }

  try {
    await initApp();
  } catch {
    logout();
  }
})();
