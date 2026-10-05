"""Stage A Synthetic Dataset Generation Runner (100 Images).

Generates a balanced 100-sample validation batch across:
- Materials: PVC, CONCRETE, METAL, CLAY
- Diameters: 150mm, 200mm, 250mm, 300mm, 375mm, 450mm, 500mm, 600mm
- Known Gaps: 0.0mm, 0.5mm, 1.0mm, 2.0mm, 3.0mm, 4.0mm, 5.0mm, 7.5mm, 10.0mm, 15.0mm
- Conditions: NORMAL_JOINT, OPEN_JOINT, DISPLACED_JOINT, DAMAGED_JOINT, INTRUDING_SEAL, DEPOSITS_OBSTACLES
- Lighting & Environmental variations
"""

import logging
from pathlib import Path
from training.synthetic.generator import (
    SyntheticPipeJointGenerator,
    CONDITIONS,
    DIAMETERS_MM,
    GAPS_MM,
    LIGHTING_MODES,
    MATERIALS,
    ENVIRONMENTS,
)
from training.synthetic.validate_dataset import validate_synthetic_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_stage_a")


def run_stage_a(output_dir: Path = Path("data/synthetic/stage_a"), num_samples: int = 100):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generator = SyntheticPipeJointGenerator(output_dir=output_dir, width=960, height=540)

    logger.info("Starting Stage A generation of %d synthetic samples...", num_samples)

    for i in range(num_samples):
        sample_id = f"JI-SYN-A{i+1:05d}"
        cond = CONDITIONS[i % len(CONDITIONS)]
        gap = GAPS_MM[i % len(GAPS_MM)]
        dia = DIAMETERS_MM[i % len(DIAMETERS_MM)]
        mat = MATERIALS[i % len(MATERIALS)]
        light = LIGHTING_MODES[i % len(LIGHTING_MODES)]
        env = ENVIRONMENTS[i % len(ENVIRONMENTS)]

        # If condition is NORMAL_JOINT, enforce small tight gap
        if cond == "NORMAL_JOINT":
            gap = min(1.0, gap)
        elif cond == "OPEN_JOINT":
            gap = max(3.0, gap)

        yaw = ((i * 7) % 21) - 10.0
        pitch = ((i * 5) % 17) - 8.0
        roll = ((i * 3) % 11) - 5.0

        generator.generate_sample(
            sample_id=sample_id,
            condition=cond,
            gap_mm=gap,
            pipe_diameter_mm=dia,
            material=mat,
            lighting=light,
            environment=env,
            camera_distance_mm=650.0 + ((i % 5) * 50.0),
            camera_yaw_deg=yaw,
            camera_pitch_deg=pitch,
            camera_roll_deg=roll,
            seed=42 + i,
        )

        if (i + 1) % 25 == 0:
            logger.info("Generated %d / %d samples...", i + 1, num_samples)

    logger.info("Stage A generation complete! Running validation...")
    val_report_path = output_dir / "synthetic_measurement_validation.json"
    report = validate_synthetic_dataset(output_dir, val_report_path)
    logger.info("Validation complete! MAE: %s mm, Within 1mm: %s%%",
                report["metrics"]["MAE_mm"], report["metrics"]["within_1mm_pct"])
    return report


if __name__ == "__main__":
    run_stage_a()
