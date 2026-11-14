export interface UnifiedEvidence {
  engine: string
  image_sha256: string
  dimensions: [number, number]
  decision: 'REVIEW_REQUIRED'
  research_only: true
  physical_gap_mm: number | null
  summary: string
  overlay_png_base64: string
  regions: Array<{ region_id: number; mask_status: string; mask_png_base64?: string; bbox: number[]; mask_quality_score?: number; geometry: { status: string; pixel_candidate?: number | null }; boundary_evidence?: { reason?: string; gap_estimate_px?: number | null; method?: string; accepted_cross_sections?: number; width_mad_px?: number; min_width_px?: number; max_width_px?: number; limitation?: string; text_exclusion_boxes?: number[][] } }>
  preliminary_findings: Array<{ label: string; status: string; explanation?: string; detector_score?: number }>
  gemini: { status: string; model?: string; analysis?: { summary: string; contradictions: string[]; limitations: string[] } }
  joint_measurement: { status: string; physical_gap_mm: number | null; calibration_authority_verified?: boolean; scene_status?: string; rejection_reasons?: string[]; calibration_status?: string; measurement_message?: string; candidates: Array<{ value: number; units: string; meaning: string }> }
  components: { inspect_view?: { status?: string; evidence?: { classes?: Record<string, { probability: number | null; status: string }> } }; sewer_detector?: { status?: string; detections?: Array<{ source_label: string; score: number; bbox: number[] }> } }
  disagreements_and_limits: string[]
  latency_seconds?: { total: number }
}
