// Mirror of the json-render-threejs block catalog (ai-components blocks/json-render-threejs/lib/catalog.ts).
//   bun scene.mjs prompt            -> print the catalog prompt the block sends the model
//   bun scene.mjs validate <file>   -> compile the JSONL patch stream, print {"passed": bool, "detail": str, ...}
import { readFileSync } from "node:fs";
import { defineCatalog, validateSpec } from "@json-render/core";
import { threeComponentDefinitions as d } from "@json-render/react-three-fiber/catalog";
import { schema } from "@json-render/react/schema";

const NAMES = [
  "Box", "Sphere", "Cylinder", "Cone", "Torus", "Plane", "Capsule", "TorusKnot", "RoundedBox",
  "GlassSphere", "GlassBox", "DistortSphere", "Group",
  "AmbientLight", "DirectionalLight", "PointLight", "SpotLight", "Model",
  "Environment", "Fog", "Sky", "Stars", "Cloud", "Sparkles",
  "GridHelper", "ContactShadows", "ReflectorPlane", "Backdrop",
  "Float", "Spin", "Orbit", "Pulse",
  "EffectComposer", "Bloom", "Glitch", "Vignette",
  "WarpTunnel", "MeshPortalMaterial", "Text3D", "HtmlLabel",
  "PerspectiveCamera", "OrbitControls", "CameraShake",
];
export const catalog = defineCatalog(schema, {
  actions: {},
  components: Object.fromEntries(NAMES.map((n) => [n, d[n]])),
});

// customRules from the block's lib/catalog.ts, so the agent sees the same prompt.
export const CUSTOM_RULES = [
  // Glass & transmission materials
  "Use GlassSphere and GlassBox for luxury, tech, or Apple-style product scenes. Set transmission ~0.95, thickness ~0.5, roughness ~0.05, chromaticAberration ~0.06 for clean refractive glass. Pair with an Environment preset (studio, lobby, city) so reflections have something to catch.",
  "Use DistortSphere for organic, living hero objects — set speed 2-4, distort 0.3-0.6 for gentle morphing or 0.8+ for aggressive distortion. Metallic + emissive DistortSphere with Bloom is a showstopper.",

  // Post-processing
  "When any mesh uses emissive materials (emissive color + emissiveIntensity > 0), ALWAYS add EffectComposer with Bloom (intensity 0.5-1.5, luminanceThreshold 0.2-0.6, mipmapBlur true). Bloom makes emissive materials glow — without it, emissive colors look flat.",
  "Add Vignette (offset 0.5, darkness 0.5-0.7) for cinematic drama. Pairs well with Fog.",
  "Use Glitch sparingly for cyberpunk, error-state, or hacker aesthetics.",
  "EffectComposer is a slot container — put Bloom, Glitch, and/or Vignette as children inside it.",

  // Animation wrappers
  "Float, Spin, Orbit, and Pulse are slot containers — they wrap child meshes to animate them. Use Float (speed 1-2, floatIntensity 1-2) to give hero objects a gentle hovering motion. Use Spin (speed 0.5-2, axis 'y') for turntable showcases. Use Orbit (radius 2-4, speed 0.5-1) for orbiting accent objects. Use Pulse (speed 1-2, min 0.9, max 1.1) for breathing scale.",
  "Wrap at least one key object in Float or Spin to give scenes life. Static scenes feel dead.",

  // Atmosphere
  "Use Stars for space, cosmic, or night scenes. Set radius 100, depth 50, count 5000, fade true for a rich starfield.",
  "Use Sky with sunPosition for outdoor daylight or sunset scenes — sunPosition [100, 20, 100] for golden hour, [0, -1, 0] for night. Adjust rayleigh (1-4) and turbidity (1-10) for mood.",
  "Use Cloud for dreamy, ethereal, or heavenly scenes — set opacity 0.3-0.6, speed 0.2-0.5 for subtle movement.",
  "Use Sparkles for ambient particle magic — count 50-200, speed 0.3-1, size 1-3, scale [5,5,5]. Adds life to any scene.",

  // Staging & grounding
  "Use ContactShadows (opacity 0.4-0.7, blur 2-3, position [0,-0.01,0]) for product/studio scenes instead of a Plane floor — they're softer and more professional.",
  "Use ReflectorPlane for showroom floors, wet surfaces, or mirror effects — set mirror 0.5-0.9, blur [300,100], resolution 1024. Position at y=0 with rotation [-Math.PI/2, 0, 0].",
  "Use Backdrop for curved cyclorama walls (photo studio style) — set floor 1-2, segments 20, receiveShadow true.",

  // Primitives
  "Use TorusKnot for impressive mathematical geometry — the p and q params control the knot topology (p:2/q:3 for trefoil, p:3/q:2 for cinquefoil). Metallic TorusKnot with emissive glow + Bloom is visually striking.",
  "Use RoundedBox instead of Box when you want softer, more modern geometry — set radius 0.05-0.15, smoothness 4.",

  // Labels
  "Use HtmlLabel for annotations, callouts, or data labels in 3D space. Set transform true, distanceFactor 10, center true for billboard-style labels.",

  // Camera
  "Use CameraShake (intensity 0.2-0.5, maxYaw/maxPitch/maxRoll 0.05-0.1) for subtle camera movement that adds energy. Too high feels nauseating.",
  "Use OrbitControls with autoRotate true, autoRotateSpeed 0.5-2 to showcase scenes without user interaction.",

  // Lighting recipes
  "For product/studio scenes: Environment preset 'studio' + AmbientLight intensity 0.3 + DirectionalLight intensity 1.5 + optional SpotLight for accents.",
  "For dramatic/cinematic scenes: low AmbientLight (0.1-0.2) + strong directional key light + colored PointLights for accent + Fog for depth.",
  "For neon/cyberpunk: very low ambient (0.05), multiple colored PointLights, emissive materials on meshes, Bloom required.",
  "For outdoor: Sky + DirectionalLight matching sun direction + AmbientLight 0.4-0.6.",

  // Materials
  "Push material variety — metalness 0.8-1.0 + roughness 0.1-0.3 for polished metal, roughness 0.7-1.0 for matte/clay. Mix emissive accents with non-emissive base geometry for contrast.",
  "Use wireframe: true on accent meshes for a technical/blueprint aesthetic.",
  "Transparent materials (opacity 0.3-0.7, transparent true) layer nicely — use on outer shells around solid inner meshes.",

  // Composition
  "Don't hold back — use the full component palette to create visually rich scenes. Combine atmosphere (Stars/Sky/Fog), animation (Float/Spin), special materials (Glass/Distort), and post-processing (Bloom/Vignette) together.",
  "WarpTunnel creates an animated ring tunnel — use for sci-fi hyperspeed, portals, or energy tunnel backgrounds. Position behind the main subject.",
  "MeshPortalMaterial is a slot container that creates a portal window into a sub-scene — use on a mesh face to create scenes-within-scenes.",
];

const LIGHTS = new Set(["AmbientLight", "DirectionalLight", "PointLight", "SpotLight", "Environment", "Sky"]);

export function check(spec) {
  const result = catalog.validate(spec);
  if (!result.success) {
    const msg = result.error?.issues?.slice(0, 3).map((i) => `${i.path?.join(".")}: ${i.message}`).join("; ");
    return { passed: false, detail: `catalog validation failed: ${msg ?? String(result.error)}`.slice(0, 300) };
  }
  const issues = validateSpec(spec).issues.filter((i) => i.severity === "error");
  if (issues.length) {
    return { passed: false, detail: `spec issues: ${issues.slice(0, 3).map((i) => i.message).join("; ")}`.slice(0, 300) };
  }
  // Render walk: every element reachable from root must resolve to a catalog component.
  const seen = new Set();
  const types = [];
  const stack = [spec.root];
  while (stack.length) {
    const key = stack.pop();
    if (seen.has(key)) continue;
    seen.add(key);
    const el = spec.elements[key];
    if (!el) return { passed: false, detail: `missing element ${key}` };
    if (!NAMES.includes(el.type)) return { passed: false, detail: `unknown component ${el.type}` };
    // The renderer ignores unknown props and fills missing ones; props that are present must type-check.
    const shape = d[el.type].props.shape ?? {};
    for (const [name, value] of Object.entries(el.props ?? {})) {
      if (!shape[name]) continue;
      const parsed = shape[name].safeParse(value);
      // Catalog fields are nullable rather than optional; a field left out is fine.
      const issue = parsed.success ? null : parsed.error.issues.find((i) => !i.message.includes("received undefined"));
      if (issue) {
        return { passed: false, detail: `${key} (${el.type}) prop ${[name, ...issue.path].join(".")}: ${issue.message}`.slice(0, 300) };
      }
    }
    types.push(el.type);
    for (const child of el.children ?? []) stack.push(child);
  }
  if (!types.some((t) => LIGHTS.has(t))) return { passed: false, detail: "no light source", types };
  return { passed: true, detail: `${seen.size} elements render`, types };
}

// Apply RFC 6902 add/replace/remove lines (what the block streams) to build a spec.
export function compilePatches(text) {
  const spec = { root: "", elements: {}, state: {} };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("```")) continue;
    const patch = JSON.parse(line);
    const parts = patch.path.split("/").slice(1).map((p) => p.replaceAll("~1", "/").replaceAll("~0", "~"));
    let node = spec;
    for (const part of parts.slice(0, -1)) {
      if (node[part] === undefined) node[part] = {};
      node = node[part];
    }
    const last = parts.at(-1);
    if (patch.op === "remove") {
      if (Array.isArray(node)) node.splice(Number(last), 1);
      else delete node[last];
    } else if (patch.op === "add" || patch.op === "replace") {
      if (Array.isArray(node) && last === "-") node.push(patch.value);
      else if (Array.isArray(node) && patch.op === "add") node.splice(Number(last), 0, patch.value);
      else node[last] = patch.value;
    } else {
      throw new Error(`unsupported op ${patch.op}`);
    }
  }
  return spec;
}

const [cmd, file] = process.argv.slice(2);
if (cmd === "prompt") {
  process.stdout.write(catalog.prompt({ customRules: CUSTOM_RULES }));
} else if (cmd === "validate") {
  let out;
  try {
    out = check(compilePatches(readFileSync(file, "utf8")));
  } catch (e) {
    out = { passed: false, detail: `invalid patch stream: ${String(e.message).slice(0, 200)}` };
  }
  console.log(JSON.stringify(out));
}
