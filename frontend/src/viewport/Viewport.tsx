// three.js viewport — loads the latest cascade GLB, orbit controls, lights.
// Plain three.js (no react-three-fiber — deps kept minimal for the
// operator's connection, SPEC_PHASE2 §3). three 0.185 addons path verified
// against the installed package (three/addons/* -> examples/jsm/*).

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { latestGlbUrl } from "../api/client";

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
  } | null>(null);
  const callbacksRef = useRef({ onModelRendered, onLoadError });
  callbacksRef.current = { onModelRendered, onLoadError };

  // One-time scene setup.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x101418);

    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / Math.max(container.clientHeight, 1),
      1,
      100000 // model units are mm
    );
    camera.position.set(3500, 2800, 3500);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // hemisphere + directional light (per spec) + a ground grid for scale
    scene.add(new THREE.HemisphereLight(0xffffff, 0x30363d, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 2.0);
    sun.position.set(4000, 6000, 2500);
    scene.add(sun);
    scene.add(new THREE.GridHelper(6000, 12, 0x2a3138, 0x1c2229));

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 900, 0);
    controls.update();

    const modelGroup = new THREE.Group();
    scene.add(modelGroup);
    sceneRef.current = { scene, camera, controls, modelGroup };

    const onResize = () => {
      const w = container.clientWidth;
      const h = Math.max(container.clientHeight, 1);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    let disposed = false;
    renderer.setAnimationLoop(() => {
      if (disposed) return;
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      disposed = true;
      window.removeEventListener("resize", onResize);
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

        // Frame the model: aim the orbit target at its bounding-box centre.
        const box = new THREE.Box3().setFromObject(model);
        const centre = box.getCenter(new THREE.Vector3());
        ctx.controls.target.copy(centre);
        ctx.controls.update();

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
