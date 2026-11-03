"use client";

import { compileSpecStream } from "@json-render/core";
import { ActionProvider, StateProvider, VisibilityProvider } from "@json-render/react";
import { ThreeCanvas } from "@json-render/react-three-fiber";
import { useMemo } from "react";

import { registry } from "./registry";

// Same canvas and registry as ai-components json-render-threejs. The spec is declarative JSON, so the agent's output
// cannot run script in the page: unknown components and props are dropped by the registry.
export function SceneView({ content }: { content: string }) {
  const spec = useMemo(() => {
    const lines = content
      .split("\n")
      .filter((l) => l.trim() && !l.trim().startsWith("```"))
      .join("\n");
    try {
      return compileSpecStream(lines, { root: "", elements: {}, state: {} } as never);
    } catch {
      return null;
    }
  }, [content]);
  if (!spec) return <p className="text-sm text-destructive">The scene could not be compiled.</p>;
  return (
    <StateProvider initialState={{}}>
      <VisibilityProvider>
        <ActionProvider handlers={{}}>
          <div className="relative aspect-video min-h-[320px] w-full overflow-hidden rounded-lg bg-black">
            <ThreeCanvas
              camera={{ fov: 50, position: [6, 6, 6] }}
              className="h-full w-full"
              registry={registry}
              shadows
              spec={spec}
              style={{ height: "100%", width: "100%" }}
            />
          </div>
        </ActionProvider>
      </VisibilityProvider>
    </StateProvider>
  );
}
