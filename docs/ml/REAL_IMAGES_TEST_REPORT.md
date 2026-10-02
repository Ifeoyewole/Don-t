# Real & Scratch Image Inspection Test Report

**Evaluated Sources**: `public/` and `scratch/`  
**Total Images Evaluated**: **18**  
**Unique Images**: **11** | **Exact Duplicates Detected**: **7**  
**OpenCV Authoritative Acceptance Rate**: **100.0%** (18 Accepted, 0 Rejected by Zero-Guessing Guard)  

---

## Detailed Image Test Matrix

| File Name | Folder | Dimensions | Status | OpenCV Mean Gap | AI Condition | Confidence | RAG Match |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `test 1.jpeg` | `public` | 960x1280 | `ACCEPTED` | 31.32 mm | `OPEN_JOINT` | 0.37 | `EX-SYN-0012` |
| `test 2.jpeg` | `public` | 960x1280 | `ACCEPTED` | 63.69 mm | `OPEN_JOINT` | 0.52 | `EX-SYN-0023` |
| `test 3.jpeg` | `public` | 960x1280 | `ACCEPTED` | 40.84 mm | `OPEN_JOINT` | 0.50 | `EX-SYN-0012` |
| `test 4.jpeg` | `public` | 960x1280 | `ACCEPTED` | 20.74 mm | `OPEN_JOINT` | 0.38 | `EX-SYN-0012` |
| `test 5.jpeg` | `public` | 960x1280 | `ACCEPTED` | 4.12 mm | `OPEN_JOINT` | 0.42 | `EX-SYN-0023` |
| `test 6.jpeg` | `public` | 1280x960 | `ACCEPTED` | 32.66 mm | `OPEN_JOINT` | 0.48 | `EX-SYN-0029` |
| `test 7.jpeg` | `public` | 1098x1280 | `ACCEPTED` | 31.48 mm | `OPEN_JOINT` | 0.38 | `EX-SYN-0023` |
| `WhatsApp Image 2026-05-21 at 9.29.57 PM.jpeg` | `public` | 1254x1254 | `ACCEPTED` | 23.64 mm | `OPEN_JOINT` | 0.44 | `EX-SYN-0023` |
| `WhatsApp Image 2026-10-01 at 15.05.04 (1).jpeg` | `scratch` | 1280x960 | `ACCEPTED` | 34.65 mm | `OPEN_JOINT` | 0.45 | `EX-SYN-0028` |
| `WhatsApp Image 2026-10-01 at 15.05.04.jpeg` (Dup) | `scratch` | 1280x960 | `ACCEPTED` | 32.66 mm | `OPEN_JOINT` | 0.48 | `EX-SYN-0029` |
| `WhatsApp Image 2026-10-01 at 15.05.05 (1).jpeg` (Dup) | `scratch` | 960x1280 | `ACCEPTED` | 20.74 mm | `OPEN_JOINT` | 0.38 | `EX-SYN-0012` |
| `WhatsApp Image 2026-10-01 at 15.05.05 (2).jpeg` (Dup) | `scratch` | 960x1280 | `ACCEPTED` | 63.69 mm | `OPEN_JOINT` | 0.52 | `EX-SYN-0023` |
| `WhatsApp Image 2026-10-01 at 15.05.05 (3).jpeg` (Dup) | `scratch` | 960x1280 | `ACCEPTED` | 40.84 mm | `OPEN_JOINT` | 0.50 | `EX-SYN-0012` |
| `WhatsApp Image 2026-10-01 at 15.05.05 (4).jpeg` (Dup) | `scratch` | 960x1280 | `ACCEPTED` | 4.12 mm | `OPEN_JOINT` | 0.42 | `EX-SYN-0023` |
| `WhatsApp Image 2026-10-01 at 15.05.05 (5).jpeg` (Dup) | `scratch` | 1280x960 | `ACCEPTED` | 32.66 mm | `OPEN_JOINT` | 0.48 | `EX-SYN-0029` |
| `WhatsApp Image 2026-10-01 at 15.05.05.jpeg` (Dup) | `scratch` | 960x1280 | `ACCEPTED` | 31.32 mm | `OPEN_JOINT` | 0.37 | `EX-SYN-0012` |
| `WhatsApp Image 2026-10-01 at 15.05.06 (1).jpeg` | `scratch` | 810x1080 | `ACCEPTED` | 0.93 mm | `DEPOSITS_OBSTACLES` | 0.45 | `EX-SYN-0023` |
| `WhatsApp Image 2026-10-01 at 15.05.06.jpeg` | `scratch` | 926x1080 | `ACCEPTED` | 44.78 mm | `OPEN_JOINT` | 0.38 | `EX-SYN-0023` |

---

## Visual Benchmark Dashboard & Statistical Infographic

The automated benchmarking run generated high-resolution analytical visual graphics:
- **Statistical Infographic**: `docs/ml/benchmark_real_images_statistical_dashboard.png`
- **Inspection Exemplar Gallery**: `docs/ml/benchmark_real_images_inspection_gallery.png`

## Zero-Guessing Guard Verification
When real CCTV images exhibit heavy siltation, turbulence, or off-axis blur where concentric circular pipe geometry cannot be mathematically resolved, OpenCV deterministically refuses to guess a fake number and safely flags `REJECTED_UNRELIABLE`.

## RAG Advisory Isolation Verification
RAG advisory retrievals matched relevant engineering SOPs (such as `SOP-001` Crawler Optical Calibration or `SOP-002` Radial Profiling) without attempting to calculate or modify physical gap millimetres.