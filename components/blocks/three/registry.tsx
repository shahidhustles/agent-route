import { defineRegistry } from "@json-render/react";
import { threeComponents } from "@json-render/react-three-fiber";

import { catalog } from "./catalog";

export const { registry } = defineRegistry(catalog, {
  components: {
    // Primitives
    Box: threeComponents.Box,
    Sphere: threeComponents.Sphere,
    Cylinder: threeComponents.Cylinder,
    Cone: threeComponents.Cone,
    Torus: threeComponents.Torus,
    Plane: threeComponents.Plane,
    Capsule: threeComponents.Capsule,
    TorusKnot: threeComponents.TorusKnot,
    RoundedBox: threeComponents.RoundedBox,

    // Special materials
    GlassSphere: threeComponents.GlassSphere,
    GlassBox: threeComponents.GlassBox,
    DistortSphere: threeComponents.DistortSphere,

    // Container
    Group: threeComponents.Group,

    // Lights
    AmbientLight: threeComponents.AmbientLight,
    DirectionalLight: threeComponents.DirectionalLight,
    PointLight: threeComponents.PointLight,
    SpotLight: threeComponents.SpotLight,

    // Model
    Model: threeComponents.Model,

    // Environment & atmosphere
    Environment: threeComponents.Environment,
    Fog: threeComponents.Fog,
    Sky: threeComponents.Sky,
    Stars: threeComponents.Stars,
    Cloud: threeComponents.Cloud,
    Sparkles: threeComponents.Sparkles,

    // Staging & grounding
    GridHelper: threeComponents.GridHelper,
    ContactShadows: threeComponents.ContactShadows,
    ReflectorPlane: threeComponents.ReflectorPlane,
    Backdrop: threeComponents.Backdrop,

    // Animation wrappers
    Float: threeComponents.Float,
    Spin: threeComponents.Spin,
    Orbit: threeComponents.Orbit,
    Pulse: threeComponents.Pulse,

    // Post-processing
    EffectComposer: threeComponents.EffectComposer,
    Bloom: threeComponents.Bloom,
    Glitch: threeComponents.Glitch,
    Vignette: threeComponents.Vignette,

    // Effects
    WarpTunnel: threeComponents.WarpTunnel,
    MeshPortalMaterial: threeComponents.MeshPortalMaterial,

    // Text & labels
    Text3D: threeComponents.Text3D,
    HtmlLabel: threeComponents.HtmlLabel,

    // Camera & controls
    PerspectiveCamera: threeComponents.PerspectiveCamera,
    OrbitControls: threeComponents.OrbitControls,
    CameraShake: threeComponents.CameraShake,
  },
});
