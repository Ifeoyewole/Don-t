import type { EstimateMaterialsInput, EstimateMaterialsResult } from '../types'
import { getPipeSpec } from './pipeSpecs'

export function estimateMaterials(
  input: EstimateMaterialsInput,
): EstimateMaterialsResult {
  const spec = getPipeSpec(input.pipeType)
  const pipesNeeded = Math.ceil(input.meterRun / spec.unitLengthM)
  const jointsNeeded = pipesNeeded + 2

  return {
    pipeType: spec.type,
    pipeDiameterMm: spec.diameterMm,
    unitLengthM: spec.unitLengthM,
    pipesNeeded,
    jointsNeeded,
  }
}
