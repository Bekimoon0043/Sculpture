// The Designer Workspace viewport — the Phase 2 viewport grown into an
// instrument a designer can work IN, not just look at:
//
//   - click an element to select it (raycast -> element id via node names)
//   - per-element hide / solo, driven by the scene panel
//   - per-element material tint (visual identification, not a render claim)
//   - a measurement tool: two clicks on the model, distance in mm
//   - a section plane on X/Y/Z with a live offset
//   - camera poses that can be captured and re-applied (saved views)
//   - a PNG snapshot of the current frame (history-strip thumbnails)
//
// ADR-020 still governs: every camera plane, the grid and the sun are
// derived from the loaded model's bounding box, never hardcoded. The GLB
// arrives in METRES (OCCT converts from mm) — the measurement tool
// multiplies by 1000 to report millimetres, the project's canonical unit.
//
// Selection depends on the backend naming each element's GLB node with its
// element_id. Matching is tolerant (exact id, else id prefix on the node or
// an ancestor) because exporters append suffixes to deduplicate node names.

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { frameCameraToObject } from "../viewport/framing";

export interface CameraPose {
  position: [number, number, number];
  target: [number, number, number];
}

export interface SectionState {
  axis: "x" | "y" | "z";
  /** 0..1 across the model's bounding box on that axis. */
  offset: number;
}

export interface MeasureResult {
  distance_mm: number;
  a: [number, number, number];
  b: [number, number, number];
}

export type StandardView =
  | "front" | "back" | "right" | "left" | "top" | "bottom";

export interface WorkspaceViewportHandle {
  getCameraPose(): CameraPose | null;
  applyCameraPose(pose: CameraPose): void;
  frameAll(): void;
  /** Frame one element's built meshes (Blender numpad-period). */
  frameSelected(elementId: string): void;
  /** Snap to an axis view (Blender numpad 1/3/7 and shifted opposites). */
  applyStandardView(view: StandardView): void;
  /** Orthographic ⇄ perspective (Blender numpad 5). Returns the new mode. */
  toggleProjection(): "persp" | "ortho";
  /** PNG data URL of the current frame, rendered fresh at capture time. */
  snapshot(width?: number): string | null;
}

/** Camera directions per standard view, in the viewport's Y-up world (the
 *  GLB arrives Y-up from OCCT). Top/bottom need a non-collinear up vector. */
const VIEW_DIRS: Record<StandardView, [THREE.Vector3, THREE.Vector3]> = {
  front: [new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 1, 0)],
  back: [new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 1, 0)],
  right: [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0)],
  left: [new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 1, 0)],
  top: [new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, -1)],
  bottom: [new THREE.Vector3(0, -1, 0), new THREE.Vector3(0, 0, 1)],
};

/** Axis gizmo dots: world axis, view it snaps to, label, colour class. */
const GIZMO_AXES: Array<{
  axis: THREE.Vector3;
  view: StandardView;
  label: string;
  cls: string;
}> = [
  { axis: new THREE.Vector3(1, 0, 0), view: "right", label: "X", cls: "gx" },
  { axis: new THREE.Vector3(-1, 0, 0), view: "left", label: "", cls: "gx neg" },
  { axis: new THREE.Vector3(0, 1, 0), view: "top", label: "Y", cls: "gy" },
  { axis: new THREE.Vector3(0, -1, 0), view: "bottom", label: "", cls: "gy neg" },
  { axis: new THREE.Vector3(0, 0, 1), view: "front", label: "Z", cls: "gz" },
  { axis: new THREE.Vector3(0, 0, -1), view: "back", label: "", cls: "gz neg" },
];

interface WorkspaceViewportProps {
  reloadToken: number;
  glbUrl: (cacheBuster: number) => string;
  /** Ids the document knows — the node-name index only maps to these. */
  elementIds: string[];
  selectedId: string | null;
  onSelect: (elementId: string | null) => void;
  hiddenIds: Set<string>;
  soloId: string | null;
  /** element id -> CSS hex colour, from the material swatch assignment. */
  tints: Record<string, string>;
  measureMode: boolean;
  onMeasure: (result: MeasureResult | null) => void;
  section: SectionState | null;
  onModelRendered: () => void;
  onLoadError: (message: string) => void;
}

/** Ancestor-walking element lookup. Exporters may suffix node names
 *  (basin_01, basin_01_1, ...), so exact match first, then prefix. */
function elementIdOf(
  object: THREE.Object3D,
  ids: string[],
  idSet: Set<string>
): string | null {
  let node: THREE.Object3D | null = object;
  while (node) {
    if (idSet.has(node.name)) return node.name;
    for (const id of ids) {
      if (node.name.startsWith(id)) return id;
    }
    node = node.parent;
  }
  return null;
}

const SELECT_EMISSIVE = new THREE.Color(0xb98a2f); // brand amber

export default forwardRef<WorkspaceViewportHandle, WorkspaceViewportProps>(
  function WorkspaceViewport(
    {
      reloadToken,
      glbUrl,
      elementIds,
      selectedId,
      onSelect,
      hiddenIds,
      soloId,
      tints,
      measureMode,
      onMeasure,
      section,
      onModelRendered,
      onLoadError,
    },
    ref
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const labelRef = useRef<HTMLDivElement>(null);
    const gizmoRef = useRef<HTMLDivElement>(null);
    const ctxRef = useRef<{
      scene: THREE.Scene;
      camera: THREE.PerspectiveCamera;
      /** Orthographic twin — Blender numpad-5. The perspective camera stays
       *  the source of truth for POSE; the ortho camera mirrors it. */
      ortho: THREE.OrthographicCamera;
      projection: "persp" | "ortho";
      renderer: THREE.WebGLRenderer;
      controls: OrbitControls;
      modelGroup: THREE.Group;
      sun: THREE.DirectionalLight;
      grid: THREE.GridHelper;
      /** element id -> the meshes that belong to it (cloned materials). */
      byElement: Map<string, THREE.Mesh[]>;
      modelBox: THREE.Box3 | null;
      measureGroup: THREE.Group;
      measurePoints: THREE.Vector3[];
      measureMid: THREE.Vector3 | null;
    } | null>(null);
    // Latest interaction props, readable from long-lived event handlers.
    const propsRef = useRef({ measureMode, elementIds, onSelect, onMeasure });
    propsRef.current = { measureMode, elementIds, onSelect, onMeasure };

    // ------------------------------------------------------------------ setup
    useEffect(() => {
      const container = containerRef.current;
      if (!container) return;

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0x101418);

      const camera = new THREE.PerspectiveCamera(
        45,
        container.clientWidth / Math.max(container.clientHeight, 1),
        1,
        100000
      );
      camera.position.set(3500, 2800, 3500);
      // The ortho twin's frustum is (re)derived from the perspective pose on
      // every sync — these initial planes are placeholders like the persp
      // camera's own (ADR-020: everything re-derives from the model bounds).
      const ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, 1, 100000);

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.setSize(container.clientWidth, container.clientHeight);
      renderer.localClippingEnabled = true; // section plane
      container.appendChild(renderer.domElement);

      scene.add(new THREE.HemisphereLight(0xffffff, 0x30363d, 1.1));
      const sun = new THREE.DirectionalLight(0xffffff, 2.0);
      sun.position.set(4000, 6000, 2500);
      scene.add(sun);
      scene.add(sun.target);
      const grid = new THREE.GridHelper(6000, 12, 0x2a3138, 0x1c2229);
      scene.add(grid);

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.target.set(0, 900, 0);
      // Blender hands: MMB orbits too (LMB drag still orbits — browser
      // convention stays). RMB pans; Shift+MMB pans while Shift is down.
      controls.mouseButtons = {
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.ROTATE,
        RIGHT: THREE.MOUSE.PAN,
      };
      const onShift = (e: KeyboardEvent) => {
        controls.mouseButtons.MIDDLE =
          e.shiftKey ? THREE.MOUSE.PAN : THREE.MOUSE.ROTATE;
      };
      window.addEventListener("keydown", onShift);
      window.addEventListener("keyup", onShift);
      controls.update();

      const modelGroup = new THREE.Group();
      scene.add(modelGroup);
      const measureGroup = new THREE.Group();
      scene.add(measureGroup);

      ctxRef.current = {
        scene,
        camera,
        ortho,
        projection: "persp",
        renderer,
        controls,
        modelGroup,
        sun,
        grid,
        byElement: new Map(),
        modelBox: null,
        measureGroup,
        measurePoints: [],
        measureMid: null,
      };

      const onResize = () => {
        const w = container.clientWidth;
        const h = Math.max(container.clientHeight, 1);
        if (w === 0) return;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        const ctx = ctxRef.current;
        if (ctx) syncOrtho(ctx);
        renderer.setSize(w, h);
      };
      const observer = new ResizeObserver(onResize);
      observer.observe(container);
      requestAnimationFrame(onResize);

      // --- picking. Click-vs-orbit disambiguation: a click that moved more
      // than a few pixels was a drag; selecting on it fights the orbit.
      const raycaster = new THREE.Raycaster();
      const down = new THREE.Vector2();
      const onPointerDown = (e: PointerEvent) => down.set(e.clientX, e.clientY);
      const onPointerUp = (e: PointerEvent) => {
        if (e.button !== 0) return;
        if (down.distanceTo(new THREE.Vector2(e.clientX, e.clientY)) > 5) return;
        const ctx = ctxRef.current;
        if (!ctx) return;
        const rect = renderer.domElement.getBoundingClientRect();
        const ndc = new THREE.Vector2(
          ((e.clientX - rect.left) / rect.width) * 2 - 1,
          -((e.clientY - rect.top) / rect.height) * 2 + 1
        );
        raycaster.setFromCamera(
          ndc,
          ctx.projection === "ortho" ? ctx.ortho : ctx.camera
        );
        const visible: THREE.Object3D[] = [];
        ctx.modelGroup.traverse((o) => {
          if ((o as THREE.Mesh).isMesh && o.visible) visible.push(o);
        });
        const hits = raycaster
          .intersectObjects(visible, false)
          // A section plane hides geometry visually; a pick through the
          // clipped half must not select what the plane has cut away.
          .filter((h) => clippedIn(ctx.renderer, h.point));
        const p = propsRef.current;
        if (p.measureMode) {
          if (hits.length === 0) return;
          addMeasurePoint(ctx, hits[0].point.clone(), labelRef.current, p.onMeasure);
          return;
        }
        if (hits.length === 0) {
          p.onSelect(null);
          return;
        }
        const idSet = new Set(p.elementIds);
        p.onSelect(elementIdOf(hits[0].object, p.elementIds, idSet));
      };
      renderer.domElement.addEventListener("pointerdown", onPointerDown);
      renderer.domElement.addEventListener("pointerup", onPointerUp);

      // Axis-gizmo dots are plain DOM, positioned every frame from the
      // camera quaternion — no React re-render in the hot loop.
      const gizmoDots = gizmoRef.current
        ? Array.from(gizmoRef.current.querySelectorAll<HTMLButtonElement>(".gizmo-dot"))
        : [];
      const gizmoV = new THREE.Vector3();
      const gizmoQ = new THREE.Quaternion();

      let disposed = false;
      renderer.setAnimationLoop(() => {
        if (disposed) return;
        const ctx = ctxRef.current;
        if (!ctx) return;
        const cam = ctx.projection === "ortho" ? ctx.ortho : ctx.camera;
        controls.update();
        renderer.render(scene, cam);
        const label = labelRef.current;
        // The measurement label is an HTML overlay; keep it pinned to the
        // midpoint of the measured segment in screen space.
        if (label) {
          if (ctx.measureMid) {
            const v = ctx.measureMid.clone().project(cam);
            const w = renderer.domElement.clientWidth;
            const h = renderer.domElement.clientHeight;
            label.style.display = v.z < 1 ? "block" : "none";
            label.style.left = `${((v.x + 1) / 2) * w}px`;
            label.style.top = `${((1 - v.y) / 2) * h}px`;
          } else {
            label.style.display = "none";
          }
        }
        if (gizmoDots.length === GIZMO_AXES.length) {
          gizmoQ.copy(cam.quaternion).invert();
          const R = 34; // px orbit radius inside the widget
          for (let i = 0; i < GIZMO_AXES.length; i++) {
            gizmoV.copy(GIZMO_AXES[i].axis).applyQuaternion(gizmoQ);
            const dot = gizmoDots[i];
            dot.style.transform =
              `translate(${gizmoV.x * R}px, ${-gizmoV.y * R}px)`;
            // Toward-viewer dots draw on top and full-strength.
            dot.style.zIndex = String(10 + Math.round(gizmoV.z * 9));
            dot.style.opacity = gizmoV.z > 0 ? "1" : "0.45";
          }
        }
      });

      return () => {
        disposed = true;
        observer.disconnect();
        window.removeEventListener("keydown", onShift);
        window.removeEventListener("keyup", onShift);
        renderer.domElement.removeEventListener("pointerdown", onPointerDown);
        renderer.domElement.removeEventListener("pointerup", onPointerUp);
        controls.dispose();
        renderer.dispose();
        container.removeChild(renderer.domElement);
        ctxRef.current = null;
      };
    }, []);

    // ------------------------------------------------------------------ load
    useEffect(() => {
      const ctx = ctxRef.current;
      if (!ctx) return;
      let cancelled = false;

      const loader = new GLTFLoader();
      loader.load(
        glbUrl(reloadToken),
        (gltf) => {
          if (cancelled) return;
          disposeGroup(ctx.modelGroup);
          ctx.modelGroup.clear();
          const model = gltf.scene;

          // Index meshes by element and give every element its OWN material
          // instance — tint, selection emissive and visibility are
          // per-element, and GLB materials are shared by default.
          ctx.byElement = new Map();
          const ids = propsRef.current.elementIds;
          const idSet = new Set(ids);
          model.traverse((obj) => {
            if (!(obj as THREE.Mesh).isMesh) return;
            const mesh = obj as THREE.Mesh;
            mesh.geometry.computeVertexNormals();
            const id = elementIdOf(mesh, ids, idSet);
            const mat = (Array.isArray(mesh.material)
              ? mesh.material[0]
              : mesh.material) as THREE.MeshStandardMaterial;
            mesh.material = mat.clone();
            if (id) {
              const list = ctx.byElement.get(id) ?? [];
              list.push(mesh);
              ctx.byElement.set(id, list);
            }
          });
          ctx.modelGroup.add(model);
          clearMeasurement(ctx, labelRef.current, propsRef.current.onMeasure);

          const { box, centre, radius } = frameCameraToObject(
            ctx.camera,
            ctx.controls,
            model
          );
          if (ctx.projection === "ortho") syncOrtho(ctx);
          ctx.modelBox = box;

          ctx.scene.remove(ctx.grid);
          ctx.grid.geometry.dispose();
          (ctx.grid.material as THREE.Material).dispose();
          const grid = new THREE.GridHelper(radius * 6, 12, 0x2a3138, 0x1c2229);
          grid.position.y = box.min.y - radius * 0.02;
          ctx.scene.add(grid);
          ctx.grid = grid;

          ctx.sun.position.set(
            centre.x + radius * 4,
            centre.y + radius * 6,
            centre.z + radius * 2.5
          );
          ctx.sun.target.position.copy(centre);
          ctx.sun.target.updateMatrixWorld();

          restyle(); // re-apply selection/tints/visibility to the new nodes
          applySection();

          requestAnimationFrame(() => {
            if (!cancelled) onModelRendered();
          });
        },
        undefined,
        (err) => {
          if (cancelled) return;
          onLoadError(
            err instanceof Error ? err.message : "failed to load the GLB"
          );
        }
      );
      return () => {
        cancelled = true;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [glbUrl, reloadToken]);

    // ----------------------------------------------- styling (sel/tint/vis)
    const restyle = () => {
      const ctx = ctxRef.current;
      if (!ctx) return;
      for (const [id, meshes] of ctx.byElement) {
        const hidden =
          soloId !== null ? id !== soloId : hiddenIds.has(id);
        const tint = tints[id];
        for (const mesh of meshes) {
          mesh.visible = !hidden;
          const mat = mesh.material as THREE.MeshStandardMaterial;
          if (tint) mat.color.set(tint);
          mat.emissive.set(
            id === selectedId ? SELECT_EMISSIVE : 0x000000
          );
          mat.emissiveIntensity = id === selectedId ? 0.35 : 0;
        }
      }
    };
    useEffect(restyle, [selectedId, hiddenIds, soloId, tints, reloadToken]);

    // ------------------------------------------------------------- section
    const applySection = () => {
      const ctx = ctxRef.current;
      if (!ctx) return;
      let planes: THREE.Plane[] = [];
      if (section && ctx.modelBox) {
        const box = ctx.modelBox;
        const axis = section.axis;
        const min = box.min[axis];
        const max = box.max[axis];
        const at = min + (max - min) * section.offset;
        // Normal points toward -axis: geometry ABOVE the plane is clipped,
        // which reads as "slide the cut down through the model".
        const normal = new THREE.Vector3(
          axis === "x" ? -1 : 0,
          axis === "y" ? -1 : 0,
          axis === "z" ? -1 : 0
        );
        planes = [new THREE.Plane(normal, at)];
      }
      ctx.renderer.clippingPlanes = planes;
    };
    useEffect(applySection, [section, reloadToken]);

    // ----------------------------------------------------------- measure off
    useEffect(() => {
      const ctx = ctxRef.current;
      if (!ctx) return;
      if (!measureMode) {
        clearMeasurement(ctx, labelRef.current, propsRef.current.onMeasure);
      }
    }, [measureMode]);

    // ------------------------------------------------------------ imperative
    const applyStandardView = (view: StandardView) => {
      const ctx = ctxRef.current;
      if (!ctx) return;
      const [dir, up] = VIEW_DIRS[view];
      const target = ctx.controls.target;
      const dist =
        ctx.projection === "ortho"
          ? ctx.ortho.position.distanceTo(target) / ctx.ortho.zoom
          : ctx.camera.position.distanceTo(target);
      ctx.camera.up.copy(up);
      ctx.camera.position.copy(target).addScaledVector(dir, dist);
      ctx.camera.lookAt(target);
      if (ctx.projection === "ortho") syncOrtho(ctx);
      ctx.controls.update();
    };

    useImperativeHandle(ref, (): WorkspaceViewportHandle => ({
      getCameraPose() {
        const ctx = ctxRef.current;
        if (!ctx) return null;
        const cam = ctx.projection === "ortho" ? ctx.ortho : ctx.camera;
        return {
          position: cam.position.toArray() as [number, number, number],
          target: ctx.controls.target.toArray() as [number, number, number],
        };
      },
      applyCameraPose(pose: CameraPose) {
        const ctx = ctxRef.current;
        if (!ctx) return;
        ctx.camera.position.set(...pose.position);
        ctx.controls.target.set(...pose.target);
        if (ctx.projection === "ortho") syncOrtho(ctx);
        ctx.controls.update();
      },
      frameAll() {
        const ctx = ctxRef.current;
        if (!ctx) return;
        frameCameraToObject(ctx.camera, ctx.controls, ctx.modelGroup);
        if (ctx.projection === "ortho") syncOrtho(ctx);
      },
      frameSelected(elementId: string) {
        const ctx = ctxRef.current;
        const meshes = ctx?.byElement.get(elementId);
        if (!ctx || !meshes || meshes.length === 0) return;
        const box = new THREE.Box3();
        for (const mesh of meshes) box.expandByObject(mesh);
        if (box.isEmpty()) return;
        const centre = box.getCenter(new THREE.Vector3());
        const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1e-6);
        // Keep the CURRENT view direction — framing an element must not
        // also yank the designer to a canned angle.
        const dir = ctx.camera.position
          .clone()
          .sub(ctx.controls.target)
          .normalize();
        const tanHalf = Math.tan(THREE.MathUtils.degToRad(ctx.camera.fov / 2));
        const fit = Math.min(tanHalf, tanHalf * ctx.camera.aspect);
        const distance = radius / (0.7 * fit);
        ctx.camera.position.copy(centre).addScaledVector(dir, distance);
        ctx.camera.near = Math.max(radius / 1000, 1e-9);
        ctx.camera.far = distance + radius * 50;
        ctx.camera.updateProjectionMatrix();
        ctx.controls.target.copy(centre);
        if (ctx.projection === "ortho") syncOrtho(ctx);
        ctx.controls.update();
      },
      applyStandardView,
      toggleProjection() {
        const ctx = ctxRef.current;
        if (!ctx) return "persp";
        if (ctx.projection === "persp") {
          syncOrtho(ctx);
          ctx.controls.object = ctx.ortho;
          ctx.projection = "ortho";
        } else {
          // Fold the ortho zoom back into a perspective distance so the
          // model keeps its apparent size across the switch.
          const target = ctx.controls.target;
          const dir = ctx.ortho.position.clone().sub(target);
          const dist = dir.length() / ctx.ortho.zoom;
          ctx.camera.up.copy(ctx.ortho.up);
          ctx.camera.position
            .copy(target)
            .addScaledVector(dir.normalize(), dist);
          ctx.camera.quaternion.copy(ctx.ortho.quaternion);
          ctx.controls.object = ctx.camera;
          ctx.projection = "persp";
        }
        ctx.controls.update();
        return ctx.projection;
      },
      snapshot(width = 320) {
        const ctx = ctxRef.current;
        if (!ctx) return null;
        // Render a fresh frame right before reading pixels — without
        // preserveDrawingBuffer the last presented frame is not readable.
        ctx.renderer.render(
          ctx.scene,
          ctx.projection === "ortho" ? ctx.ortho : ctx.camera
        );
        const full = ctx.renderer.domElement;
        if (full.width === 0 || full.height === 0) return null;
        const scale = width / full.width;
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = Math.max(1, Math.round(full.height * scale));
        const g = canvas.getContext("2d");
        if (!g) return null;
        g.drawImage(full, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL("image/png");
      },
    }));

    return (
      <div ref={containerRef} className="viewport-canvas">
        <div ref={labelRef} className="measure-label" style={{ display: "none" }} />
        <div
          ref={gizmoRef}
          className="axis-gizmo"
          title="Click an axis to snap the view (1/3/7 front-right-top, Shift for opposites)"
        >
          {GIZMO_AXES.map((a) => (
            <button
              key={a.view}
              type="button"
              className={`gizmo-dot ${a.cls}`}
              aria-label={`${a.view} view`}
              onClick={() => applyStandardView(a.view)}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    );
  }
);

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

/** Mirror the perspective camera's pose into the ortho twin and size its
 *  frustum so the model keeps its apparent size at the orbit target. */
function syncOrtho(ctx: {
  camera: THREE.PerspectiveCamera;
  ortho: THREE.OrthographicCamera;
  controls: { target: THREE.Vector3 };
}) {
  const { camera, ortho, controls } = ctx;
  const dist = camera.position.distanceTo(controls.target);
  const halfH = dist * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const halfW = halfH * camera.aspect;
  ortho.left = -halfW;
  ortho.right = halfW;
  ortho.top = halfH;
  ortho.bottom = -halfH;
  // Ortho near planes may go negative — geometry behind the pose still
  // renders, which is what makes axis views usable without clip fiddling.
  ortho.near = -camera.far;
  ortho.far = camera.far;
  ortho.zoom = 1;
  ortho.position.copy(camera.position);
  ortho.quaternion.copy(camera.quaternion);
  ortho.up.copy(camera.up);
  ortho.updateProjectionMatrix();
}

/** True when the point survives the renderer's active clipping planes. */
function clippedIn(renderer: THREE.WebGLRenderer, point: THREE.Vector3): boolean {
  for (const plane of renderer.clippingPlanes) {
    if (plane.distanceToPoint(point) < 0) return false;
  }
  return true;
}

function disposeGroup(group: THREE.Group) {
  group.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh) {
      const mesh = obj as THREE.Mesh;
      mesh.geometry.dispose();
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const m of mats) m.dispose();
    }
  });
}

function addMeasurePoint(
  ctx: NonNullable<React.MutableRefObject<any>["current"]>,
  point: THREE.Vector3,
  label: HTMLDivElement | null,
  onMeasure: (r: MeasureResult | null) => void
) {
  // Third click starts a new measurement.
  if (ctx.measurePoints.length >= 2) clearMeasurement(ctx, label, onMeasure);
  ctx.measurePoints.push(point);

  const radius = ctx.modelBox
    ? ctx.modelBox.getSize(new THREE.Vector3()).length() / 200
    : 0.02;
  const marker = new THREE.Mesh(
    new THREE.SphereGeometry(radius, 12, 12),
    new THREE.MeshBasicMaterial({ color: 0xb98a2f, depthTest: false })
  );
  marker.position.copy(point);
  marker.renderOrder = 999;
  ctx.measureGroup.add(marker);

  if (ctx.measurePoints.length === 2) {
    const [a, b] = ctx.measurePoints;
    const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
    const line = new THREE.Line(
      geo,
      new THREE.LineBasicMaterial({ color: 0xb98a2f, depthTest: false })
    );
    line.renderOrder = 999;
    ctx.measureGroup.add(line);
    ctx.measureMid = a.clone().add(b).multiplyScalar(0.5);
    // Scene units are METRES (OCCT converts on export); report mm.
    const mm = a.distanceTo(b) * 1000;
    if (label) label.textContent = formatMm(mm);
    onMeasure({
      distance_mm: mm,
      a: a.toArray() as [number, number, number],
      b: b.toArray() as [number, number, number],
    });
  }
}

function clearMeasurement(
  ctx: NonNullable<React.MutableRefObject<any>["current"]>,
  label: HTMLDivElement | null,
  onMeasure: (r: MeasureResult | null) => void
) {
  for (const child of [...ctx.measureGroup.children]) {
    const mesh = child as THREE.Mesh;
    mesh.geometry?.dispose();
    (mesh.material as THREE.Material | undefined)?.dispose?.();
    ctx.measureGroup.remove(child);
  }
  ctx.measurePoints = [];
  ctx.measureMid = null;
  if (label) label.style.display = "none";
  onMeasure(null);
}

export function formatMm(mm: number): string {
  return mm >= 1000
    ? `${(mm / 1000).toFixed(3)} m`
    : `${mm.toFixed(1)} mm`;
}
