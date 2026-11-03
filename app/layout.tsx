import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";

import { clerkConfigured } from "@/lib/clerk-config";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";

const chat = Inter({ subsets: ["latin"], variable: "--font-chat" });

export const metadata: Metadata = {
  title: "Relay",
  description: "Route a task to an agent and a model, watch it run, and read the result.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const shell = (
    <>
      <TooltipProvider>{children}</TooltipProvider>
      <Toaster />
    </>
  );
  return (
    <html className={chat.variable} lang="en">
      <body>{clerkConfigured() ? <ClerkProvider>{shell}</ClerkProvider> : shell}</body>
    </html>
  );
}
