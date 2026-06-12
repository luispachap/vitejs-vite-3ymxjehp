# AgroGestión — Sistema de Rancho

Aplicación de gestión de costos para un rancho agrícola.
Hecha con React + Vite.

## Cómo abrirla en StackBlitz

1. Entra a https://stackblitz.com
2. Inicia sesión (puedes usar tu cuenta de Google o GitHub).
3. Haz clic en el botón azul **"Create new project"** (o el ícono "+").
4. Elige la plantilla **"Vite"** y dentro de ella **"React"** (NO "React TypeScript", solo "React").
5. Se abrirá un proyecto de ejemplo. Vas a reemplazar sus archivos por los de esta carpeta:
   - Borra los archivos que trae de ejemplo dentro de `src/` (normalmente `App.jsx`, `App.css`, `index.css`, `main.jsx`).
   - Sube TODOS los archivos de este proyecto arrastrándolos al panel de archivos de StackBlitz, respetando las carpetas:
     - `package.json` (reemplaza el que ya está)
     - `vite.config.js`
     - `index.html`
     - `src/main.jsx`
     - `src/index.css`
     - `src/App.jsx`
6. StackBlitz instalará las dependencias solo y la app arrancará en la ventana de vista previa.

## Cómo abrirla en tu computadora (alternativa)

Necesitas tener Node.js instalado. Luego, en una terminal dentro de esta carpeta:

```
npm install
npm run dev
```

Abre la dirección que te muestre (normalmente http://localhost:5173).

## Accesos de prueba (PINs demo)

- Administrador: **1234**
- Encargado / Capataz: **5555** (Pedro Ramírez)
- Trabajador: **1111** (tractorista), **2222** (jornalero), **3333** (dronero)
- Cuadrilla: **8888**, **9999**

## Nota sobre los datos

La app guarda todo en el navegador (localStorage). Los datos viven en el
dispositivo donde la abras. Para empezar de cero, puedes borrar los datos
del sitio desde las opciones del navegador, o usar el botón de reinicio
que aparece en la pantalla de error si algo falla.
