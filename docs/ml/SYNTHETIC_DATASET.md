# Procedural Synthetic Pipe-Joint Dataset Architecture

## 1. Overview & Commercial Rationale

While third-party academic datasets (such as Sewer-ML) remain under permission review, JointInspect leverages an internal, commercially unencumbered procedural synthetic dataset generation engine (`training/synthetic/`).

Unlike generic generative AI models that fabricate pixel hallucinations without physical ground truth, the JointInspect Synthetic Generator is **fully parametric and geometrically deterministic**:
- Every pixel coordinate maps directly to a 3D cylindrical pipe model.
- Physical pipe diameters, socket thicknesses, and joint clearances are explicitly specified in millimetres.
- Ground truth segmentation masks, inner lumen masks, outer joint masks, and 16-bit depth maps are derived directly from the mathematical model.

---

## 2. Parametric Variations

### Materials
1. **PVC**: High-smoothness polymer, white/light-grey base, specular CCTV sheen.
2. **Concrete**: Textured aggregate, micro-pit noise, matte diffuse reflection.
3. **Metal**: Ductile cast iron, low albedo, subtle oxidation/corrosion mottling.
4. **Vitrified Clay**: Terracotta red-brown, medium roughness, organic porosity.

### Geometry & Defect Taxonomy
- `NORMAL_JOINT`: Concentric spigot and bell socket, gap $\le 1.0\text{ mm}$.
- `OPEN_JOINT`: Axial joint displacement with clear annular gap ($2.0\text{ mm} - 15.0\text{ mm}$).
- `DISPLACED_JOINT`: Angular deflection and eccentric offset producing asymmetric circumferential gap profiles.
- `DAMAGED_JOINT`: Spalling, fractured socket edges, cracks, and structural deformation.
- `INTRUDING_SEAL`: Protruding rubber gasket extrusion into pipe lumen.
- `DEPOSITS_OBSTACLES`: Invert siltation, sediment line, roots, and partial blockages.

### Environmental & Optical Simulation
- **CCTV Spotlight**: Inverse-square falloff with adjustable beam angle.
- **Water & Invert Sheen**: Specular puddle reflection and standing water level.
- **Atmospheric Haze**: Turbid fog simulation in unventilated sewer conditions.
- **Lens Artifacts**: Optical dust specks, bilateral blur, and sensor noise.

---

## 3. Output Schema per Sample

Each sample exports:
- `JI-SYN-XXXXX.png`: 3-channel RGB image.
- `JI-SYN-XXXXX_mask.png`: Binary segmentation mask (joint gap / anomaly).
- `JI-SYN-XXXXX_inner_mask.png`: Pipe lumen interior mask.
- `JI-SYN-XXXXX_outer_mask.png`: Outer bell/spigot boundary mask.
- `JI-SYN-XXXXX_depth.png`: 16-bit depth map (depth in millimetres).
- `JI-SYN-XXXXX_normal.png`: Surface normal map (RGB normal vector encoding).
- `JI-SYN-XXXXX.json`: Comprehensive geometric metadata, camera matrices ($K, R, T$), and 72-point circumferential gap profile.

---

## 4. Verification & Metrology Testing

All generated synthetic samples are subjected to automated verification in `training/synthetic/validate_dataset.py`:
- Bounding box containment.
- Mask and image dimensional alignment.
- Zero-blank render check.
- **OpenCV Ground-Truth Comparison**: The deterministic OpenCV circular measurement engine (`measure_circular_gap`) runs against the rendered image and compares against the exact ground truth.
- Metrics generated: `MAE_mm`, `RMSE_mm`, `bias_mm`, and accuracy within $0.5\text{ mm}$, $1.0\text{ mm}$, and $2.0\text{ mm}$.

> **CRITICAL REPORTING NOTICE**: All metrics derived from this synthetic dataset are strictly designated:
> **`SYNTHETIC_GEOMETRIC_GROUND_TRUTH`**
> They must never be conflated with or presented as empirical real-world field accuracy.
