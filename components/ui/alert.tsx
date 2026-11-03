import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const alertVariants = cva("relative flex w-full items-start gap-3 rounded-sm border bg-paper p-4 text-[14px]", {
  variants: { variant: { default: "border-hairline text-ink", destructive: "border-fail text-ink [&>svg]:text-fail" } },
  defaultVariants: { variant: "default" },
});

function Alert({ className, variant, ...props }: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return <div className={cn(alertVariants({ variant }), className)} data-slot="alert" role="alert" {...props} />;
}

function AlertTitle({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("chrome mb-1", className)} data-slot="alert-title" {...props} />;
}

function AlertDescription({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("text-ash", className)} data-slot="alert-description" {...props} />;
}

export { Alert, AlertDescription, AlertTitle };
