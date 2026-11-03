"use client";

import mermaid from "mermaid";
import { useEffect, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { sanitizeMermaidSource } from "./mermaid-sanitize";
import { applyMermaidConfig } from "./mermaid-theme";

interface MermaidDiagramProps {
  source: string;
  className?: string;
}

export function MermaidDiagram({ source, className }: MermaidDiagramProps) {
  const reactId = useId().replaceAll(":", "");
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(true);
  const [envVersion, setEnvVersion] = useState(0);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    const onEnvChange = () => {
      setEnvVersion((v) => v + 1);
    };
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", onEnvChange);
    const mo = new MutationObserver(onEnvChange);
    mo.observe(document.documentElement, {
      attributeFilter: ["class"],
      attributes: true,
    });
    return () => {
      mq.removeEventListener("change", onEnvChange);
      mo.disconnect();
    };
  }, []);

  useEffect(() => {
    const sanitizedSource = sanitizeMermaidSource(source);

    if (!sanitizedSource.trim()) {
      setError(null);
      setIsRendering(false);
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
      return;
    }

    let cancelled = false;
    const diagramId = `mermaid-${reactId}-${Date.now()}`;

    const run = async () => {
      setError(null);
      setIsRendering(true);
      applyMermaidConfig();
      try {
        const { svg } = await mermaid.render(diagramId, sanitizedSource);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setIsRendering(false);
        }
      } catch (error) {
        if (!cancelled) {
          setError(error instanceof Error ? error.message : String(error));
          setIsRendering(false);
          if (containerRef.current) {
            containerRef.current.innerHTML = "";
          }
        }
      }
    };

    run().catch((error) => {
      if (!cancelled) {
        setError(error instanceof Error ? error.message : String(error));
        setIsRendering(false);
        if (containerRef.current) {
          containerRef.current.innerHTML = "";
        }
      }
    });

    return () => {
      cancelled = true;
    };
  }, [envVersion, reactId, source]);

  return (
    <div
      className={cn("relative flex min-h-0 w-full flex-1 flex-col", className)}
    >
      {isRendering ? (
        <div
          aria-busy="true"
          aria-live="polite"
          className={cn(
            "pointer-events-none absolute inset-0 z-10 rounded-[calc(var(--radius)+4px)] bg-muted/40",
            "animate-pulse motion-reduce:animate-none motion-reduce:bg-muted/60"
          )}
        />
      ) : null}
      {error ? (
        <div
          className="rounded-[calc(var(--radius)+2px)] border border-destructive/35 bg-destructive/10 px-3 py-2.5 text-sm leading-relaxed text-pretty text-destructive shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)] dark:shadow-[inset_0_1px_0_0_rgba(0,0,0,0.2)]"
          role="alert"
        >
          {error}
        </div>
      ) : null}
      <div
        className="mermaid-diagram-root relative z-20 flex min-h-[12rem] w-full flex-1 flex-col items-center justify-start overflow-auto p-2 [&_svg]:block [&_svg]:h-auto [&_svg]:max-w-full"
        ref={containerRef}
      />
    </div>
  );
}
