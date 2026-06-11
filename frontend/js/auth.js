// Login form submit handler
document.getElementById("login-form").addEventListener("submit", async (e) => {
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
