import type {
  FlaggedInspectionSummary,
  InspectionResult,
  ManholeInspectionSummary,
  ProjectInspectionSummary,
} from '../types'

export function toFlaggedInspection(result: InspectionResult): FlaggedInspectionSummary {
  return {
    inspectionId: result.id,
    jointLabel: result.jointLabel,
    status: result.status,
    finalGapMm: result.finalGapMm,
    overrideApplied: result.overrideApplied,
  }
}

export function summarizeInspectionResults(
  key: string,
  results: InspectionResult[],
  type: 'project' | 'manhole',
): ProjectInspectionSummary | ManholeInspectionSummary {
  const passCount = results.filter((result) => result.status === 'PASS').length
  const reviewCount = results.filter((result) => result.status === 'REVIEW').length
  const failCount = results.filter((result) => result.status === 'FAIL').length
  const overriddenCount = results.filter((result) => result.overrideApplied).length
  const flaggedJoints = results
    .filter((result) => result.status !== 'PASS' || result.overrideApplied)
    .map(toFlaggedInspection)

  if (type === 'project') {
    return {
      projectId: key,
      totalJoints: results.length,
      passCount,
      reviewCount,
      failCount,
      overriddenCount,
      flaggedJoints,
    }
  }

  return {
    manholeId: key,
    totalJoints: results.length,
    passCount,
    reviewCount,
    failCount,
    overriddenCount,
    flaggedJoints,
  }
}
