import type { InspectionFeedback } from '../types/feedback'
import Dexie, { type Table } from 'dexie'
import type {
  InspectionBlob,
  InspectionImage,
  InspectionResult,
  Manhole,
  Project,
} from '../types'
import { normalizeLegacyInspectionResult } from './migrations'

export class PipeInspectionDatabase extends Dexie {
  feedbackInterpretations!: Table<{feedbackId:string;result:unknown;createdAt:string},string>
  inspectionFeedback!: Table<InspectionFeedback,string>
  projects!: Table<Project, string>
  manholes!: Table<Manhole, string>
  inspectionImages!: Table<InspectionImage, string>
  inspectionBlobs!: Table<InspectionBlob, string>
  inspectionResults!: Table<InspectionResult, string>

  constructor() {
    super('pipe-joint-inspection-db')

    this.version(1).stores({
      projects: 'id, name, createdAt, updatedAt',
      manholes: 'id, projectId, manholeId, type, pipeType, createdAt, updatedAt',
      inspectionImages: 'id, projectId, manholeId, orderIndex, jointLabel, queueStatus, createdAt',
      inspectionResults: 'id, imageId, projectId, manholeId, jointLabel, status, processedAt, overrideApplied',
    })

    this.version(2).stores({
      projects: 'id, name, createdAt, updatedAt',
      manholes: 'id, projectId, manholeId, type, pipeType, createdAt, updatedAt',
      inspectionImages: 'id, projectId, manholeId, orderIndex, jointLabel, queueStatus, createdAt',
      inspectionBlobs: 'id, imageId, createdAt',
      inspectionResults: 'id, imageId, projectId, manholeId, jointLabel, status, processedAt, overrideApplied',
    })

    this.version(3).stores({
      projects: 'id, name, createdAt, updatedAt',
      manholes: 'id, projectId, manholeId, type, pipeType, createdAt, updatedAt',
      inspectionImages: 'id, projectId, manholeId, orderIndex, jointLabel, queueStatus, createdAt',
      inspectionBlobs: 'id, imageId, createdAt',
      inspectionResults: 'id, imageId, projectId, manholeId, jointLabel, status, processedAt, overrideApplied',
    }).upgrade((transaction) => transaction.table('inspectionResults').toCollection().modify((record) => {
      Object.assign(record, normalizeLegacyInspectionResult(record))
    }))
    this.version(4).stores({inspectionFeedback:'id, inspectionId, imageId, createdAt, [inspectionId+revision]',feedbackInterpretations:'feedbackId, createdAt'})

  }
}

export const db = new PipeInspectionDatabase()
