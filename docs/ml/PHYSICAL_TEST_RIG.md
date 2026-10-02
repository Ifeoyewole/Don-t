# Controlled Physical Test Rig Specification & Metrology Standard

## 1. Objective & Role in Empirical Verification

To satisfy the **Zero-Guessing Measurement Invariant**, JointInspect requires real-world physical verification grounded in genuine physical measurement instruments.

While synthetic geometric ground truth verifies algorithm mathematical correctness under idealized projection, **empirical accuracy metrics (MAE, RMSE, bias, 95% error bounds) may only be published when backed by physical test rig ground truth**.

---

## 2. Hardware Architecture & Test Bench Layout

The physical test rig consists of:
1. **Pipe Specimen Mounts**:
   - Interchangeable pipe sections: Vitrified Clay, Reinforced Concrete, Ductile Iron, PVC.
   - Standard internal diameters: $150\text{ mm}$, $225\text{ mm}$, $300\text{ mm}$, $450\text{ mm}$.
2. **Precision Linear Micrometer Stage**:
   - Allows calibrated axial separation of bell and spigot joint faces from $0.0\text{ mm}$ to $25.0\text{ mm}$.
   - Adjustable angular deflection gimballing from $0.0^\circ$ to $8.0^\circ$.
3. **Calibrated Physical Instruments**:
   - Certified Class 1 Feeler Gauges ($0.05\text{ mm}$ increments).
   - Mitutoyo Digital Depth Micrometer / Vernier Caliper (Resolution: $0.01\text{ mm}$, NIST-traceable).
   - Precision machined step blocks ($1.00\text{ mm}$, $2.00\text{ mm}$, $5.00\text{ mm}$, $10.00\text{ mm}$).
4. **Optical CCTV Crawler Mount**:
   - Rigid camera dolly mounted along pipe centerline.
   - Known standoff distances: $400\text{ mm}$, $600\text{ mm}$, $800\text{ mm}$, $1200\text{ mm}$.
   - Controlled LED illumination with lux metering.

---

## 3. Ground-Truth Data Logging Schema

Every physical test rig capture records the following 8 attributes in `training/data/physical_ground_truth/ground_truth_records.csv`:

```csv
image_id,ground_truth_gap_mm,instrument,instrument_resolution_mm,pipe_diameter_mm,camera_distance_mm,camera_angle_deg,lighting_lux
RIG-001-01,0.00,FEELER_GAUGE_0.05,0.05,300,650,0.0,450
RIG-001-02,1.00,VERNIER_CALIPER_MITUTOYO,0.01,300,650,0.0,450
RIG-001-03,2.00,PRECISION_STEP_BLOCK,0.01,300,650,0.0,450
RIG-001-04,3.00,VERNIER_CALIPER_MITUTOYO,0.01,300,650,0.0,450
RIG-001-05,5.00,PRECISION_STEP_BLOCK,0.01,300,650,0.0,450
RIG-001-06,10.00,PRECISION_STEP_BLOCK,0.01,300,650,0.0,450
```

---

## 4. Empirical Metrology Reporting Rules

- Real-world MAE, RMSE, bias, and $\pm 1.0\text{ mm}$ compliance percentages must be calculated strictly against physical test rig rows where `instrument_resolution_mm <= 0.05`.
- No simulated or heuristic values may ever be reported under physical ground truth.
- When physical records do not yet exist for a diameter or material, status must be explicitly reported as `PENDING_PHYSICAL_BENCH_TEST`.
