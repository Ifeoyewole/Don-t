export function createJointLabel(startIndex: number): string {
  return `${startIndex}-${startIndex + 1}`
}

export function createJointLabels(count: number, startIndex = 1): string[] {
  return Array.from({ length: count }, (_, index) =>
    createJointLabel(startIndex + index),
  )
}
