// Login form submit handler — guard prevents crash when auth.js loads on
// pages that don't have the login form (e.g. index.html).
const _loginForm = document.getElementById("login-form");
if (_loginForm) _loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const formData = new URLSearchParams();
  formData.set("username", document.getElementById("email").value);
  formData.set("password", document.getElementById("password").value);

  const errorEl = document.getElementById("error-message");
  errorEl.textContent = "";

  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData,
    credentials: "same-origin",
  });

  if (res.ok) {
    window.location.href = "/";
  } else {
    errorEl.textContent = "Invalid email or password";
  }
});

// D-03: global 401 -> redirect-to-login interceptor for use across the dashboard's
// shared JS once Plans 02/03 add authenticated pages.
async function apiFetch(url, options = {}) {
  const res = await fetch(url, { ...options, credentials: "same-origin" });
  if (res.status === 401) {
    window.location.href = "/login.html";
    return;
  }
  return res;
}

// Shared logout helper: POSTs /auth/logout via apiFetch (so a stale/expired
// session also bounces through the 401 interceptor above), then sends the
// user back to the login page.
async function logout() {
  await apiFetch("/auth/logout", { method: "POST" });
  window.location.href = "/login.html";
}

// ── Settings modal ────────────────────────────────────────────────────────────

let _currentUserEmail = null;
let _currentUserIsAdmin = false;

// Fetch current user on page load (index.html only).
const _settingsModal = document.getElementById("settings-modal");
if (_settingsModal) {
  apiFetch("/auth/me")
    .then(r => r && r.ok ? r.json() : null)
    .then(data => {
      if (data) {
        _currentUserEmail = data.email;
        _currentUserIsAdmin = data.is_admin === true;
        // Reveal the dashboard only after session is confirmed — eliminates
        // the unauthenticated flash. On 401, apiFetch redirects before this runs.
        document.body.style.visibility = "visible";
      }
    })
    .catch(() => {});
}

function openSettingsModal() {
  const modal = document.getElementById("settings-modal");
  if (!modal) return;
  const isAdmin = _currentUserIsAdmin;
  document.getElementById("section-create-user").style.display = isAdmin ? "block" : "none";
  document.getElementById("modal-divider").style.display = isAdmin ? "block" : "none";
  modal.classList.add("open");
}

function closeSettingsModal() {
  const modal = document.getElementById("settings-modal");
  if (!modal) return;
  modal.classList.remove("open");
  const cu = document.getElementById("form-create-user");
  const cp = document.getElementById("form-change-password");
  if (cu) cu.reset();
  if (cp) cp.reset();
}

function handleModalBackdropClick(e) {
  if (e.target === document.getElementById("settings-modal")) closeSettingsModal();
}

async function handleCreateUser(e) {
  e.preventDefault();
  const email = document.getElementById("cu-email").value.trim();
  const password = document.getElementById("cu-password").value;
  const confirm = document.getElementById("cu-confirm").value;
  if (password !== confirm) { showToast("Las contraseñas no coinciden"); return; }
  if (password.length < 8) { showToast("La contraseña debe tener al menos 8 caracteres"); return; }

  const btn = document.getElementById("cu-submit");
  btn.disabled = true;
  btn.textContent = "Creando...";
  try {
    const res = await apiFetch("/auth/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, is_admin: document.getElementById("cu-is-admin").checked }),
    });
    if (!res) return;
    if (res.status === 201) {
      showToast(`Usuario ${email} creado`);
      document.getElementById("form-create-user").reset();
    } else if (res.status === 409) {
      showToast("Ya existe un usuario con ese email");
    } else if (res.status === 403) {
      showToast("Sin permisos para crear usuarios");
    } else {
      showToast("Error al crear usuario");
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "Crear usuario";
  }
}

async function handleChangePassword(e) {
  e.preventDefault();
  const current_password = document.getElementById("cp-current").value;
  const new_password = document.getElementById("cp-new").value;
  const confirm = document.getElementById("cp-confirm").value;
  if (new_password !== confirm) { showToast("Las contraseñas nuevas no coinciden"); return; }
  if (new_password.length < 8) { showToast("La contraseña debe tener al menos 8 caracteres"); return; }

  const btn = document.getElementById("cp-submit");
  btn.disabled = true;
  btn.textContent = "Guardando...";
  try {
    const res = await apiFetch("/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password, new_password }),
    });
    if (!res) return;
    if (res.ok) {
      showToast("Contraseña actualizada");
      document.getElementById("form-change-password").reset();
      closeSettingsModal();
    } else if (res.status === 401) {
      showToast("Contraseña actual incorrecta");
    } else {
      showToast("Error al cambiar contraseña");
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "Cambiar contraseña";
  }
}
