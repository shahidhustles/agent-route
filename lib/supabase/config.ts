/** Supabase needs a project URL and a public key. Without them the app keeps its in-memory chat list. */
export const supabaseUrl = () => process.env.NEXT_PUBLIC_SUPABASE_URL;
export const supabaseKey = () =>
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
export const supabaseConfigured = () => Boolean(supabaseUrl() && supabaseKey());

export const ARTIFACT_BUCKET = "artifacts";
