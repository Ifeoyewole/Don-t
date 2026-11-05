import type { InspectionImage, ProcessOptions } from '../types'

/**
 * A batch can contain different joint geometry, lateral views, and defect types.
 * Never copy a batch default into individual inspection images.
 */
export function resolveImageContext(image: InspectionImage, options?: ProcessOptions): ProcessOptions {
  return {
    ...options,
    jointType: image.jointType,
    operatorContext: image.operatorContext,
    geometrySelectionProvenance: image.geometrySelectionProvenance ?? 'LEGACY_DEFAULT',
  }
}

export function hasExplicitPhotoMode(image: InspectionImage): boolean {
  return image.analysisMode === 'EVIDENCE_ONLY' ||
    Boolean(image.jointType && image.geometrySelectionProvenance !== 'LEGACY_DEFAULT')
}
