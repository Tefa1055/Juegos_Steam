// auth.js
const API_BASE = (window.ENV && window.ENV.API_BASE) ? window.ENV.API_BASE : "http://localhost:8000";
const ENDPOINTS = {
  login: "/api/v1/usuarios/login",
  register: "/api/v1/usuarios/",
  forgot: "/api/v1/auth/forgot-password",
  reset: "/api/v1/auth/reset-password",
  me: "/api/v1/usuarios/me",
  games: "/api/v1/juegos/",
  reviews: "/api/v1/reviews/",
  gameReviews: "/api/v1/juegos/"
};
function getToken(){ return localStorage.getItem("token"); }
function setToken(t){ if(t){ localStorage.setItem("token", t); } }
function clearToken(){ localStorage.removeItem("token"); }
async function requireAuth(){
  const token = getToken();
  if(!token){ location.replace("./login.html"); return; }
  try{
    const me = await fetch(API_BASE + ENDPOINTS.me, { headers: { "Authorization": "Bearer " + token }}).then(r => r.ok ? r.json() : null);
    if(!me) throw new Error("not auth");
    const badge = document.getElementById("userBadge");
    if(badge){ badge.textContent = me.username || me.email || "Usuario"; }
  }catch(e){ clearToken(); location.replace("./login.html"); }
}
function logout(){ clearToken(); location.replace("./index.html"); }
async function login(email, password){
  const resp = await fetch(API_BASE + ENDPOINTS.login, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ email, password }) });
  if(!resp.ok) return false; const data = await resp.json();
  const token = data.access_token || data.token || data.jwt || null; if(token) setToken(token); return !!token;
}
async function registerUser(payload){
  const resp = await fetch(API_BASE + ENDPOINTS.register, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload) });
  return resp.ok;
}
async function forgotPassword(email){
  const resp = await fetch(API_BASE + ENDPOINTS.forgot, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ email }) });
  return resp.ok;
}
async function resetPassword(token, new_password){
  const resp = await fetch(API_BASE + ENDPOINTS.reset, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ token, new_password }) });
  return resp.ok;
}
