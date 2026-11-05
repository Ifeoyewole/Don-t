import { describe, expect, it } from 'vitest'
import type { InspectionImage } from '../types'
import { hasExplicitPhotoMode, resolveImageContext } from './imageContext'

const photo = (data: Partial<InspectionImage>) => ({
  id: 'x', projectId: 'p', manholeId: 'm', fileName: 'photo.jpg',
  mimeType: 'image/jpeg', blobKey: 'b', orderIndex: 0,
  jointLabel: 'Joint 1', captureSource: 'upload', queueStatus: 'queued',
  createdAt: '2026-11-05', ...data,
} as InspectionImage)

describe('photo-specific geometry', () => {
  it('does not inherit the batch geometry', () => {
    const blank = photo({})
    const resolved = resolveImageContext(blank, { jointType: 'CIRCULAR_OPENING' })
    expect(resolved.jointType).toBeUndefined()
    expect(hasExplicitPhotoMode(blank)).toBe(false)
  })
  it('keeps distinct photo notes and geometry', () => {
    const a = resolveImageContext(photo({
      jointType: 'CIRCULAR_OPENING', operatorContext: 'Annular view',
      geometrySelectionProvenance: 'EVIDENCE_SUGGESTED',
    }), { jointType: 'VERTICAL_SEAM', operatorContext: 'Global note' })
    const c = resolveImageContext(photo({
      jointType: 'VERTICAL_SEAM', operatorContext: 'Vertical view',
      geometrySelectionProvenance: 'INSPECTOR_SELECTED',
    }))
    expect([a.jointType, c.jointType]).toEqual(['CIRCULAR_OPENING', 'VERTICAL_SEAM'])
    expect([a.operatorContext, c.operatorContext]).toEqual(['Annular view', 'Vertical view'])
  })
  it('keeps camera identity distinct across two photos', () => {
    const a = resolveImageContext(photo({
      cameraId: 'RIG-A', pipeDiameterMm: 900,
      jointType: 'CIRCULAR_OPENING', geometrySelectionProvenance: 'INSPECTOR_SELECTED',
    }), { cameraId: 'BATCH-CAMERA', pipeDiameterMm: 600 })
    const c = resolveImageContext(photo({
      cameraId: 'RIG-B', pipeDiameterMm: 600,
      jointType: 'HORIZONTAL_SEAM', geometrySelectionProvenance: 'INSPECTOR_SELECTED',
    }), { cameraId: 'BATCH-CAMERA', pipeDiameterMm: 900 })
    expect(a.cameraId).toBe('RIG-A')
    expect(c.cameraId).toBe('RIG-B')
    expect([a.pipeDiameterMm, c.pipeDiameterMm]).toEqual([900, 600])
    expect(resolveImageContext(photo({}), { cameraId: 'BATCH-CAMERA' }).cameraId).toBeUndefined()
  })

  it('supports evidence-only review', () => {
    expect(hasExplicitPhotoMode(photo({ analysisMode: 'EVIDENCE_ONLY' }))).toBe(true)
  })
})
