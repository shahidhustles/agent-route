"use client";

import { useClerk, useUser } from "@clerk/nextjs";
import { LogOut } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

/** Sidebar footer: the signed-in user's avatar, name and email, with a Sign out button. */
export function AccountFooter() {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();
  const name = user?.fullName ?? user?.primaryEmailAddress?.emailAddress ?? "Account";
  const email = user?.primaryEmailAddress?.emailAddress;
  return (
    <div className="sidebar-account">
      <div className="sidebar-footer" aria-busy={!isLoaded}>
        <Avatar>
          {user?.imageUrl && <AvatarImage src={user.imageUrl} alt="" />}
          <AvatarFallback>{name.charAt(0).toUpperCase()}</AvatarFallback>
        </Avatar>
        <div className="account-text">
          <span title={name}>{isLoaded ? name : "Loading…"}</span>
          {email && email !== name && <p title={email}>{email}</p>}
        </div>
      </div>
      <button className="nav-button" onClick={() => signOut({ redirectUrl: "/" })}>
        <LogOut size={17} />
        Sign out
      </button>
    </div>
  );
}
