# WRc InceptionResNetV2 Pretrained Baseline Audit

**Audit Date**: October 4, 2026  
**Auditor**: Antigravity Machine Learning Quality & Assurance  
**Repository**: `alexgeorge13/WRc-Dataset-Classification`  
**Git Commit**: `7ac0b0f9edf430d43e5f180466e2e456d98fdfe7`  
**Model Identifier**: `wrc-inceptionresnetv2-baseline-v1`  
**Status**: `AUDITED_AND_VERIFIED`  

---

## 1. Executive Summary

This document presents the technical audit of the external sewer defect classification model repository:
`alexgeorge13/WRc-Dataset-Classification`.

The purpose of this integration into **JointInspect** (`Ifeoyewole/Don-t`) is to provide a genuine, real-sewer-trained **external classification baseline** (`ADVISORY_BASELINE`) to benchmark against JointInspect's experimental native candidate models (`seg-smoke-v1` and `cls-smoke-v1`).

> [!IMPORTANT]
> The WRc InceptionResNetV2 baseline is strictly **classification advisory**. It has **ZERO physical measurement authority** and **ZERO engineering tolerance authority**. Physical millimeter measurements remain exclusively governed by the calibrated OpenCV radial edge geometry engine.

---

## 2. Artifact & Provenance Verification

| Property | Value / Finding | Verification Method |
| :--- | :--- | :--- |
| **Source Repository** | `https://github.com/alexgeorge13/WRc-Dataset-Classification.git` | Cloned from upstream GitHub |
| **Source Commit** | `7ac0b0f9edf430d43e5f180466e2e456d98fdfe7` | `git rev-parse HEAD` |
| **Weights Path** | `trainedWRc_inceptionresnetv2_focalLoss/weights.h5` | Git LFS track |
| **Weights File Size** | `231,566,563 bytes` (~220.84 MB) | `Get-Item` (Not the ~134 B pointer) |
| **Weights SHA-256** | `42527d8c4d38e6113f079bcb007715a5476d39cd3cc327f4ba87269d3c7de253` | `Get-FileHash -Algorithm SHA256` |
| **LFS Metadata Match** | `PASS` (`42527d8c4d38e6113f079bcb007715a5476d39cd3cc327f4ba87269d3c7de253`) | `git lfs ls-files -l` |
| **Software License** | `MIT License` (Copyright (c) 2025 Alex George) | Verified `LICENSE` |
| **Weight Provenance** | `EXTERNAL_PRETRAINED / PENDING_COMMERCIAL_REVIEW` | Documented in `model_version.json` |
| **Dataset Source** | WRc Sewer Inspection Dataset (CCWI 2025 paper) | Verified `README.md` |

---

## 3. Model Architecture & Contract

### 3.1 Network Topology
- **Origin**: Exported from MATLAB Deep Learning Toolbox Converter for TensorFlow Models (10-Jul-2025 12:33:19).
- **Backbone**: InceptionResNetV2 with custom head:
  - Global average pooling (`layers.GlobalAveragePooling2D(keepdims=True)`)
  - Dropout 0.30 (`layers.Dropout(0.300000)`)
  - Flatten/Reshape (`layers.Reshape((-1,), name="new_fc_preFlatten1")`)
  - Dense 13 (`layers.Dense(13, name="new_fc_")`)
  - Softmax (`layers.Softmax()`)
- **Total Parameters**: ~54,336,493 parameters.

### 3.2 Input Contract
- **Input Tensor Name**: `input_1_unnormalized`
- **Input Shape**: `(None, 299, 299, 3)` (NHWC format)
- **Input Dtype**: `float32`
- **Pixel Value Range**: `[0.0, 255.0]` (unnormalized raw pixels)
- **Channel Order**: `RGB` (Standard PIL / TensorFlow image representation)
- **Built-in Normalization**: The model has an in-graph `keras.layers.Normalization(axis=(1,2,3), name="input_1_")` layer immediately following the input tensor. Its mean and variance are stored in `weights.h5`. The caller passes raw pixel values `[0, 255]`.

### 3.3 Preprocessing Pipeline
To match the original reference implementation in `testImageClassification.ipynb`:
1. Load image in **RGB** format (e.g. `PIL.Image.open(path).convert('RGB')` or OpenCV `cvtColor(cv2.COLOR_BGR2RGB)`).
2. Calculate aspect-preserving scale factor:
   $$\text{scale} = \min\left(\frac{299}{\text{width}}, \frac{299}{\text{height}}\right)$$
3. Resize image to $(w', h') = (\lfloor \text{width} \times \text{scale} \rfloor, \lfloor \text{height} \times \text{scale} \rfloor)$ using `LANCZOS` / bicubic resampling.
4. Create a black canvas `(299, 299, 3)` with value `(0, 0, 0)`.
5. Center the resized image onto the canvas:
   $$\text{paste\_x} = \frac{299 - w'}{2}, \quad \text{paste\_y} = \frac{299 - h'}{2}$$
6. Convert to `float32` array with shape `(1, 299, 299, 3)`.

### 3.4 Output Contract
- **Output Tensor Name**: `new_softmax`
- **Output Shape**: `(None, 13)`
- **Activation**: Softmax (sums to 1.0 across the 13 classes)
- **Score Interpretation**: Model probability distribution across 13 closed-set classes.

---

## 4. Class Taxonomy (13 Classes)

The exact class ordering established from `testImageClassification.ipynb` (Cell 6, line 664):

| Index | Class Name | UK WRc Code | JointInspect Concept | Mapping Status |
| :---: | :--- | :--- | :--- | :--- |
| **0** | `Broken` | `B` | `DAMAGED_JOINT` | `GROUPED` |
| **1** | `Connection` | `CN` | `null` | `UNMAPPED` |
| **2** | `Crack` | `CK` | `DAMAGED_JOINT` | `GROUPED` |
| **3** | `Defective Connection` | `CND` | `null` | `AMBIGUOUS` |
| **4** | `Deformed` | `D` | `DAMAGED_JOINT` | `GROUPED` |
| **5** | `Deposit` | `DE` | `DEPOSITS_OBSTACLES` | `DIRECT` |
| **6** | `Displaced Joint` | `JD` | `DISPLACED_JOINT` | `DIRECT` |
| **7** | `Fracture` | `F` | `DAMAGED_JOINT` | `GROUPED` |
| **8** | `Hole` | `H` | `DAMAGED_JOINT` | `GROUPED` |
| **9** | `Junction` | `J` | `null` | `UNMAPPED` |
| **10** | `Line of Sewer` | `LL` | `null` | `AMBIGUOUS` |
| **11** | `Roots` | `R` | `DEPOSITS_OBSTACLES` | `GROUPED` |
| **12** | `Water` | `W` | `null` | `UNMAPPED` |

---

## 5. Weights File Loading Caveat

The external `README.txt` specifies:
> `weights.h5` contains model weights in HDF5 format. This file is **not compatible** with `tensorflow.keras.models.load_model()`. The package defines `create_model()` in `model.py` and manually assigns weights using h5py in `loadWeights()` inside `__init__.py`.

Our integration respects this exact loading routine. Once weights are assigned into the Keras model, the model can be evaluated directly or exported to ONNX for low-latency runtime deployment.
