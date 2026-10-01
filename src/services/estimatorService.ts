import type { EstimateMaterialsInput, EstimateMaterialsResult } from '../types'
import { estimateMaterials } from '../utils'

export const estimatorService = {
  async calculate(
    input: EstimateMaterialsInput,
  ): Promise<EstimateMaterialsResult> {
    return estimateMaterials(input)
  },
}
