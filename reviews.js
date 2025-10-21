// reviews.js - reseñas (estrellas + imagen opcional + CRUD)
function starsHtml(value){ const v=Math.max(0,Math.min(5,Math.round(value||0))); let s='<div class="stars" aria-label="Calificación '+v+' de 5">'; for(let i=1;i<=5;i++){ s+= '<span class="star '+(i<=v?'on':'')+'">★</span>'; } s+='</div>'; return s; }
function openCreateReview(game){ const f=document.getElementById("reviewForm"); document.getElementById("reviewModalTitle").textContent="Nueva reseña"; f.reset(); f.id.value=""; f.game_id.value=(game.id||game._id||game.uuid||""); f.rating.value="5"; document.getElementById("reviewFormError").textContent=""; syncStars(5); showReviewModal(); }
function openEditReview(review){ const f=document.getElementById("reviewForm"); document.getElementById("reviewModalTitle").textContent="Editar reseña"; f.id.value=review.id||review._id||""; f.game_id.value=review.game_id||""; f.titulo.value=review.titulo||""; f.imagen_url.value=review.imagen_url||""; f.rating.value=String(review.rating||5); f.contenido.value=review.contenido||""; document.getElementById("reviewFormError").textContent=""; syncStars(parseInt(f.rating.value,10)); showReviewModal(); }
function showReviewModal(){ const bd=document.getElementById("reviewModalBackdrop"); bd.classList.add("show"); bd.setAttribute("aria-hidden","false"); }
function closeReviewModal(){ const bd=document.getElementById("reviewModalBackdrop"); bd.classList.remove("show"); bd.setAttribute("aria-hidden","true"); }
function syncStars(v){ const nodes=document.querySelectorAll("#starsInput .star"); nodes.forEach(n=>{ const val=parseInt(n.getAttribute("data-v"),10); n.classList.toggle("on", val<=v); }); }
window.addEventListener("load", ()=>{ const stars=document.getElementById("starsInput"); if(stars){ stars.addEventListener("click",(e)=>{ const node=e.target.closest(".star"); if(!node) return; const v=parseInt(node.getAttribute("data-v"),10); document.querySelector("#reviewForm [name='rating']").value=String(v); syncStars(v); }); } const rf=document.getElementById("reviewForm"); if(rf){ rf.addEventListener("submit", saveReview); } document.addEventListener("keydown",(e)=>{ const open=document.getElementById("reviewModalBackdrop")?.classList.contains("show"); if(open && e.key==="Escape"){ closeReviewModal(); }}); });
async function saveReview(ev){
  ev.preventDefault(); const token=getToken(); const f=ev.target;
  const data={ titulo:f.titulo.value.trim(), imagen_url:f.imagen_url.value.trim(), rating:parseInt(f.rating.value,10)||5, contenido:f.contenido.value.trim(), game_id:f.game_id.value.trim() };
  const err=document.getElementById("reviewFormError");
  if(!data.titulo || !data.contenido || !data.game_id){ err.textContent="Título, contenido y juego son obligatorios."; return; }
  if(data.imagen_url && !/^https?:\/\/.+/i.test(data.imagen_url)){ err.textContent="La URL de imagen debe empezar por http(s):// (o sube archivo)."; return; }
  try{
    const fileInput=document.getElementById("imagen_file");
    if(fileInput && fileInput.files && fileInput.files[0]){
      const up=new FormData(); up.append("file", fileInput.files[0]);
      const respUp=await fetch(API_BASE + "/api/v1/uploads/image", { method:"POST", headers:{ "Authorization":"Bearer "+token }, body: up });
      if(respUp.ok){ const r=await respUp.json(); data.imagen_url=r.url||data.imagen_url; }
    }
    let resp;
    if(f.id.value){
      const id=f.id.value;
      resp=await fetch(API_BASE + ENDPOINTS.reviews + id, { method:"PUT", headers:{ "Content-Type":"application/json","Authorization":"Bearer "+token }, body: JSON.stringify(data) });
    }else{
      const pathNested=API_BASE + ENDPOINTS.gameReviews + data.game_id + "/reviews";
      resp=await fetch(pathNested, { method:"POST", headers:{ "Content-Type":"application/json","Authorization":"Bearer "+token }, body: JSON.stringify(data) });
      if(!resp.ok){
        resp=await fetch(API_BASE + ENDPOINTS.reviews, { method:"POST", headers:{ "Content-Type":"application/json","Authorization":"Bearer "+token }, body: JSON.stringify(data) });
      }
    }
    if(!resp.ok){ throw new Error(await resp.text()||"Error guardando reseña"); }
    closeReviewModal(); reloadGames();
  }catch(e){ err.textContent=e.message||"Error al guardar reseña"; console.error(e); }
}
async function deleteReview(review){
  if(!confirm("¿Eliminar esta reseña?")) return;
  const token=getToken(); const id=review.id||review._id;
  try{
    const resp=await fetch(API_BASE + ENDPOINTS.reviews + id, { method:"DELETE", headers:{ "Authorization":"Bearer "+token } });
    if(!resp.ok){ throw new Error("No se pudo eliminar"); } reloadGames();
  }catch(e){ alert("Error al eliminar reseña"); console.error(e); }
}
// Extiende renderGames para botón y lista de reseñas
const _renderGames_original = renderGames;
renderGames = async function(items){
  _renderGames_original(items);
  const grid=document.getElementById("grid"); const cards=grid.querySelectorAll(".card");
  items.forEach(async (g, idx)=>{
    const card=cards[idx]; if(!card) return;
    const actions=card.querySelector(".body > div:last-child");
    const btn=document.createElement("button"); btn.className="ghost"; btn.textContent="Reseñar"; btn.addEventListener("click", ()=>openCreateReview(g)); actions.appendChild(btn);
    const wrap=document.createElement("div"); wrap.className="reviews"; const h=document.createElement("h4"); h.className="title"; h.textContent="Reseñas"; wrap.appendChild(h);
    const gameId=(g.id||g._id||g.uuid); let resp=await fetch(API_BASE + ENDPOINTS.gameReviews + gameId + "/reviews"); if(!resp.ok){ resp=await fetch(API_BASE + ENDPOINTS.reviews + "?game_id="+encodeURIComponent(gameId)); }
    const list=resp.ok ? await resp.json() : [];
    list.forEach(rv=>{
      const rc=document.createElement("div"); rc.className="review-card";
      const avatar=document.createElement("div"); avatar.className="avatar"; if(rv.user_avatar){ avatar.style.backgroundImage="url('"+rv.user_avatar+"')"; }
      const body=document.createElement("div"); body.className="review-body";
      const title=document.createElement("h5"); title.className="title"; title.textContent=rv.titulo||"Reseña";
      const meta=document.createElement("div"); meta.className="meta"; meta.innerHTML=(rv.username||"Usuario")+" • "+starsHtml(rv.rating||0);
      const text=document.createElement("p"); text.textContent=rv.contenido||"";
      const media=document.createElement("div"); media.className="review-media"; if(rv.imagen_url){ const img=document.createElement("div"); img.className="img"; img.style.backgroundImage="url('"+rv.imagen_url+"')"; media.appendChild(img); }
      body.appendChild(title); body.appendChild(meta); body.appendChild(text); body.appendChild(media);
      const act=document.createElement("div"); act.className="actions";
      const be=document.createElement("button"); be.className="ghost"; be.textContent="Editar"; be.addEventListener("click", ()=>openEditReview(rv));
      const bd=document.createElement("button"); bd.className="danger"; bd.textContent="Eliminar"; bd.addEventListener("click", ()=>deleteReview(rv));
      act.appendChild(be); act.appendChild(bd);
      rc.appendChild(avatar); rc.appendChild(body); rc.appendChild(act); wrap.appendChild(rc);
    });
    card.appendChild(wrap);
  });
};
