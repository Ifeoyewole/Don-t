import type { InspectionStatus, QueueStatus } from '../types/domain'

type StatusValue = InspectionStatus | QueueStatus | 'IN PROGRESS'

type Props = {
  status: StatusValue
}

const labels: Record<StatusValue, string> = {
  PASS: 'Pass',
  REVIEW: 'Review',
  FAIL: 'Fail',
  queued: 'Queued',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
  'IN PROGRESS': 'In Progress',
}

export const StatusBadge = ({ status }: Props) => {
  const tone =
    status === 'PASS' || status === 'completed'
      ? 'status-badge status-pass'
      : status === 'FAIL' || status === 'failed'
        ? 'status-badge status-fail'
        : status === 'processing'
          ? 'status-badge status-processing'
          : 'status-badge status-review'

  return <span className={tone}>{labels[status]}</span>
}
