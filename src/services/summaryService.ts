import { db } from '../db'
import type {
  ManholeInspectionSummary,
  ProjectInspectionSummary,
} from '../types'
import { summarizeInspectionResults } from '../utils'

export const summaryService = {
  async getProjectSummary(projectId: string): Promise<ProjectInspectionSummary> {
    const results = await db.inspectionResults.where('projectId').equals(projectId).toArray()
    return summarizeInspectionResults(projectId, results, 'project') as ProjectInspectionSummary
  },

  async getManholeSummary(manholeId: string): Promise<ManholeInspectionSummary> {
    const results = await db.inspectionResults.where('manholeId').equals(manholeId).toArray()
    return summarizeInspectionResults(manholeId, results, 'manhole') as ManholeInspectionSummary
  },
}
