// three.js viewport — loads the latest cascade GLB, orbit controls, lights.
// Plain three.js (no react-three-fiber — deps kept minimal for the
// operator's connection, SPEC_PHASE2 §3). three 0.185 addons path verified
// against the installed package (three/addons/* -> examples/jsm/*).
//
// ADR-020: the camera is framed from the loaded model's BOUNDING BOX (see
// ./framing.ts) — never a hardcoded position/target/near/far. The GLB
// arrives in METRES (OCCT converts from mm at export), so any
// millimetre-assuming constant renders the model sub-pixel. The grid and
// the sun light are also re-derived from the model bounds on every load.

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { latestGlbUrl } from "../api/client";
import { frameCameraToObject } from "./framing";

interface ViewportProps {
  reloadToken: number; // change triggers a GLB reload (cache-busted)
  onModelRendered: () => void; // fired when the GLB is on screen [ADD-5]
  onLoadError: (message: string) => void;
}

export default function Viewport({
  reloadToken,
  onModelRendered,
  onLoadError,
}: ViewportProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    controls: OrbitControls;
    modelGroup: THREE.Group;
    sun: THREE.DirectionalLight;
    grid: THREE.GridHelper;
  } | null>(null);
  const callbacksRef = useRef({ onModelRendered, onLoadError });
  callbacksRef.current = { onModelRendered, onLoadError };

  // One-time scene setup.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x101418);

    // Placeholder camera — every plane is re-derived from the model's
    // bounding box on load (ADR-020); before the first load only the grid
    // is visible anyway.
    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / Math.max(container.clientHeight, 1),
      1,
      100000
    );
    camera.position.set(3500, 2800, 3500);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // hemisphere + directional light (per spec) + a ground grid for scale.
    // The sun's TARGET must be in the scene graph to take effect.
    scene.add(new THREE.HemisphereLight(0xffffff, 0x30363d, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 2.0);
    sun.position.set(4000, 6000, 2500);
    scene.add(sun);
    scene.add(sun.target);
    const grid = new THREE.GridHelper(6000, 12, 0x2a3138, 0x1c2229);
    scene.add(grid);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 900, 0);
    controls.update();

    const modelGroup = new THREE.Group();
    scene.add(modelGroup);
    sceneRef.current = { scene, camera, controls, modelGroup, sun, grid };

    // Resize when the CONTAINER changes size (panel layout can change it
    // without a window resize; a canvas sized to a pre-layout container is
    // the "destination rect smaller than viewport rect" warning, ADR-020).
    const onResize = () => {
      const w = container.clientWidth;
      const h = Math.max(container.clientHeight, 1);
      if (w === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    const observer = new ResizeObserver(onResize);
    observer.observe(container);
    // One sizing pass after the first layout settles.
    requestAnimationFrame(onResize);

    let disposed = false;
    renderer.setAnimationLoop(() => {
      if (disposed) return;
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      disposed = true;
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
  }, []);

  // GLB (re)load whenever reloadToken changes.
  useEffect(() => {
    const ctx = sceneRef.current;
    if (!ctx) return;
    let cancelled = false;

    const loader = new GLTFLoader();
    loader.load(
      latestGlbUrl(reloadToken),
      (gltf) => {
        if (cancelled) return;
        ctx.modelGroup.clear();
        const model = gltf.scene;
        model.traverse((obj) => {
          if ((obj as THREE.Mesh).isMesh) {
            const mesh = obj as THREE.Mesh;
            mesh.geometry.computeVertexNormals();
          }
        });
        ctx.modelGroup.add(model);

        // Frame the camera from the model's bounding box — distance, near,
        // far and orbit target all follow the model's real size (ADR-020).
        const { box, centre, size, radius, distance } = frameCameraToObject(
          ctx.camera,
          ctx.controls,
          model
        );

        // Model-scaled ground grid, just under the model's lowest point.
        ctx.scene.remove(ctx.grid);
        ctx.grid.geometry.dispose();
        (ctx.grid.material as THREE.Material).dispose();
        const grid = new THREE.GridHelper(radius * 6, 12, 0x2a3138, 0x1c2229);
        grid.position.y = box.min.y - radius * 0.02;
        ctx.scene.add(grid);
        ctx.grid = grid;

        // Sun follows the model, so direction/shadows are scale-correct.
        ctx.sun.position.set(
          centre.x + radius * 4,
          centre.y + radius * 6,
          centre.z + radius * 2.5
        );
        ctx.sun.target.position.copy(centre);
        ctx.sun.target.updateMatrixWorld();

        // Operator diagnostics (ADR-020 ask #2): proof the model is in the
        // scene and the frame came from its real bounds.
        const fmt = (v: THREE.Vector3) =>
          v.toArray().map((n) => Math.round(n * 1000) / 1000).join(", ");
        console.info(
          "[viewport] model loaded — scene children:",
          ctx.scene.children.length,
          "| bbox size:",
          fmt(size),
          "| bbox centre:",
          fmt(centre),
          "| camera distance:",
          Math.round(distance * 100) / 100,
          "| near/far:",
          ctx.camera.near.toExponential(2),
          "/",
          Math.round(ctx.camera.far)
        );

        // Render one frame immediately, THEN report [ADD-5]: the rebuild
        // timer stops when the new geometry is actually on screen.
        requestAnimationFrame(() => {
          if (!cancelled) callbacksRef.current.onModelRendered();
        });
      },
      undefined,
      (err) => {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "failed to load latest.glb";
        callbacksRef.current.onLoadError(message);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  return <div ref={containerRef} className="viewport-canvas" />;
}
