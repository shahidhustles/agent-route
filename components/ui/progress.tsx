"use client";

import { Progress as ProgressPrimitive } from "radix-ui";
import * as React from "react";

import { cn } from "@/lib/utils";

function Progress({ className, indicatorClassName, value, ...props }: React.ComponentProps<typeof ProgressPrimitive.Root> & { indicatorClassName?: string }) {
  return (
    <ProgressPrimitive.Root className={cn("relative h-1.5 w-full overflow-hidden rounded-sm bg-fog", className)} data-slot="progress" value={value} {...props}>
      <ProgressPrimitive.Indicator
        className={cn("h-full w-full origin-left bg-blueprint transition-transform duration-300", indicatorClassName)}
        data-slot="progress-indicator"
        style={{ transform: `scaleX(${(value || 0) / 100})` }}
      />
    </ProgressPrimitive.Root>
  );
}

export { Progress };
