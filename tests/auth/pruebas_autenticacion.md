# Pruebas de Autenticación – feature/tests-auth

## ✔ Prueba 1: Login correcto
- Endpoint: POST /auth/login
- Datos enviados: usuario válido + contraseña válida
- Resultado esperado:
  - Código 200 OK
  - Token JWT válido
  - Objeto del usuario

---

## ✔ Prueba 2: Contraseña incorrecta
- Endpoint: POST /auth/login
- Datos: clave errónea
- Resultado esperado:
  - 401 Unauthorized
  - Mensaje: “Credenciales inválidas”

---

## ✔ Prueba 3: Usuario inexistente
- Endpoint: POST /auth/login
- Datos: usuario que no existe
- Resultado esperado:
  - 404 o 401
  - Mensaje: “Usuario no encontrado”

---

## ✔ Prueba 4: Acceso a endpoint protegido sin token
- Endpoint: /usuarios
- Método: GET
- Datos: sin header Authorization
- Resultado esperado:
  - 401 Unauthorized
  - Mensaje: “Token requerido”

---

## ✔ Prueba 5: Token inválido
- Endpoint: /usuarios
- Método: GET
- Datos: token corrupto o vencido
- Resultado esperado:
  - 401 Unauthorized
  - Mensaje: “Token inválido”
