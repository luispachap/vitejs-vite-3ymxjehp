// ============================================================
//  Conexión a Supabase — AgroGestión
//  Agroselectos P&A
//
//  Este archivo crea UN solo cliente de Supabase que toda la
//  aplicación reutiliza. Lee las llaves desde variables de
//  entorno para no exponerlas en el código.
//
//  Modelo de autenticación:
//  - Si el usuario entra con correo y contraseña, esa cuenta
//    es la sesión activa.
//  - Si el usuario entra con PIN (trabajador, cuadrilla, etc),
//    la app inicia sesión con la "cuenta técnica" del rancho
//    (definida en VITE_SUPABASE_APP_EMAIL/PASSWORD).
// ============================================================

import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const appEmail = import.meta.env.VITE_SUPABASE_APP_EMAIL;
const appPassword = import.meta.env.VITE_SUPABASE_APP_PASSWORD;

if (!url || !anonKey) {
  console.warn(
    "AgroGestión: faltan las llaves de Supabase. " +
    "Verifica que el archivo .env tenga VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY."
  );
}

export const supabase = createClient(url || "", anonKey || "", {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false,
  },
});

export const supabaseListo = Boolean(url && anonKey);

// ¿Hay cuenta técnica configurada? Si no, los trabajadores con PIN
// no podrán escribir a la nube (caen al modo solo-local).
export const cuentaTecnicaListo = Boolean(appEmail && appPassword);

// Inicia sesión con la cuenta técnica del rancho.
// Útil cuando un usuario entra por PIN (sin cuenta propia)
// y la app necesita poder escribir a Supabase en su nombre.
export async function iniciarConCuentaTecnica() {
  if (!cuentaTecnicaListo) return { ok: false, motivo: "no_configurada" };
  try {
    // ¿Ya hay sesión activa? No re-loguear.
    const { data: { session } } = await supabase.auth.getSession();
    if (session) return { ok: true, yaIniciada: true };
    const { error } = await supabase.auth.signInWithPassword({
      email: appEmail, password: appPassword,
    });
    if (error) return { ok: false, motivo: error.message };
    return { ok: true };
  } catch (e) {
    return { ok: false, motivo: e?.message || "desconocido" };
  }
}
