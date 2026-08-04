// Camera framing from the model's own bounding box — SCALE-INDEPENDENT
// (ADR-020). Root cause of the 2026-08-04 "empty viewport" incident:
// build123d's export_gltf declares the XDE length unit (mm), and OCCT's
// RWGltf_CafWriter converts coordinates to METRES (glTF 2.0 spec,
// coordinate-system-and-units) — the 2600 mm cascade arrives 2.6 units
// wide, a sub-pixel speck at the old hardcoded millimetre camera. Framing
// from the bounding box works at ANY scale, which Phase 6 requires:
// primitives will vary hugely in size. Nothing here assumes units.

import * as THREE from "three";

export interface FramingResult {
  box: THREE.Box3;
  centre: THREE.Vector3;
  size: THREE.Vector3;
  radius: number;
  distance: number;
}

export function frameCameraToObject(
  camera: THREE.PerspectiveCamera,
  controls: { target: THREE.Vector3; update: () => void },
  object: THREE.Object3D
): FramingResult {
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) {
    // Degenerate load (no geometry): frame a unit region at the origin
    // rather than produce NaN/Inf camera planes.
    box.setFromCenterAndSize(
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(1, 1, 1)
    );
  }
  const centre = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.length() / 2, 1e-6);

  // Fit the bounding sphere to ~70% of the SHORTER view dimension, so the
  // whole model is visible at any aspect ratio without manual zooming:
  //   visible height at distance d = 2 d tan(fov/2)
  //   visible width  at distance d = 2 d tan(fov/2) aspect
  // want 2r <= 0.7 * min(visible height, visible width).
  const tanHalfFov = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const fit = Math.min(tanHalfFov, tanHalfFov * camera.aspect);
  const distance = radius / (0.7 * fit);

  const direction = new THREE.Vector3(1, 0.75, 1).normalize();
  camera.position.copy(centre).addScaledVector(direction, distance);
  camera.near = Math.max(radius / 1000, 1e-9);
  camera.far = distance + radius * 50;
  camera.updateProjectionMatrix();

  controls.target.copy(centre);
  controls.update();

  return { box, centre, size, radius, distance };
}
