"use client";

import { useSession } from "@clerk/nextjs";
import { createClient } from "@supabase/supabase-js";
import { useEffect, useMemo, useRef } from "react";

import { supabaseConfigured, supabaseKey, supabaseUrl } from "./config";

/**
 * One Supabase client per page, signed with the Clerk session token (Supabase's native Clerk integration).
 * The token is fetched on every request, so it never expires under the client.
 */
export function useSupabase() {
  const { session } = useSession();
  const sessionRef = useRef(session);
  useEffect(() => {
    sessionRef.current = session;
  });
  return useMemo(
    () =>
      supabaseConfigured()
        ? createClient(supabaseUrl()!, supabaseKey()!, {
            accessToken: async () => (await sessionRef.current?.getToken()) ?? null,
          })
        : null,
    [],
  );
}
