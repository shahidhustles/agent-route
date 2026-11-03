import { auth } from "@clerk/nextjs/server";

import { SetupNeeded } from "@/components/setup-needed";
import { SignInScreen } from "@/components/sign-in-screen";
import { clerkConfigured } from "@/lib/clerk-config";
import { Assistant } from "./assistant";

// Rendered per request: the keys and the session decide what this page shows.
export const dynamic = "force-dynamic";

export default async function Page() {
  if (!clerkConfigured()) return <SetupNeeded />;
  const { userId } = await auth();
  return userId ? <Assistant /> : <SignInScreen />;
}
