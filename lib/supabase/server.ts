import { auth } from "@clerk/nextjs/server";
import { createClient } from "@supabase/supabase-js";

import { supabaseConfigured, supabaseKey, supabaseUrl } from "./config";

/** A Supabase client for the signed-in user's request, or null. Row-level security applies; no service-role key. */
export async function serverSupabase() {
  if (!supabaseConfigured()) return null;
  const { userId, getToken } = await auth();
  if (!userId) return null;
  return {
    userId,
    db: createClient(supabaseUrl()!, supabaseKey()!, { accessToken: async () => getToken() }),
  };
}
