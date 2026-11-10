import { Command } from "lucide-react";

export function SetupNeeded() {
  return (
    <main className="auth-screen">
      <div className="auth-card">
        <Command size={28} strokeWidth={1.6} />
        <h1>Finish the Clerk setup</h1>
        <p>
          Relay needs Clerk keys before it can start. Add these two lines to <code>.env.local</code>{" "}
          and restart the dev server.
        </p>
        <pre>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...{"\n"}CLERK_SECRET_KEY=sk_test_...</pre>
        <p>Both keys are on the API keys page of your Clerk dashboard. See .env.example.</p>
      </div>
    </main>
  );
}
