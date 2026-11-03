import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";
import { clerkConfigured, SETUP_MESSAGE } from "@/lib/clerk-config";

// "/" serves the signed-out screen itself, and the Google redirect lands on /sso-callback.
const isPublicPage = (r: NextRequest) => ["/", "/sso-callback"].includes(r.nextUrl.pathname);
const isApi = (r: NextRequest) => r.nextUrl.pathname.startsWith("/api");

const withClerk = clerkMiddleware(async (auth, request) => {
  if (isApi(request)) {
    const { userId } = await auth();
    if (!userId) return NextResponse.json({ error: "Sign in to use Relay." }, { status: 401 });
    return;
  }
  if (!isPublicPage(request)) await auth.protect();
});

export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (!clerkConfigured()) {
    // Fail closed: the backend rewrite and the model routes stay unreachable until keys exist.
    return isApi(request)
      ? NextResponse.json({ error: SETUP_MESSAGE }, { status: 503 })
      : NextResponse.next();
  }
  return withClerk(request, event);
}

export const config = {
  // Clerk's recommended matcher: skip Next internals and static files, always run for API routes.
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
