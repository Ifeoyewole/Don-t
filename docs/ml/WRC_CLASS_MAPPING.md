# WRc Sewer Classification to JointInspect Taxonomy Mapping

**Specification Version**: 1.0.0 (Beta Baseline)  
**Model Identity**: `wrc-inceptionresnetv2-baseline-v1`  
**Upstream Dataset**: WRc Sewer Defect Classification Dataset  
**Authority Level**: `ADVISORY_BASELINE` (Non-Authoritative)  

---

## 1. Principles of Conservative Mapping

JointInspect is an engineering-grade pipe joint inspection system. Its primary mission is the verification of joint integrity, displacement, and seal geometry against calibrated engineering tolerances.

The external WRc InceptionResNetV2 model was trained on general closed-circuit television (CCTV) sewer defects from the UK Water Research Centre (WRc) Manual of Sewer Condition Classification (MSCC). The WRc taxonomy covers broad sewer structural, operational, and network features, many of which do not map 1:1 onto pipe joint condition states.

To prevent category confusion and false positives:
1. **Conservative Mapping**: Only map classes where there is clear engineering correspondence.
2. **Four Allowed Outcomes**:
   - `DIRECT`: Exact 1:1 conceptual match with a JointInspect condition class.
   - `GROUPED`: Multiple related defect modes mapped into a broader JointInspect category (e.g. Broken, Crack, Fracture -> DAMAGED_JOINT).
   - `UNMAPPED`: Legitimate sewer features that are not pipe joint defect conditions (e.g. Connection, Junction, Water). Mapped to `null`.
   - `AMBIGUOUS`: Observations whose relationship to joint integrity is ambiguous or undetermined (e.g. Line of Sewer). Mapped to `null`.
3. **Preservation of Raw Evidence**: The raw WRc class index, raw class name, and model score are always preserved in the response schema regardless of mapping outcome.
4. **Zero Tolerance Override**: The external classifier cannot override deterministic OpenCV gap measurements or engineering tolerances.

---

## 2. Complete Taxonomy Mapping Matrix

| Index | WRc Name | WRc Code | JointInspect Target | Mapping Status | Conf. Weight | Engineering Rationale |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **0** | `Broken` | `B` | `DAMAGED_JOINT` | `GROUPED` | 0.85 | Pipe barrel fracture or broken socket represents structural damage at or adjacent to the joint seam. |
| **1** | `Connection` | `CN` | `null` | `UNMAPPED` | 0.00 | Lateral or service connection is a pipe feature, not an inspectable joint defect. |
| **2** | `Crack` | `CK` | `DAMAGED_JOINT` | `GROUPED` | 0.90 | Longitudinal or circumferential cracking directly threatens joint watertightness. |
| **3** | `Defective Connection` | `CND` | `null` | `AMBIGUOUS` | 0.00 | Defective lateral connection may project into pipe bore but is ambiguous relative to the circumferential joint ring. |
| **4** | `Deformed` | `D` | `DAMAGED_JOINT` | `GROUPED` | 0.80 | Cross-sectional out-of-round deformation distorts joint spigot and socket sealing profile. |
| **5** | `Deposit` | `DE` | `DEPOSITS_OBSTACLES` | `DIRECT` | 0.95 | Direct conceptual alignment with JointInspect operational deposits, silt, and encrustation. |
| **6** | `Displaced Joint` | `JD` | `DISPLACED_JOINT` | `DIRECT` | 0.98 | Direct 1:1 match for JointInspect displaced or misaligned pipe joint classification. |
| **7** | `Fracture` | `F` | `DAMAGED_JOINT` | `GROUPED` | 0.90 | Severe material fracture compromises joint structural capacity. |
| **8** | `Hole` | `H` | `DAMAGED_JOINT` | `GROUPED` | 0.85 | Wall void or perforation in pipe wall adjacent to joint line. |
| **9** | `Junction` | `J` | `null` | `UNMAPPED` | 0.00 | Sewer junction node is a mainline network junction, not a joint anomaly. |
| **10** | `Line of Sewer` | `LL` | `null` | `AMBIGUOUS` | 0.00 | Alignment survey reference code with no specific defect significance. |
| **11** | `Roots` | `R` | `DEPOSITS_OBSTACLES` | `GROUPED` | 0.90 | Vegetation and root mass intrusions obstruct the joint and seal region. |
| **12** | `Water` | `W` | `null` | `UNMAPPED` | 0.00 | Standing water, invert flow level, or infiltration is a hydraulic condition, not a joint defect. |

---

## 3. Summary Statistics

- **Total WRc Classes**: 13
- **Direct 1:1 Mappings**: 2 (`Deposit`, `Displaced Joint`)
- **Grouped Mappings**: 6 (`Broken`, `Crack`, `Deformed`, `Fracture`, `Hole`, `Roots`)
- **Unmapped Classes**: 3 (`Connection`, `Junction`, `Water`)
- **Ambiguous Classes**: 2 (`Defective Connection`, `Line of Sewer`)
- **Total Mapped to JointInspect Concepts**: 8 / 13 (61.5%)
- **Total Safe Null Mappings**: 5 / 13 (38.5%)
