"use client";

import { HandleSSOCallback } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

export function SsoCallback() {
  const router = useRouter();
  const go = (url: string) =>
    url.startsWith("http") ? window.location.assign(url) : router.push(url);
  return (
    <HandleSSOCallback
      navigateToApp={({ decorateUrl }) => go(decorateUrl("/"))}
      navigateToSignIn={() => router.push("/")}
      navigateToSignUp={() => router.push("/")}
    />
  );
}
