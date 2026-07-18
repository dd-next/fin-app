const $ = (id) => document.getElementById(id);
let registerMode = false;

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload && payload.detail ? payload.detail : "Request failed");
  return payload;
}

function showAuth() {
  $("auth-card").classList.remove("hidden");
  $("app-shell").classList.add("hidden");
}

async function showApp(context) {
  $("auth-card").classList.add("hidden");
  $("app-shell").classList.remove("hidden");
  $("workspace-name").textContent = context.workspace.name;
  $("welcome").textContent = `Welcome, ${context.user.display_name}`;
  const assets = await api("/api/v1/assets");
  $("asset-list").replaceChildren(...assets.map((asset) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = asset.code;
    return chip;
  }));
}

$("toggle-auth").addEventListener("click", () => {
  registerMode = !registerMode;
  $("display-field").classList.toggle("hidden", !registerMode);
  $("submit-auth").textContent = registerMode ? "Create account" : "Log in";
  $("toggle-auth").textContent = registerMode ? "I have an account" : "Create account";
  $("password").autocomplete = registerMode ? "new-password" : "current-password";
  $("auth-error").textContent = "";
});

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("auth-error").textContent = "";
  const body = { username: $("username").value, password: $("password").value };
  if (registerMode && $("display-name").value.trim()) body.display_name = $("display-name").value.trim();
  try {
    await showApp(await api(`/api/v1/auth/${registerMode ? "register" : "login"}`, {
      method: "POST", body: JSON.stringify(body),
    }));
  } catch (error) { $("auth-error").textContent = error.message; }
});

$("logout").addEventListener("click", async () => {
  await api("/api/v1/auth/logout", { method: "POST" });
  showAuth();
});

api("/api/v1/auth/me").then(showApp).catch(showAuth);
