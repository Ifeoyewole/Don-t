# Improve Gap Calculation for GoPro MAX 360 Pipe Joint Photos

Improve the gap measurement pipeline to accurately calculate pipe joint gaps from **GoPro MAX 5.6K 360° camera** images (reframed perspective crops), using AI-enhanced image processing that improves visibility **without distorting or changing the actual content**.

## Camera: GoPro MAX

- **Resolution**: 5.6K 360° (16MP), 1440p @ 60fps video
- **Image format**: Photos reaching the app are **reframed perspective crops** exported from the 360° footage — confirmed by examining all 8 test images
- **Characteristics**: Moderate wide-angle barrel distortion, low-light conditions (underground manholes), motion blur risk, variable angles

## Real Image Analysis

From the 8 test images in `public/`:

| Image | Type | Gap Visible? | Current Pipeline Issue |
|-------|------|-------------|----------------------|
| test 1 | Close-up yellow pipe from side | ✅ Dark horizontal line | Close-up detector should catch this, but low light reduces contrast |
| test 2 | Down into concrete manhole | ✅ Ring around pipe opening | Good for circle detection, but pipe is off-center |
| test 3 | Down into manhole (shifted) | ✅ Ring visible | Pipe is in upper portion — `detectOpeningCenter` may miss it (searches only top 72%) |
| test 4 | Blurry close-up joint | ⚠️ Barely visible | Heavy motion blur destroys edges — enhancement must sharpen without adding noise |
| test 5 | Angled yellow pipe opening | ✅ Elliptical opening | **HoughCircles will fail** — opening is an ellipse, not a circle |
| test 6 | Extreme close-up clay pipe gap | ✅ Very clear vertical gap | Best case for vertical gap detector, but current `mmPerPixel` scales are rough estimates |
| test 7 | Centered concrete pipe | ✅ Clear ring gap | Good for circle detection — the ideal case |
| WhatsApp | Perfect centered concrete joint | ✅ Beautiful thin dark ring | This is the ideal image — should produce highest confidence |

---

## Proposed Changes

### 1. Image Enhancement — Sharpen Edges for GoPro MAX Without Distortion

#### [MODIFY] [cvMeasurement.ts](file:///c:/Users/toyew/Documents/Don-t-/src/lib/cvMeasurement.ts) — `enhanceImageData()`

Replace the current global contrast/exposure approach (lines 82–102) with a measurement-focused enhancement:

```
Current (problematic):
- Flat exposure lift up to 42 → shifts all pixels, can move edge boundaries by 1–2px
- Fixed contrast multiplier 1.08–1.18 → washes out subtle gaps in bright areas
- No noise handling → GoPro MAX in dark manholes produces noisy images

New approach:
- CLAHE-style local contrast: divide image into 8×8 tiles, equalise histogram per tile
  → reveals detail in dark manhole shadows without washing out bright pipe surfaces
- Unsharp mask (radius 2, amount 0.4): sharpens existing edges without moving them
  → makes the gap boundary crisper for the CV detector
- Bilateral-style edge-preserving denoise: smooth noise while keeping sharp edges
  → handles GoPro MAX noise in low-light underground conditions
```

The key principle: **sharpen contrast at edges that already exist, never create or shift edge positions.**

#### [MODIFY] [imageEnhancement.ts](file:///c:/Users/toyew/Documents/Don-t-/src/lib/imageEnhancement.ts) — `enhancePixels()`

Apply the same measurement-focused enhancement here (this is the version sent to the AI for review). Currently even more aggressive than `cvMeasurement.ts` (contrast 1.24, exposure lift up to 54).

---

### 2. CV Measurement Engine — Handle GoPro MAX Image Types

#### [MODIFY] [cvMeasurement.ts](file:///c:/Users/toyew/Documents/Don-t-/src/lib/cvMeasurement.ts)

**a) Higher resolution processing**
- `MAX_PROCESS_DIMENSION`: `720` → `1200`
- GoPro MAX delivers 16MP images. At 720px, a 5mm gap on a 225mm pipe is only ~3.2px. At 1200px it's ~5.3px — significantly more measurable.

**b) More angular samples**
- `ANGLE_STEPS`: `48` → `72` (5° steps instead of 7.5°)
- More radial samples = better median gap value, especially when debris/dirt partially obscures some angles.

**c) Ellipse detection for angled views (NEW)**
- Add `findEllipseGapMeasurement()` — when HoughCircles fails, fit an ellipse to the detected opening. GoPro MAX photos from the manhole often show the pipe at an angle (test 5), making the opening elliptical.
- Use OpenCV's `fitEllipse` on the dark opening contour.
- Convert the ellipse axes to the known pipe diameter for mm-per-pixel calibration.

**d) Adaptive thresholding**
- Replace the single global `brightThreshold` with per-ray local adaptive thresholds.
- For each radial ray, compute the threshold from the local min/max within a sliding window along the ray profile.
- This handles the uneven lighting common in GoPro MAX manhole shots (one side in shadow, other side lit by torch).

**e) Gradient-magnitude edge detection**
- In `measureGapFromKnownCircle()`, instead of checking `profile[radius] >= rayBrightThreshold`, compute the **Sobel gradient magnitude** along each ray.
- The gap boundary is where the gradient peaks — this is invariant to absolute brightness and handles the variable lighting from the GoPro MAX.

**f) Sub-pixel edge refinement**
- After finding the integer-pixel gap boundary, interpolate between adjacent pixels using gradient values for sub-pixel accuracy.
- Improves accuracy by ~0.3–0.5mm on typical images.

**g) Remove fake fallback**
- Delete `deriveGapMm()` (line 61–66) which generates a fake measurement from a filename hash.
- Replace with proper result: `originalGapMm: 0`, `status: 'REVIEW'`, clear message telling the inspector to retake.

**h) Widen opening center search area**
- In `detectOpeningCenter()`, change `endY` from `height * 0.72` to `height * 0.82`.
- Test images 2 and 3 show pipes that extend below the 72% mark — the current code misses them.

---

### 3. AI Integration — Better Gemini Analysis for Pipe Gaps

#### [MODIFY] [aiMeasurement.ts](file:///c:/Users/toyew/Documents/Don-t-/src/services/aiMeasurement.ts)

- Send the **best 3 image variants** to Gemini instead of just the first one (full-enhanced + center-zoom + the strip containing the detected joint area).
- `createEnhancedImageVariants()` already produces 7 variants but only `variants[0]` is used currently.

#### [MODIFY] [vite.config.ts](file:///c:/Users/toyew/Documents/Don-t-/vite.config.ts) and [ai-measure-photo.ts](file:///c:/Users/toyew/Documents/Don-t-/netlify/functions/ai-measure-photo.ts)

Improve the Gemini prompt:
- Tell the AI this is from a **GoPro MAX 360° camera** (reframed crop) so it can account for the wide-angle distortion
- Ask it to **identify the two pipe edges** on either side of the gap specifically
- Ask it to **measure the gap in pixels first**, then convert to mm using the known pipe diameter
- Ask it to evaluate **image quality** (blur score, exposure, focus) and factor that into confidence
- Ask it to flag when the image is too blurry for reliable measurement (test 4 scenario)

---

### 4. Measurement Fusion — Better CV+AI Combination

#### [MODIFY] [measurementFusion.ts](file:///c:/Users/toyew/Documents/Don-t-/src/lib/measurementFusion.ts)

- When CV and AI disagree by >2mm but both have confidence ≥0.5, use **weighted average** based on confidence scores instead of picking one
- When CV fails but AI succeeds with confidence ≥ 0.6, trust AI even when `pipeOpeningVisible` is false (the close-up gap views like test 6 are valid)
- Add **consistency boost**: when CV and AI pixel-based gap estimates agree within 20%, boost combined confidence by 0.08

---

## File Change Summary

| File | Change Type | What Changes |
|------|------------|--------------|
| [cvMeasurement.ts](file:///c:/Users/toyew/Documents/Don-t-/src/lib/cvMeasurement.ts) | MODIFY | New enhancement, higher res, more angles, ellipse detection, adaptive thresholds, gradient edges, sub-pixel, remove fake fallback, wider search |
| [imageEnhancement.ts](file:///c:/Users/toyew/Documents/Don-t-/src/lib/imageEnhancement.ts) | MODIFY | Replace aggressive global enhancement with CLAHE + unsharp mask |
| [aiMeasurement.ts](file:///c:/Users/toyew/Documents/Don-t-/src/services/aiMeasurement.ts) | MODIFY | Send 3 image variants instead of 1 |
| [vite.config.ts](file:///c:/Users/toyew/Documents/Don-t-/vite.config.ts) | MODIFY | Improved Gemini prompt for GoPro MAX + pixel-first measurement |
| [ai-measure-photo.ts](file:///c:/Users/toyew/Documents/Don-t-/netlify/functions/ai-measure-photo.ts) | MODIFY | Same prompt improvement for production |
| [measurementFusion.ts](file:///c:/Users/toyew/Documents/Don-t-/src/lib/measurementFusion.ts) | MODIFY | Weighted averaging, relaxed AI trust, consistency boost |

---

## Decisions Made (from previous open questions)

> [!NOTE]
> **Processing time**: Increasing resolution from 720→1200 is worth the ~2.5x time increase. The GoPro MAX delivers 16MP — throwing away 99.7% of pixels at 720px is too aggressive. At 1200px we keep more gap detail while staying under 5 seconds per image.

> [!NOTE]
> **AI cost**: Sending 3 image variants instead of 1 triples Gemini token usage. This is acceptable because accurate gap measurement is the core product value.

> [!NOTE]
> **Fake fallback**: `deriveGapMm()` will be replaced with `originalGapMm: 0, status: 'REVIEW'`. A fake number derived from filename hashing is worse than no measurement — it misleads the inspector.

---

## Verification Plan

### Automated Tests
- Process all 8 test images (`test 1.jpeg` through `test 7.jpeg` + WhatsApp image) through the improved pipeline
- Compare measurements before and after on each image
- Verify enhanced images have identical pixel dimensions to originals (no geometric distortion)

### Manual Verification
- Run the dev server and upload the test images through the UI
- Verify overlay hints correctly mark the detected gap edges on each image type
- Confirm the blurry image (test 4) gets a low confidence score and retake suggestion
- Confirm the angled elliptical pipe (test 5) is now detected where it previously failed
- Confirm the perfect WhatsApp image gets the highest confidence
