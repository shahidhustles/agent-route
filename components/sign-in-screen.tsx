"use client";

import { useSignIn } from "@clerk/nextjs";
import { Command } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

const GoogleMark = () => (
  <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
    <path
      fill="#EA4335"
      d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.5 13.2l7.9 6.1C12.3 13.6 17.7 9.5 24 9.5z"
    />
    <path
      fill="#4285F4"
      d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.4-4.1 7-10.1 7-17.6z"
    />
    <path
      fill="#FBBC05"
      d="M10.4 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.9-4.7l-7.9-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.5 10.8l7.9-6.1z"
    />
    <path
      fill="#34A853"
      d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.7-4.1-13.6-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z"
    />
  </svg>
);

export function SignInScreen() {
  const { signIn } = useSignIn();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const continueWithGoogle = async () => {
    setBusy(true);
    setError(null);
    const { error } = await signIn.sso({
      strategy: "oauth_google",
      redirectUrl: "/",
      redirectCallbackUrl: "/sso-callback",
    });
    if (error) {
      setError(error.longMessage ?? error.message ?? "Google sign-in failed. Try again.");
      setBusy(false);
    }
  };

  return (
    <main className="auth-screen">
      <div className="auth-card">
        <Command size={28} strokeWidth={1.6} />
        <h1>Sign in to Relay</h1>
        <p>Route a task to an agent and a model, watch it run, and read the result.</p>
        <Button
          variant="outline"
          className="auth-google"
          disabled={busy}
          onClick={continueWithGoogle}
        >
          <GoogleMark />
          Continue with Google
        </Button>
        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
