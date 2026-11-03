/** Clerk needs both keys. Without them the app shows a setup message instead of crashing. */
export const clerkConfigured = () =>
  Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY);

export const SETUP_MESSAGE =
  "Clerk keys are missing. Add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY to .env.local, then restart the dev server.";
