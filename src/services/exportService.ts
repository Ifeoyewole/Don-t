import JSZip from 'jszip'
import { PDFDocument, StandardFonts, rgb } from 'pdf-lib'
import { db } from '../db'
import type {
  InspectionBlob,
  InspectionImage,
  InspectionResult,
  Manhole,
  Project,
  ProjectInspectionSummary,
} from '../types'
import { summaryService } from './summaryService'
import { getPipeSpec } from '../utils'

const DISCLAIMER = 'Guidance only – not a formal adoption assessment.'

interface ExportProjectData {
  project: Project
  manholes: Manhole[]
  inspectionImages: InspectionImage[]
  inspectionResults: InspectionResult[]
  inspectionBlobs: InspectionBlob[]
  summary: ProjectInspectionSummary
  exportedAt: string
  disclaimer: string
}

interface ExportResultRecord {
  projectName: string
  manholeId: string
  dateTime: string
  pipeType: string
  pipeDiameterMm: number | null
  numberOfJointsCaptured: number
  gapValueMm: number
  gapStatus: string
  userNotes?: string
}

async function loadProjectExportData(projectId: string): Promise<ExportProjectData> {
  const project = await db.projects.get(projectId)
  if (!project) {
    throw new Error(`Project not found: ${projectId}`)
  }

  const manholes = await db.manholes.where('projectId').equals(projectId).sortBy('createdAt')
  const inspectionImages = await db.inspectionImages.where('projectId').equals(projectId).sortBy('orderIndex')
  const inspectionResults = await db.inspectionResults.where('projectId').equals(projectId).toArray()
  const inspectionBlobs: InspectionBlob[] = []

  for (const image of inspectionImages) {
    const blobRecord = await db.inspectionBlobs.get(image.blobKey)
    if (blobRecord) {
      inspectionBlobs.push(blobRecord)
    }
  }

  return {
    project,
    manholes,
    inspectionImages,
    inspectionResults,
    inspectionBlobs,
    summary: await summaryService.getProjectSummary(projectId),
    exportedAt: new Date().toISOString(),
    disclaimer: DISCLAIMER,
  }
}

function buildExportResultRecords(data: ExportProjectData): ExportResultRecord[] {
  return data.inspectionResults.map((result) => {
    const manhole = data.manholes.find((item) => item.id === result.manholeId)
    const spec = manhole ? getPipeSpec(manhole.pipeType) : null
    const capturedCount = data.inspectionResults.filter((item) => item.manholeId === result.manholeId).length

    return {
      projectName: data.project.name,
      manholeId: manhole?.manholeId ?? 'N/A',
      dateTime: result.processedAt,
      pipeType: spec?.label ?? 'N/A',
      pipeDiameterMm: manhole?.pipeDiameterMm ?? null,
      numberOfJointsCaptured: capturedCount,
      gapValueMm: result.finalGapMm,
      gapStatus: result.status,
      userNotes: result.notes ?? '',
    }
  })
}

function createExportFileName(name: string, extension: string): string {
  const safeName =
    name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') ||
    'project'
  return `${safeName}.${extension}`
}

async function createPdfBlob(data: ExportProjectData): Promise<Blob> {
  const pdf = await PDFDocument.create()
  let page = pdf.addPage([595, 842])
  const font = await pdf.embedFont(StandardFonts.Helvetica)
  const boldFont = await pdf.embedFont(StandardFonts.HelveticaBold)

  let y = 800
  const left = 50

  page.drawText('Pipe Joint Inspection Evidence Report', {
    x: left,
    y,
    size: 18,
    font: boldFont,
    color: rgb(0.04, 0.09, 0.2),
  })

  y -= 32
  const lines = [
    `Project: ${data.project.name}`,
    `Site: ${data.project.siteName ?? 'N/A'}`,
    `Exported: ${data.exportedAt}`,
    `Manholes: ${data.manholes.length}`,
    `Inspections: ${data.inspectionResults.length}`,
    `PASS: ${data.summary.passCount}  REVIEW: ${data.summary.reviewCount}  FAIL: ${data.summary.failCount}`,
  ]

  for (const line of lines) {
    page.drawText(line, {
      x: left,
      y,
      size: 11,
      font,
      color: rgb(0.1, 0.1, 0.1),
    })
    y -= 18
  }

  y -= 12
  page.drawText('Inspection Results', {
    x: left,
    y,
    size: 13,
    font: boldFont,
    color: rgb(0.04, 0.09, 0.2),
  })
  y -= 20

  for (const result of buildExportResultRecords(data).slice(0, 25)) {
    const text = [
      `Project name: ${result.projectName}`,
      `Manhole ID: ${result.manholeId}`,
      `Date/time: ${result.dateTime}`,
      `Pipe type: ${result.pipeType}`,
      `Pipe diameter: ${result.pipeDiameterMm ?? 'N/A'} mm`,
      `Number of joints captured: ${result.numberOfJointsCaptured}`,
      `Gap value (mm): ${result.gapValueMm.toFixed(1)}`,
      `Gap status: ${result.gapStatus}`,
      `User notes: ${result.userNotes || 'None'}`,
    ].join(' | ')
    page.drawText(text, {
      x: left,
      y,
      size: 10,
      font,
      color: rgb(0.15, 0.15, 0.15),
    })
    y -= 14

    if (y < 70) {
      page = pdf.addPage([595, 842])
      y = 800
      page.drawText('Inspection Results (continued)', {
        x: left,
        y,
        size: 13,
        font: boldFont,
        color: rgb(0.04, 0.09, 0.2),
      })
      y -= 20
    }
  }

  page.drawText(DISCLAIMER, {
    x: left,
    y: 40,
    size: 10,
    font,
    color: rgb(0.45, 0.1, 0.1),
  })

  const bytes = await pdf.save()
  const normalizedBytes = new Uint8Array(bytes.length)
  normalizedBytes.set(bytes)
  return new Blob([normalizedBytes], { type: 'application/pdf' })
}

export const exportService = {
  async exportJson(projectId: string): Promise<Blob> {
    const data = await loadProjectExportData(projectId)
    const serialized = JSON.stringify(
      {
        disclaimer: data.disclaimer,
        results: buildExportResultRecords(data),
      },
      null,
      2,
    )
    return new Blob([serialized], { type: 'application/json' })
  },

  async exportPdf(projectId: string): Promise<Blob> {
    const data = await loadProjectExportData(projectId)
    return createPdfBlob(data)
  },

  async exportEvidenceZip(projectId: string): Promise<Blob> {
    const data = await loadProjectExportData(projectId)
    const zip = new JSZip()
    const baseName = data.project.name || 'project'

    const jsonBlob = await this.exportJson(projectId)
    const jsonText = await jsonBlob.text()
    zip.file(createExportFileName(baseName, 'json'), jsonText)

    const pdfBlob = await this.exportPdf(projectId)
    zip.file(createExportFileName(baseName, 'pdf'), pdfBlob)

    const imagesFolder = zip.folder('images')
    for (const blobRecord of data.inspectionBlobs) {
      imagesFolder?.file(blobRecord.fileName, blobRecord.blob)
    }

    zip.file('README.txt', `${DISCLAIMER}\n\nExported: ${data.exportedAt}`)

    return zip.generateAsync({ type: 'blob' })
  },
}
