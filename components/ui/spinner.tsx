import { Loader2Icon } from "lucide-react";

import { cn } from "@/lib/utils";

/** Spins unless the reader asked for less motion; the icon alone still says "working". */
function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return <Loader2Icon aria-hidden className={cn("size-3.5 animate-spin motion-reduce:animate-none", className)} {...props} />;
}

export { Spinner };
