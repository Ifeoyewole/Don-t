import Dexie, { type Table } from 'dexie'
import type { InspectionImage, InspectionResult, Manhole, Project } from '../types'

export class PipeInspectionDatabase extends Dexie {
  projects!: Table<Project, string>
  manholes!: Table<Manhole, string>
  inspectionImages!: Table<InspectionImage, string>
  inspectionResults!: Table<InspectionResult, string>

  constructor() {
    super('pipe-joint-inspection-db')

    this.version(1).stores({
      projects: 'id, name, createdAt, updatedAt',
      manholes: 'id, projectId, manholeId, type, pipeType, createdAt, updatedAt',
      inspectionImages: 'id, projectId, manholeId, orderIndex, jointLabel, queueStatus, createdAt',
      inspectionResults: 'id, imageId, projectId, manholeId, jointLabel, status, processedAt, overrideApplied',
    })
  }
}

export const db = new PipeInspectionDatabase()
