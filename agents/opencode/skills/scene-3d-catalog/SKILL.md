---
name: scene-3d-catalog
description: Prop-level rules and a working example for json-render three.js scenes (scene.jsonl). Load before writing the scene.
license: MIT
metadata:
  source: original, written for agent-route from the agents-cc-20261031 validator errors
---
# Writing a scene the validator accepts

Every baseline failure was a format error, not a design error. This skill corrects the prompt examples that mislead models. Where it differs from the catalog prompt's example prose, the catalog's prop types win, and the list below shows what those types accept.

## Prop shapes that failed

- `position`, `rotation`, `scale` are arrays of exactly 3 numbers. `scale` on `ContactShadows` is `[10,10,10]`, not `10` and not a 2-array. A fin or any other mesh gets `[x,y,z]`, never 4 numbers.
- Numbers only. `-Math.PI/2` is not JSON and breaks the whole stream. Write `-1.5708` for a floor rotation: `"rotation":[-1.5708,0,0]`.
- `ReflectorPlane` `blur` is one number (for example `300`), not `[300,100]`. Keep `mirror` 0.5 to 0.9, `resolution` 1024, `width` and `height` as numbers.
- `Box` takes `width`, `height`, `depth`, and `material: {color, metalness, roughness, emissive, emissiveIntensity, opacity, transparent, wireframe}`. Colour goes inside `material`, except on `Glass*` components and `ReflectorPlane`, which take `color` directly.
- `HtmlLabel` needs `text` (a string); `transform`, `distanceFactor`, `center`, `color`, `fontSize` are optional. Put each label at the object's position raised by about 1.
- `Bloom` and `Vignette` are children of `EffectComposer`, never siblings.
- `Float` and `Spin` take the mesh in `children`; `Spin` axis is `"x"`, `"y"` or `"z"`.

## Structure

1. The first line is `{"op":"add","path":"/root","value":"scene"}`, and an element with id `scene` must exist. The root id and an element id must be the same string.
2. Every id in any `children` array has its own `add` line. Every element is reachable from the root.
3. Required types: whatever the task names (count them: three fins means three Box elements), plus a light, `PerspectiveCamera` with `makeDefault:true`, `OrbitControls`, at least one `Float` or `Spin` wrapper, grounding that matches the task, and `EffectComposer` with `Bloom` when any `emissive` is set.
4. If the task names a shape, build that shape type: "red box" is a `Box`, "sphere" a `Sphere`. Do not substitute `RoundedBox` for a named Box.
5. Use 8 to 30 elements. Colours the task names are used exactly.

## Skeleton to adapt

```
{"op":"add","path":"/root","value":"scene"}
{"op":"add","path":"/elements/scene","value":{"type":"Group","props":{},"children":["cam","controls","key","hero","floor"]}}
{"op":"add","path":"/elements/cam","value":{"type":"PerspectiveCamera","props":{"position":[0,2,6],"fov":50,"makeDefault":true},"children":[]}}
{"op":"add","path":"/elements/controls","value":{"type":"OrbitControls","props":{"enableDamping":true},"children":[]}}
{"op":"add","path":"/elements/key","value":{"type":"DirectionalLight","props":{"position":[3,5,3],"intensity":1.5},"children":[]}}
{"op":"add","path":"/elements/hero","value":{"type":"Float","props":{"speed":1.5,"floatIntensity":1},"children":["box"]}}
{"op":"add","path":"/elements/box","value":{"type":"Box","props":{"position":[0,1,0],"material":{"color":"#d33"}},"children":[]}}
{"op":"add","path":"/elements/floor","value":{"type":"ContactShadows","props":{"position":[0,0,0],"scale":[10,10,10],"opacity":0.5,"blur":2.5},"children":[]}}
```

## Self-check before you finish

Generate the lines with a Python script (`json.dumps` per line). Then in Python assert: every line parses, the root id exists, every child id exists, every type is in the catalog list, every `position`/`rotation`/`scale` has length 3, `blur` on `ReflectorPlane` is a number, and each type the task names occurs the right number of times.
