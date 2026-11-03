import { auth } from "@clerk/nextjs/server";
import { clerkConfigured, SETUP_MESSAGE } from "@/lib/clerk-config";

/** Route-handler check behind the proxy. Returns a response to send back, or null when a user is signed in. */
export async function rejectAnonymous(): Promise<Response | null> {
  if (!clerkConfigured()) return Response.json({ error: SETUP_MESSAGE }, { status: 503 });
  const { userId } = await auth();
  return userId ? null : Response.json({ error: "Sign in to use Relay." }, { status: 401 });
}
