import { defineCatalog } from "@json-render/core";
import { threeComponentDefinitions } from "@json-render/react-three-fiber/catalog";
import { schema } from "@json-render/react/schema";

export const catalog = defineCatalog(schema, {
  actions: {},
  components: {
    // Primitives
    Box: threeComponentDefinitions.Box,
    Sphere: threeComponentDefinitions.Sphere,
    Cylinder: threeComponentDefinitions.Cylinder,
    Cone: threeComponentDefinitions.Cone,
    Torus: threeComponentDefinitions.Torus,
    Plane: threeComponentDefinitions.Plane,
    Capsule: threeComponentDefinitions.Capsule,
    TorusKnot: threeComponentDefinitions.TorusKnot,
    RoundedBox: threeComponentDefinitions.RoundedBox,

    // Special materials
    GlassSphere: threeComponentDefinitions.GlassSphere,
    GlassBox: threeComponentDefinitions.GlassBox,
    DistortSphere: threeComponentDefinitions.DistortSphere,

    // Container
    Group: threeComponentDefinitions.Group,

    // Lights
    AmbientLight: threeComponentDefinitions.AmbientLight,
    DirectionalLight: threeComponentDefinitions.DirectionalLight,
    PointLight: threeComponentDefinitions.PointLight,
    SpotLight: threeComponentDefinitions.SpotLight,

    // Model
    Model: threeComponentDefinitions.Model,

    // Environment & atmosphere
    Environment: threeComponentDefinitions.Environment,
    Fog: threeComponentDefinitions.Fog,
    Sky: threeComponentDefinitions.Sky,
    Stars: threeComponentDefinitions.Stars,
    Cloud: threeComponentDefinitions.Cloud,
    Sparkles: threeComponentDefinitions.Sparkles,

    // Staging & grounding
    GridHelper: threeComponentDefinitions.GridHelper,
    ContactShadows: threeComponentDefinitions.ContactShadows,
    ReflectorPlane: threeComponentDefinitions.ReflectorPlane,
    Backdrop: threeComponentDefinitions.Backdrop,

    // Animation wrappers (slot containers — wrap children)
    Float: threeComponentDefinitions.Float,
    Spin: threeComponentDefinitions.Spin,
    Orbit: threeComponentDefinitions.Orbit,
    Pulse: threeComponentDefinitions.Pulse,

    // Post-processing (EffectComposer wraps Bloom/Glitch/Vignette)
    EffectComposer: threeComponentDefinitions.EffectComposer,
    Bloom: threeComponentDefinitions.Bloom,
    Glitch: threeComponentDefinitions.Glitch,
    Vignette: threeComponentDefinitions.Vignette,

    // Effects
    WarpTunnel: threeComponentDefinitions.WarpTunnel,
    MeshPortalMaterial: threeComponentDefinitions.MeshPortalMaterial,

    // Text & labels
    Text3D: threeComponentDefinitions.Text3D,
    HtmlLabel: threeComponentDefinitions.HtmlLabel,

    // Camera & controls
    PerspectiveCamera: threeComponentDefinitions.PerspectiveCamera,
    OrbitControls: threeComponentDefinitions.OrbitControls,
    CameraShake: threeComponentDefinitions.CameraShake,
  },
});

const customRules = [
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

export function getScenePrompt(): string {
  return catalog.prompt({ customRules });
}
