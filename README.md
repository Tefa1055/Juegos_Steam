# Steam Dashboard - Frontend (Static)
Sitio estático con flujo: Landing → Login/Registro/Olvidé → Dashboard (autenticado).
- Juegos: grid + CRUD con modal
- Reseñas: estrellas, imagen opcional (URL o upload), CRUD

## Despliegue (Render Static Site)
Build command: (vacío) — Publish directory: `.`

## Config
Edita `env.js` y pon tu API:
```js
window.ENV = { API_BASE: "https://tu-api.onrender.com" }
```
