// Free fixture: inline three.js r147 and its OrbitControls into one HTML file, as the scene agent is told to.
const fs = require("fs");
const root = "/usr/local/lib/node_modules/three";
const three = fs.readFileSync(root + "/build/three.min.js", "utf8");
const orbit = fs.readFileSync(root + "/examples/js/controls/OrbitControls.js", "utf8");
const scene = `
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio); renderer.setSize(innerWidth, innerHeight); document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x101826); scene.fog = new THREE.Fog(0x101826, 12, 30);
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 100); camera.position.set(6, 5, 8);
const controls = new THREE.OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
scene.add(new THREE.AmbientLight(0x8899bb, 0.6)); const sun = new THREE.DirectionalLight(0xffe2b0, 1.2); sun.position.set(5, 8, 3); scene.add(sun);
const ground = new THREE.Mesh(new THREE.CircleGeometry(12, 48), new THREE.MeshStandardMaterial({ color: 0x1d2b3a })); ground.rotation.x = -Math.PI / 2; scene.add(ground);
const cubes = [];
[0xf2a93b, 0x4fb3a9, 0xe76f51].forEach((c, i) => { const m = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.4, 1.4), new THREE.MeshStandardMaterial({ color: c, roughness: 0.4 })); m.position.set((i - 1) * 2.6, 1, 0); scene.add(m); cubes.push(m); });
addEventListener("resize", () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
renderer.setAnimationLoop((t) => { cubes.forEach((m, i) => { m.rotation.y = t / 1000 + i; m.position.y = 1 + Math.sin(t / 700 + i) * 0.25; }); controls.update(); renderer.render(scene, camera); });`;
fs.writeFileSync(process.argv[2] || "out/scene.html", `<!doctype html><meta charset="utf-8"><style>body{margin:0;overflow:hidden}</style><body><script>${three}</script><script>${orbit}</script><script>${scene}</script></body>`);
