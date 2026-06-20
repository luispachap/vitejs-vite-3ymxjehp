import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const appEmail = import.meta.env.VITE_SUPABASE_APP_EMAIL;
const appPassword = import.meta.env.VITE_SUPABASE_APP_PASSWORD;

if (!url || !anonKey) {
  console.warn("Faltan variables de entorno de Supabase (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY).");
}

export const supabase = createClient(url || "", anonKey || "", {
  auth: { persistSession: true, autoRefreshToken: true },
});

export const supabaseListo = !!(url && anonKey);
export let cuentaTecnicaListo = false;

// Inicia sesión con la cuenta técnica compartida (credenciales solo en variables de entorno).
export async function iniciarConCuentaTecnica() {
  if (!supabaseListo || !appEmail || !appPassword) return { ok: false, motivo: "sin_config" };
  try {
    const { data: ses } = await supabase.auth.getSession();
    if (ses?.session) { cuentaTecnicaListo = true; return { ok: true }; }
    const { error } = await supabase.auth.signInWithPassword({ email: appEmail, password: appPassword });
    if (error) return { ok: false, motivo: error.message };
    cuentaTecnicaListo = true;
    return { ok: true };
  } catch (e) {
    return { ok: false, motivo: e?.message || "error" };
  }
}
