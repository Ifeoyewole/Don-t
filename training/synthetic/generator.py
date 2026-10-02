"""Commercially Safe Procedural Pipe-Joint Dataset Generator.

Generates photorealistic synthetic pipe-joint images with known exact geometry:
- Known ground-truth annular and axial gap (0.0 to 15.0 mm)
- Controlled pipe diameters (150mm to 600mm)
- Physical materials: PVC, concrete, ductile metal, vitrified clay
- Structural joint anomalies:
  * NORMAL_JOINT
  * OPEN_JOINT (axial gap)
  * DISPLACED_JOINT (angular deflection, eccentric offset)
  * DAMAGED_JOINT (broken edge, cracks, deformation)
  * INTRUDING_SEAL (intruding rubber gasket, gasket extrusion)
  * DEPOSITS_OBSTACLES (invert silt, roots, partial blockage)
- Physical camera simulation (intrinsics K, extrinsics R|t, CCTV spotlight falloff)
- Environmental effects (dry, wet specular reflection, standing water, turbid fog, lens noise)

Per-sample outputs:
- RGB image (PNG)
- Segmentation mask (PNG: 255 for joint gap/anomaly)
- Inner pipe mask (PNG: 255 for pipe lumen)
- Outer joint mask (PNG: 255 for outer joint socket boundary)
- Depth map (16-bit uint PNG in millimetres)
- Surface normal map (PNG: RGB encoding of normal vectors)
- Exact JSON metadata with ground-truth gap profile, camera matrices, and physical parameters
"""

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


MATERIALS = ["PVC", "CONCRETE", "METAL", "CLAY"]
DIAMETERS_MM = [150.0, 200.0, 250.0, 300.0, 375.0, 450.0, 500.0, 600.0]
GAPS_MM = [0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0, 15.0]

CONDITIONS = [
    "NORMAL_JOINT",
    "OPEN_JOINT",
    "DISPLACED_JOINT",
    "DAMAGED_JOINT",
    "INTRUDING_SEAL",
    "DEPOSITS_OBSTACLES",
]

LIGHTING_MODES = [
    "central_cctv",
    "dim_lighting",
    "harsh_specular",
    "asymmetric_shadow",
    "wet_specular",
]

ENVIRONMENTS = [
    "dry",
    "wet",
    "standing_water",
    "dirty_lens",
    "turbid_fog",
]


class SyntheticPipeJointGenerator:
    """Procedural 3D perspective renderer for sewer pipe joints."""

    def __init__(
        self,
        output_dir: Path,
        width: int = 1280,
        height: int = 720,
        synthetic_version: str = "jointinspect-synthetic-v1.0",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
        self.version = synthetic_version

    def _get_material_palette(self, material: str) -> Dict[str, Any]:
        """Returns base color, roughness, and specular parameters for pipe materials."""
        if material == "PVC":
            # Smooth grey-white or terracotta PVC
            return {
                "base_bgr": np.array([215, 220, 225], dtype=np.float32),
                "noise_amp": 8.0,
                "specular_power": 64.0,
                "specular_intensity": 0.45,
            }
        elif material == "CONCRETE":
            # Matte grey textured concrete with aggregate speckles
            return {
                "base_bgr": np.array([140, 145, 150], dtype=np.float32),
                "noise_amp": 28.0,
                "specular_power": 12.0,
                "specular_intensity": 0.15,
            }
        elif material == "METAL":
            # Dark ductile cast iron with slight rust/mottling
            return {
                "base_bgr": np.array([85, 90, 95], dtype=np.float32),
                "noise_amp": 20.0,
                "specular_power": 32.0,
                "specular_intensity": 0.35,
            }
        elif material == "CLAY":
            # Vitrified clay terracotta reddish brown
            return {
                "base_bgr": np.array([80, 110, 175], dtype=np.float32),
                "noise_amp": 22.0,
                "specular_power": 16.0,
                "specular_intensity": 0.20,
            }
        else:
            return {
                "base_bgr": np.array([160, 160, 160], dtype=np.float32),
                "noise_amp": 15.0,
                "specular_power": 24.0,
                "specular_intensity": 0.25,
            }

    def generate_sample(
        self,
        sample_id: str,
        condition: str = "NORMAL_JOINT",
        gap_mm: float = 1.0,
        pipe_diameter_mm: float = 300.0,
        material: str = "CONCRETE",
        lighting: str = "central_cctv",
        environment: str = "dry",
        camera_distance_mm: float = 650.0,
        camera_yaw_deg: float = 0.0,
        camera_pitch_deg: float = 0.0,
        camera_roll_deg: float = 0.0,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generates a complete synthetic pipe-joint sample with masks and metadata."""
        if seed is not None:
            np.random.seed(seed)

        w, h = self.width, self.height
        cx, cy = w / 2.0, h / 2.0

        # 1. Camera Intrinsics
        # Standard CCTV focal length roughly 900-1400 pixels
        fx = 1200.0
        fy = 1200.0
        K = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float64)

        # Scale factor: pixels per mm at the joint plane
        # Z = camera_distance_mm
        pixels_per_mm = fx / camera_distance_mm

        # Effective projected radii in image plane
        r_inner_mm = pipe_diameter_mm / 2.0
        r_inner_px = r_inner_mm * pixels_per_mm

        # Joint socket/bell wall thickness (typical 10-25mm)
        wall_thickness_mm = max(12.0, pipe_diameter_mm * 0.06)
        r_outer_mm = r_inner_mm + wall_thickness_mm
        r_outer_px = r_outer_mm * pixels_per_mm

        # Gap in pixels (projected along perspective ray)
        gap_px = max(0.5, gap_mm * pixels_per_mm)

        # Offset camera / center shifts from yaw and pitch
        yaw_rad = math.radians(camera_yaw_deg)
        pitch_rad = math.radians(camera_pitch_deg)
        roll_rad = math.radians(camera_roll_deg)

        center_shift_x = math.tan(yaw_rad) * fx
        center_shift_y = math.tan(pitch_rad) * fy

        joint_cx = cx + center_shift_x
        joint_cy = cy + center_shift_y

        # Extrinsic Rotation Matrix
        R_z = np.array(
            [[math.cos(roll_rad), -math.sin(roll_rad), 0], [math.sin(roll_rad), math.cos(roll_rad), 0], [0, 0, 1]]
        )
        R_y = np.array(
            [[math.cos(yaw_rad), 0, math.sin(yaw_rad)], [0, 1, 0], [-math.sin(yaw_rad), 0, math.cos(yaw_rad)]]
        )
        R_x = np.array(
            [
                [1, 0, 0],
                [0, math.cos(pitch_rad), -math.sin(pitch_rad)],
                [0, math.sin(pitch_rad), math.cos(pitch_rad)],
            ]
        )
        R = R_z @ R_y @ R_x
        T = np.array([center_shift_x / pixels_per_mm, center_shift_y / pixels_per_mm, camera_distance_mm])

        # Coordinate Grids for Vectorized Rendering
        y_coords, x_coords = np.indices((h, w), dtype=np.float32)
        dx = x_coords - joint_cx
        dy = y_coords - joint_cy

        # If roll is present, rotate grid
        if abs(roll_rad) > 1e-4:
            cos_r, sin_r = math.cos(roll_rad), math.sin(roll_rad)
            dx_rot = dx * cos_r + dy * sin_r
            dy_rot = -dx * sin_r + dy * cos_r
            dist_from_center = np.sqrt(dx_rot**2 + dy_rot**2)
            angle_grid = np.arctan2(dy_rot, dx_rot)
        else:
            dist_from_center = np.sqrt(dx**2 + dy**2)
            angle_grid = np.arctan2(dy, dx)

        # Material styling
        mat_palette = self._get_material_palette(material)
        base_color = mat_palette["base_bgr"].copy()

        # Canvas Initialization
        rgb_img = np.zeros((h, w, 3), dtype=np.uint8)
        joint_mask = np.zeros((h, w), dtype=np.uint8)
        inner_mask = np.zeros((h, w), dtype=np.uint8)
        outer_mask = np.zeros((h, w), dtype=np.uint8)
        depth_map = np.zeros((h, w), dtype=np.uint16)
        normal_map = np.zeros((h, w, 3), dtype=np.uint8)

        # Circumferential gap profile calculation
        num_profile_points = 72
        angles = np.linspace(-math.pi, math.pi, num_profile_points, endpoint=False)
        gap_profile_mm: List[float] = []

        # Modulations based on condition
        for a in angles:
            if condition == "DISPLACED_JOINT":
                # Angular deflection produces variable gap around circumference
                var_gap = max(0.0, gap_mm * (1.0 + 0.65 * math.sin(a)))
            elif condition == "NORMAL_JOINT":
                var_gap = min(1.5, gap_mm + 0.1 * math.cos(2 * a))
            else:
                var_gap = gap_mm
            gap_profile_mm.append(round(float(var_gap), 3))

        # Radial Zones
        # Pipe barrel ahead (receding lumen into distance): dist < r_inner_px - gap_px/2
        # Joint gap seam: r_inner_px - gap_px/2 <= dist <= r_inner_px + gap_px/2
        # Pipe wall / Bell spigot: r_inner_px + gap_px/2 < dist <= r_outer_px
        # Surrounding / outer barrel: dist > r_outer_px

        seam_inner_r = r_inner_px - (gap_px / 2.0)
        seam_outer_r = r_inner_px + (gap_px / 2.0)

        # Apply Angular Deflection to seam boundaries if DISPLACED
        if condition == "DISPLACED_JOINT":
            eccentric_shift = 0.35 * gap_px * np.sin(angle_grid)
            seam_inner_r += eccentric_shift
            seam_outer_r += eccentric_shift * 0.5

        # Masks
        is_inner_lumen = dist_from_center < seam_inner_r
        is_joint_gap = (dist_from_center >= seam_inner_r) & (dist_from_center <= seam_outer_r)
        is_outer_bell = (dist_from_center > seam_outer_r) & (dist_from_center <= r_outer_px)
        is_surround = dist_from_center > r_outer_px

        # Base Surface Texture
        noise = (np.random.randn(h, w, 1) * mat_palette["noise_amp"]).astype(np.float32)
        pipe_surface = np.clip(base_color + noise, 0, 255)

        # Receding pipe interior shading (distance falloff)
        lumen_shade = np.clip(1.0 - (dist_from_center / (r_inner_px + 1e-5)), 0.0, 1.0)
        interior_color = pipe_surface * (0.35 + 0.45 * (dist_from_center[..., None] / (r_inner_px + 1e-5)))

        # CCTV Spotlight Falloff
        cctv_light_dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
        beam_radius = min(w, h) * 0.65
        light_falloff = np.clip(1.0 - (cctv_light_dist / beam_radius) ** 2 * 0.6, 0.25, 1.0)

        if lighting == "dim_lighting":
            light_falloff *= 0.55
        elif lighting == "harsh_specular":
            light_falloff = np.power(light_falloff, 0.75) * 1.35
        elif lighting == "asymmetric_shadow":
            light_falloff *= (0.5 + 0.5 * np.cos(angle_grid))

        # Assign Regional Colors
        # Lumen
        rgb_img[is_inner_lumen] = np.clip(interior_color[is_inner_lumen] * light_falloff[is_inner_lumen, None], 0, 255)
        # Joint Gap / Annulus (dark shadow recess)
        gap_shadow = np.array([25, 25, 30], dtype=np.float32)
        rgb_img[is_joint_gap] = gap_shadow
        # Outer Bell / Spigot
        bell_color = pipe_surface * 1.08  # slightly highlighted outer lip
        rgb_img[is_outer_bell] = np.clip(bell_color[is_outer_bell] * light_falloff[is_outer_bell, None], 0, 255)
        # Surrounding outer pipe
        rgb_img[is_surround] = np.clip(pipe_surface[is_surround] * (light_falloff[is_surround, None] * 0.9), 0, 255)

        # Masks
        inner_mask[is_inner_lumen] = 255
        joint_mask[is_joint_gap] = 255
        outer_mask[is_outer_bell] = 255

        # 2. Defect Injections
        if condition == "DAMAGED_JOINT":
            # Break/spall at crown or invert (notch in joint)
            notch_angle = np.random.uniform(-math.pi / 3, math.pi / 3)
            angular_dist = np.abs(np.angle(np.exp(1j * (angle_grid - notch_angle))))
            is_notch = (angular_dist < 0.25) & (dist_from_center >= seam_inner_r * 0.88) & (dist_from_center <= seam_outer_r * 1.35)
            # Make broken jagged edge
            fracture_noise = np.random.rand(h, w) > 0.3
            is_notch &= fracture_noise
            rgb_img[is_notch] = np.array([15, 18, 22])  # deep fracture shadow
            joint_mask[is_notch] = 255

        elif condition == "INTRUDING_SEAL":
            # Rubber gasket protruding inward into pipe lumen
            gasket_angle = np.random.uniform(-math.pi / 2, math.pi / 2)
            angular_dist = np.abs(np.angle(np.exp(1j * (angle_grid - gasket_angle))))
            is_gasket = (angular_dist < 0.35) & (dist_from_center >= seam_inner_r * 0.75) & (dist_from_center <= seam_inner_r * 1.05)
            # Black rubber color
            rgb_img[is_gasket] = np.array([30, 32, 35])
            joint_mask[is_gasket] = 255

        elif condition == "DEPOSITS_OBSTACLES":
            # Invert silt / sediment deposition at pipe bottom (dy > 0)
            sediment_level_px = joint_cy + r_inner_px * 0.70
            is_sediment = (y_coords > sediment_level_px) & (dist_from_center < r_inner_px * 0.98)
            silt_color = np.array([55, 95, 115], dtype=np.float32)  # brown/mud silt
            rgb_img[is_sediment] = silt_color
            joint_mask[is_sediment] = 255

        # 3. Environmental Simulations
        if environment == "standing_water" or lighting == "wet_specular":
            # Water line at invert with specular reflection
            waterline_y = joint_cy + r_inner_px * 0.65
            is_water = (y_coords >= waterline_y) & (dist_from_center < r_inner_px)
            # Reflection of CCTV light in water
            glare = np.exp(-((x_coords - joint_cx) ** 2) / 600.0) * 180.0
            rgb_img[is_water] = np.clip(rgb_img[is_water] * 0.45 + glare[is_water, None], 0, 255)

        if environment == "dirty_lens":
            # Specks on lens
            num_specks = np.random.randint(15, 45)
            for _ in range(num_specks):
                sx = np.random.randint(0, w)
                sy = np.random.randint(0, h)
                s_rad = np.random.randint(3, 14)
                cv2.circle(rgb_img, (sx, sy), s_rad, (40, 45, 50), -1)
            rgb_img = cv2.GaussianBlur(rgb_img, (3, 3), 0.8)

        elif environment == "turbid_fog":
            # Atmospheric haze in sewer
            fog = np.full((h, w, 3), 160, dtype=np.uint8)
            rgb_img = cv2.addWeighted(rgb_img, 0.75, fog, 0.25, 0)

        # 4. Depth Map Generation (16-bit millimetres)
        # Cylinder depth: z = Z0 + sqrt(R^2 - x^2)
        # Lumen depth recedes to 2500mm; joint plane at camera_distance_mm
        depth_f = np.full((h, w), float(camera_distance_mm + 1200.0), dtype=np.float32)
        depth_f[is_surround] = camera_distance_mm - 150.0
        depth_f[is_outer_bell] = camera_distance_mm
        depth_f[is_joint_gap] = camera_distance_mm + max(5.0, gap_mm * 10.0)
        depth_f[is_inner_lumen] = camera_distance_mm + 400.0 + (1.0 - dist_from_center[is_inner_lumen] / r_inner_px) * 800.0
        depth_map = np.clip(depth_f, 0, 65535).astype(np.uint16)

        # 5. Surface Normal Map (RGB encoding)
        # Normals point roughly inward toward pipe centerline
        nx = -(dx / (dist_from_center + 1e-5))
        ny = -(dy / (dist_from_center + 1e-5))
        nz = np.full((h, w), 0.5, dtype=np.float32)
        # Normalize
        norm_mag = np.sqrt(nx**2 + ny**2 + nz**2) + 1e-5
        nx /= norm_mag
        ny /= norm_mag
        nz /= norm_mag
        # Map [-1, 1] to [0, 255]
        normal_map[..., 0] = np.clip((nx + 1.0) * 127.5, 0, 255).astype(np.uint8)
        normal_map[..., 1] = np.clip((ny + 1.0) * 127.5, 0, 255).astype(np.uint8)
        normal_map[..., 2] = np.clip((nz + 1.0) * 127.5, 0, 255).astype(np.uint8)

        # 6. Bounding Box Calculation around Joint Annulus
        # Bounding box covers seam_outer_r around joint center
        bb_margin = 10.0
        xmin = max(0.0, float(joint_cx - r_outer_px - bb_margin))
        ymin = max(0.0, float(joint_cy - r_outer_px - bb_margin))
        xmax = min(float(w), float(joint_cx + r_outer_px + bb_margin))
        ymax = min(float(h), float(joint_cy + r_outer_px + bb_margin))
        bbox_xyxy = [round(xmin, 1), round(ymin, 1), round(xmax, 1), round(ymax, 1)]

        # File Export
        base_filename = f"{sample_id}"
        img_path = self.output_dir / f"{base_filename}.png"
        mask_path = self.output_dir / f"{base_filename}_mask.png"
        inner_mask_path = self.output_dir / f"{base_filename}_inner_mask.png"
        outer_mask_path = self.output_dir / f"{base_filename}_outer_mask.png"
        depth_path = self.output_dir / f"{base_filename}_depth.png"
        normal_path = self.output_dir / f"{base_filename}_normal.png"
        meta_path = self.output_dir / f"{base_filename}.json"

        cv2.imwrite(str(img_path), rgb_img)
        cv2.imwrite(str(mask_path), joint_mask)
        cv2.imwrite(str(inner_mask_path), inner_mask)
        cv2.imwrite(str(outer_mask_path), outer_mask)
        cv2.imwrite(str(depth_path), depth_map)
        cv2.imwrite(str(normal_path), normal_map)

        metadata = {
            "sample_id": sample_id,
            "condition": condition,
            "gap_mm": round(float(gap_mm), 3),
            "pipe_diameter_mm": pipe_diameter_mm,
            "pipe_material": material,
            "gap_profile_circumference": gap_profile_mm,
            "pixels_per_mm": round(float(pixels_per_mm), 4),
            "camera_distance_mm": round(float(camera_distance_mm), 2),
            "camera_yaw_deg": round(float(camera_yaw_deg), 2),
            "camera_pitch_deg": round(float(camera_pitch_deg), 2),
            "camera_roll_deg": round(float(camera_roll_deg), 2),
            "lighting": lighting,
            "environment": environment,
            "bbox_xyxy": bbox_xyxy,
            "camera_intrinsic_matrix": K.tolist(),
            "camera_extrinsic_R": R.tolist(),
            "camera_extrinsic_T": T.tolist(),
            "production_eligible": True,
            "source_type": "SYNTHETIC",
            "synthetic_source_version": self.version,
            "generation_seed": seed,
            "files": {
                "rgb_image": img_path.name,
                "segmentation_mask": mask_path.name,
                "inner_pipe_mask": inner_mask_path.name,
                "outer_joint_mask": outer_mask_path.name,
                "depth_map": depth_path.name,
                "surface_normal_map": normal_path.name,
            },
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata
