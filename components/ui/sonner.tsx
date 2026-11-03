"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

/** Light-only, tokens from globals.css. Errors are sticky (see lib/notify.ts), so a close button is always on. */
function Toaster(props: ToasterProps) {
  return (
    <Sonner
      closeButton
      position="bottom-right"
      theme="light"
      toastOptions={{
        classNames: {
          toast: "!rounded-sm !border !border-concrete !bg-paper !font-serif !text-[14px] !text-ink !shadow-none",
          title: "!font-medium",
          description: "!text-ash",
          closeButton: "!rounded-sm !border-concrete !bg-paper !text-ink",
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
