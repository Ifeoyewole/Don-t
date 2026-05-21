import type { PipeType } from '../types'

export interface PipeSpec {
  type: PipeType
  label: string
  diameterMm: number
  unitLengthM: number
}

export const PIPE_SPECS: Record<PipeType, PipeSpec> = {
  '150mm-clay': {
    type: '150mm-clay',
    label: '150 mm (clay) - 1.75m',
    diameterMm: 150,
    unitLengthM: 1.75,
  },
  '225mm-clay': {
    type: '225mm-clay',
    label: '225 mm (clay) - 2m',
    diameterMm: 225,
    unitLengthM: 2.0,
  },
  '300mm-concrete': {
    type: '300mm-concrete',
    label: '300 mm (concrete) - 2.6m',
    diameterMm: 300,
    unitLengthM: 2.6,
  },
  '450mm-concrete': {
    type: '450mm-concrete',
    label: '450 mm (concrete) - 2.6m',
    diameterMm: 450,
    unitLengthM: 2.6,
  },
  '600mm-concrete': {
    type: '600mm-concrete',
    label: '600 mm (concrete) - 2.6m',
    diameterMm: 600,
    unitLengthM: 2.6,
  },
  '900mm-concrete': {
    type: '900mm-concrete',
    label: '900 mm (concrete)',
    diameterMm: 900,
    unitLengthM: 2.6,
  },
}

export function getPipeSpec(pipeType: PipeType): PipeSpec {
  return PIPE_SPECS[pipeType]
}

export function listPipeSpecs(): PipeSpec[] {
  return Object.values(PIPE_SPECS)
}
