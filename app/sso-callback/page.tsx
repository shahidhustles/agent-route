import { redirect } from "next/navigation";

import { SsoCallback } from "@/components/sso-callback";
import { clerkConfigured } from "@/lib/clerk-config";

// Rendered per request so the build works before Clerk keys exist.
export const dynamic = "force-dynamic";

export default function Page() {
  if (!clerkConfigured()) redirect("/");
  return <SsoCallback />;
}
