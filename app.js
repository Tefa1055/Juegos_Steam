// app.js - juegos CRUD + grid
let editingGame = null;
async function fetchGames(query){
  const token = getToken();
  const qs = query ? ("?q="+encodeURIComponent(query)) : "";
  const resp = await fetch(API_BASE + ENDPOINTS.games + qs, { headers: token ? { "Authorization": "Bearer " + token } : {} });
  if(!resp.ok) throw new Error("No se pudieron cargar los juegos");
  return await resp.json();
}
function renderGames(items){
  const grid = document.getElementById("grid"); grid.innerHTML = "";
  const tpl = document.createElement("template");
  tpl.innerHTML = `<div class="card">
    <div class="thumb"></div>
    <div class="body">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
        <strong class="title">Título</strong>
        <span class="badge cat">Categoría</span>
      </div>
      <p class="desc helper" style="margin:0">Descripción</p>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="ghost" data-action="edit">Editar</button>
        <button class="danger" data-action="delete">Eliminar</button>
      </div>
    </div>
  </div>`;
  items.forEach(g => {
    const node = tpl.content.cloneNode(true);
    const thumb = node.querySelector(".thumb");
    node.querySelector(".title").textContent = g.titulo || g.nombre || "Juego";
    node.querySelector(".cat").textContent = g.categoria || g.genero || "General";
    node.querySelector(".desc").textContent = g.descripcion || "Sin descripción";
    if(g.portada_url){ thumb.style.backgroundImage = `url('${g.portada_url}')`; thumb.style.backgroundSize = "cover"; }
    node.querySelector("[data-action='edit']").addEventListener("click", () => openEdit(g));
    node.querySelector("[data-action='delete']").addEventListener("click", () => deleteGame(g));
    grid.appendChild(node);
  });
}
async function reloadGames(){ const q = document.getElementById("q")?.value || ""; try{ const items = await fetchGames(q); renderGames(Array.isArray(items) ? items : (items.items || [])); }catch(e){ alert(e.message); console.error(e);}}
function openCreate(){ editingGame = null; document.getElementById("modalTitle").textContent = "Nuevo juego"; const f = document.getElementById("gameForm"); f.reset(); f.id.value=""; document.getElementById("formError").textContent=""; showModal(); }
function openEdit(g){ editingGame = g; document.getElementById("modalTitle").textContent = "Editar juego"; const f = document.getElementById("gameForm"); f.id.value=(g.id||g._id||g.uuid||""); f.titulo.value=g.titulo||g.nombre||""; f.categoria.value=g.categoria||g.genero||""; f.descripcion.value=g.descripcion||""; f.portada_url.value=g.portada_url||""; document.getElementById("formError").textContent=""; showModal(); }
function showModal(){ const bd = document.getElementById("modalBackdrop"); bd.classList.add("show"); bd.setAttribute("aria-hidden","false"); }
function closeModal(){ const bd = document.getElementById("modalBackdrop"); bd.classList.remove("show"); bd.setAttribute("aria-hidden","true"); }
async function saveGame(ev){
  ev.preventDefault(); const token=getToken(); const f=ev.target;
  const data={ titulo:f.titulo.value.trim(), categoria:f.categoria.value.trim(), descripcion:f.descripcion.value.trim(), portada_url:f.portada_url.value.trim() };
  const err=document.getElementById("formError");
  if(!data.titulo||!data.categoria){ err.textContent="Título y categoría son obligatorios."; return; }
  if(data.portada_url && !/^https?:\/\/.+/i.test(data.portada_url)){ err.textContent="La URL de portada debe empezar por http(s)://"; return; }
  try{
    let resp;
    if(editingGame && (f.id.value)){
      const id=f.id.value;
      resp=await fetch(API_BASE + ENDPOINTS.games + id, { method:"PUT", headers:{ "Content-Type":"application/json","Authorization":"Bearer "+token }, body: JSON.stringify(data)});
    }else{
      resp=await fetch(API_BASE + ENDPOINTS.games, { method:"POST", headers:{ "Content-Type":"application/json","Authorization":"Bearer "+token }, body: JSON.stringify(data)});
    }
    if(!resp.ok){ throw new Error(await resp.text()||"Error guardando el juego"); }
    closeModal(); reloadGames();
  }catch(e){ err.textContent = e.message || "Error al guardar"; console.error(e); }
}
async function deleteGame(g){
  if(!confirm("¿Eliminar este juego?")) return;
  const token=getToken();
  try{
    const id=(g.id||g._id||g.uuid);
    const resp=await fetch(API_BASE + ENDPOINTS.games + id, { method:"DELETE", headers:{ "Authorization":"Bearer "+token } });
    if(!resp.ok){ throw new Error("No se pudo eliminar"); }
    reloadGames();
  }catch(e){ alert("Error al eliminar (ver consola). ¿Tu API requiere rol/propietario?"); console.error(e); }
}
window.addEventListener("load", () => {
  const q=document.getElementById("q"); if(q){ q.addEventListener("keydown", (ev)=>{ if(ev.key==="Enter"){ reloadGames(); } }); }
  const form=document.getElementById("gameForm"); if(form) form.addEventListener("submit", saveGame);
  document.addEventListener("keydown", (e)=>{ const open=document.getElementById("modalBackdrop")?.classList.contains("show"); if(open && e.key==="Escape"){ closeModal(); } });
  reloadGames();
});
