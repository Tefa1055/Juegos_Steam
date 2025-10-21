// auth.js — versión corregida
// - Lee API_BASE desde env.js
// - Login con application/x-www-form-urlencoded (OAuth2PasswordRequestForm)
// - Fallbacks por si tu backend usa /token o JSON
// - Helpers de token y requireAuth()

// 1) Config
const API_BASE = (window.ENV && window.ENV.API_BASE) ? window.ENV.API_BASE : "http://localhost:8000";

const ENDPOINTS = {
  login: "/api/v1/usuarios/login",   // OAuth2PasswordRequestForm por defecto
  loginAlt: "/token",                 // fallback clásico de FastAPI
  register: "/api/v1/usuarios/",
  forgot: "/api/v1/auth/forgot-password",
  reset: "/api/v1/auth/reset-password",
  me: "/api/v1/usuarios/me",
  games: "/api/v1/juegos/",
  reviews: "/api/v1/reviews/",
  gameReviews: "/api/v1/juegos/"
};

// 2) Token helpers
function getToken(){ return localStorage.getItem("token"); }
function setToken(t){ if(t){ localStorage.setItem("token", t); } }
function clearToken(){ localStorage.removeItem("token"); }

// 3) Fetch con auth (opcional para reuso)
async function authFetch(path, opts = {}){
  const token = getToken();
  const headers = new Headers(opts.headers || {});
  if(token) headers.set("Authorization", "Bearer " + token);
  return fetch(API_BASE + path, { ...opts, headers });
}

// 4) Guard de página (redirige si no hay sesión)
async function requireAuth(){
  const token = getToken();
  if(!token){ location.replace("./login.html"); return; }
  try{
    const r = await fetch(API_BASE + ENDPOINTS.me, {
      headers: { "Authorization": "Bearer " + token }
    });
    if(!r.ok) throw new Error("Unauthorized");
    const me = await r.json();
    const badge = document.getElementById("userBadge");
    if(badge){ badge.textContent = me.username || me.email || "Usuario"; }
  }catch(e){
    clearToken();
    location.replace("./login.html");
  }
}

// 5) Cerrar sesión
function logout(){
  clearToken();
  location.replace("./index.html");
}

// 6) LOGIN (CORREGIDO)
//   Intenta en este orden:
//   a) POST /api/v1/usuarios/login con x-www-form-urlencoded (username, password)
//   b) POST /token (form-urlencoded)
//   c) POST /api/v1/usuarios/login con JSON { email, password } (por compatibilidad)
async function login(email, password){
  // a) Form-urlencoded → /api/v1/usuarios/login
  const form = new URLSearchParams();
  form.set("username", email);   // OAuth2PasswordRequestForm exige "username"
  form.set("password", password);

  let resp = await fetch(API_BASE + ENDPOINTS.login, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form
  });

  // b) Fallback: /token (mismo esquema)
  if(!resp.ok && (resp.status === 404 || resp.status === 405)){
    const respAlt = await fetch(API_BASE + ENDPOINTS.loginAlt, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form
    });
    if(respAlt.ok) resp = respAlt;
  }

  // c) Fallback: JSON { email, password }
  if(!resp.ok && (resp.status === 415 || resp.status === 422 || resp.status === 400)){
    const respJson = await fetch(API_BASE + ENDPOINTS.login, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    if(respJson.ok) resp = respJson;
  }

  if(!resp.ok) return false;

  const data = await resp.json();
  const token = data.access_token || data.token || data.jwt || null;
  if(token) setToken(token);
  return !!token;
}

// 7) Registro (tu backend suele aceptar JSON)
async function registerUser(payload){
  // payload: { first_name?, last_name?, username, email, password }
  const resp = await fetch(API_BASE + ENDPOINTS.register, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify(payload)
  });
  return resp.ok;
}

// 8) Forgot/Reset (opcionales, si existen en tu backend)
async function forgotPassword(email){
  const resp = await fetch(API_BASE + ENDPOINTS.forgot, {
    method:"POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify({ email })
  });
  return resp.ok;
}

async function resetPassword(token, new_password){
  const resp = await fetch(API_BASE + ENDPOINTS.reset, {
    method:"POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify({ token, new_password })
  });
  return resp.ok;
}

// 9) Exportar helpers al scope global (por si los llamas inline en HTML)
window.requireAuth = requireAuth;
window.logout = logout;
window.login = login;
window.registerUser = registerUser;
window.forgotPassword = forgotPassword;
window.resetPassword = resetPassword;
window.getToken = getToken;
window.authFetch = authFetch;
