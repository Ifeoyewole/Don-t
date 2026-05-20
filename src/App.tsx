import { useEffect, useMemo, useState } from 'react'
import { AppShell } from './components/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { CreateProjectPage } from './pages/CreateProjectPage'
import { InspectionResultsPage } from './pages/InspectionResultsPage'
import { InspectionSummaryPage } from './pages/InspectionSummaryPage'
import { ManholeSetupPage } from './pages/ManholeSetupPage'
import { PhotoUploadPage } from './pages/PhotoUploadPage'
import { pipeSpecs } from './services/mockData'
import type {
  CreateManholeInput,
  CreateProjectInput,
  EstimateMaterialsResult,
  InspectionImage,
  InspectionResult,
  InspectionStatus,
  Manhole,
  ManholeInspectionSummary,
  PipeType,
  ProjectInspectionSummary,
  ProjectSummary,
} from './types/domain'

type Route =
  | { key: 'dashboard' }
  | { key: 'create-project' }
  | { key: 'new-manhole'; projectId: string }
  | { key: 'edit-manhole'; projectId: string; manholeId: string }
  | { key: 'upload'; projectId: string; manholeId: string }
  | { key: 'results'; projectId: string; manholeId: string }
  | { key: 'summary'; projectId: string }

type ProjectMeta = {
  id: string
  name: string
  siteName?: string
  createdAt: string
  updatedAt: string
}

const parseRoute = (pathname: string): Route => {
  const segments = pathname.split('/').filter(Boolean)
  if (!segments.length) return { key: 'dashboard' }
  if (segments[0] === 'projects' && segments[1] === 'new') return { key: 'create-project' }
  if (segments[0] === 'projects' && segments[2] === 'manholes' && segments[3] === 'new') {
    return { key: 'new-manhole', projectId: segments[1] }
  }
  if (segments[0] === 'projects' && segments[2] === 'manholes' && segments[4] === 'upload') {
    return { key: 'upload', projectId: segments[1], manholeId: segments[3] }
  }
  if (segments[0] === 'projects' && segments[2] === 'manholes' && segments[4] === 'results') {
    return { key: 'results', projectId: segments[1], manholeId: segments[3] }
  }
  if (segments[0] === 'projects' && segments[2] === 'summary') {
    return { key: 'summary', projectId: segments[1] }
  }
  if (segments[0] === 'projects' && segments[2] === 'manholes' && segments[3]) {
    return { key: 'edit-manhole', projectId: segments[1], manholeId: segments[3] }
  }
  return { key: 'dashboard' }
}

const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))
const formatNow = () => new Date().toISOString()
const createId = (prefix: string) => `${prefix}-${Math.random().toString(36).slice(2, 10)}`

const classifyGap = (value: number): InspectionStatus => {
  if (value < 3) return 'REVIEW'
  if (value <= 15) return 'PASS'
  if (value <= 25) return 'REVIEW'
  return 'FAIL'
}

const calculateEstimate = (meterRun: number, pipeType: PipeType): EstimateMaterialsResult => {
  const spec = pipeSpecs[pipeType]
  const pipesNeeded = Math.max(1, Math.ceil(meterRun / spec.unitLengthM))
  return {
    unitLengthM: spec.unitLengthM,
    pipesNeeded,
    jointsNeeded: pipesNeeded + 2,
  }
}

const summarizeInspections = (inspections: InspectionResult[]) => {
  const passCount = inspections.filter((item) => item.status === 'PASS').length
  const reviewCount = inspections.filter((item) => item.status === 'REVIEW').length
  const failCount = inspections.filter((item) => item.status === 'FAIL').length
  const overriddenCount = inspections.filter((item) => item.overrideApplied).length

  return {
    totalJoints: inspections.length,
    passCount,
    reviewCount,
    failCount,
    overriddenCount,
    flaggedJoints: inspections
      .filter((item) => item.status !== 'PASS')
      .map((item) => ({
        inspectionId: item.id,
        jointLabel: item.jointLabel,
        status: item.status,
        finalGapMm: item.finalGapMm,
        note: item.notes || 'No note added yet.',
      })),
  }
}

const buildProjectSummary = (
  project: ProjectMeta,
  manholes: Manhole[],
  queues: Record<string, InspectionImage[]>,
  results: Record<string, InspectionResult[]>,
): ProjectSummary => {
  const projectManholes = manholes.filter((item) => item.projectId === project.id)
  const projectQueue = projectManholes.flatMap((item) => queues[item.id] ?? [])
  const projectResults = projectManholes.flatMap((item) => results[item.id] ?? [])
  const summary = summarizeInspections(projectResults)

  let status: ProjectSummary['status'] = 'IN PROGRESS'
  if (summary.failCount > 0) status = 'FAIL'
  else if (summary.reviewCount > 0) status = 'REVIEW'
  else if (summary.totalJoints > 0) status = 'PASS'

  return {
    id: project.id,
    name: project.name,
    siteName: project.siteName,
    createdAt: project.createdAt,
    updatedAt: project.updatedAt,
    totalManholes: projectManholes.length,
    totalJoints: summary.totalJoints,
    completedInspections: projectQueue.filter((item) => item.queueStatus === 'completed').length,
    failCount: summary.failCount,
    reviewCount: summary.reviewCount,
    status,
  }
}

const downloadBlob = (blob: Blob, fileName: string) => {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

const seedProjects: ProjectMeta[] = [
  {
    id: 'project-north-basin',
    name: 'North Basin Relief Main',
    siteName: 'Terminal 4 drainage corridor',
    createdAt: '2026-05-18T06:45:00.000Z',
    updatedAt: '2026-05-20T07:12:00.000Z',
  },
  {
    id: 'project-riverside',
    name: 'Riverside Joint Renewal',
    siteName: 'Sector C interceptor run',
    createdAt: '2026-05-14T10:20:00.000Z',
    updatedAt: '2026-05-20T08:15:00.000Z',
  },
]

const seedManholes: Manhole[] = [
  {
    id: 'manhole-nb-1',
    projectId: 'project-north-basin',
    manholeId: 'MH-204',
    type: 'surface-water',
    meterRun: 22.5,
    pipeType: '225mm-clay',
    pipeDiameterMm: 225,
    unitLengthM: 2,
    estimatedPipeCount: 12,
    estimatedJointCount: 14,
    createdAt: '2026-05-18T07:20:00.000Z',
    updatedAt: '2026-05-20T07:12:00.000Z',
  },
  {
    id: 'manhole-rv-1',
    projectId: 'project-riverside',
    manholeId: 'MH-117',
    type: 'foul-water',
    meterRun: 18,
    pipeType: '300mm-concrete',
    pipeDiameterMm: 300,
    unitLengthM: 2.6,
    estimatedPipeCount: 7,
    estimatedJointCount: 9,
    createdAt: '2026-05-14T11:00:00.000Z',
    updatedAt: '2026-05-20T08:15:00.000Z',
  },
]

const seedQueues: Record<string, InspectionImage[]> = {
  'manhole-nb-1': [
    {
      id: 'seed-image-1',
      projectId: 'project-north-basin',
      manholeId: 'manhole-nb-1',
      fileName: 'mh204_joint_1-2.jpg',
      mimeType: 'image/jpeg',
      blobKey: 'seed-1',
      orderIndex: 1,
      jointLabel: '1-2',
      captureSource: 'upload',
      queueStatus: 'completed',
      createdAt: '2026-05-20T06:58:00.000Z',
      progress: 100,
    },
    {
      id: 'seed-image-2',
      projectId: 'project-north-basin',
      manholeId: 'manhole-nb-1',
      fileName: 'mh204_joint_2-3.jpg',
      mimeType: 'image/jpeg',
      blobKey: 'seed-2',
      orderIndex: 2,
      jointLabel: '2-3',
      captureSource: 'upload',
      queueStatus: 'completed',
      createdAt: '2026-05-20T06:59:00.000Z',
      progress: 100,
    },
  ],
}

const seedResults: Record<string, InspectionResult[]> = {
  'manhole-nb-1': [
    {
      id: 'inspection-1',
      imageId: 'seed-image-1',
      projectId: 'project-north-basin',
      manholeId: 'manhole-nb-1',
      jointLabel: '1-2',
      originalGapMm: 4.8,
      finalGapMm: 4.8,
      status: 'PASS',
      confidence: 0.96,
      notes: 'Clean joint edge and stable ring alignment.',
      processedAt: '2026-05-20T07:05:00.000Z',
      overrideApplied: false,
    },
    {
      id: 'inspection-2',
      imageId: 'seed-image-2',
      projectId: 'project-north-basin',
      manholeId: 'manhole-nb-1',
      jointLabel: '2-3',
      originalGapMm: 2.4,
      finalGapMm: 2.4,
      status: 'REVIEW',
      confidence: 0.82,
      notes: 'Potential shadowing along lower left quadrant.',
      processedAt: '2026-05-20T07:07:00.000Z',
      overrideApplied: false,
    },
  ],
  'manhole-rv-1': [
    {
      id: 'inspection-3',
      imageId: 'seed-image-3',
      projectId: 'project-riverside',
      manholeId: 'manhole-rv-1',
      jointLabel: '1-2',
      originalGapMm: 28.4,
      finalGapMm: 26.1,
      status: 'FAIL',
      confidence: 0.91,
      notes: 'Inspector confirmed chipped edge did not affect final seating.',
      processedAt: '2026-05-20T08:00:00.000Z',
      overrideApplied: true,
      overrideReason: 'Adjusted after second visual review.',
      overrideValueMm: 26.1,
      overrideAt: '2026-05-20T08:04:00.000Z',
    },
  ],
}

function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname))
  const [online, setOnline] = useState(() => window.navigator.onLine)
  const [showAllProjects, setShowAllProjects] = useState(false)
  const [events, setEvents] = useState<string[]>([])
  const [projects, setProjects] = useState<ProjectMeta[]>(seedProjects)
  const [manholes, setManholes] = useState<Manhole[]>(seedManholes)
  const [queues, setQueues] = useState<Record<string, InspectionImage[]>>(seedQueues)
  const [results, setResults] = useState<Record<string, InspectionResult[]>>(seedResults)

  useEffect(() => {
    const onPopstate = () => setRoute(parseRoute(window.location.pathname))
    const onOnline = () => setOnline(true)
    const onOffline = () => setOnline(false)

    window.addEventListener('popstate', onPopstate)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)

    return () => {
      window.removeEventListener('popstate', onPopstate)
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  const navigate = (pathname: string) => {
    window.history.pushState({}, '', pathname)
    setRoute(parseRoute(pathname))
  }

  const projectSummaries = useMemo(
    () => projects.map((project) => buildProjectSummary(project, manholes, queues, results)),
    [projects, manholes, queues, results],
  )

  const currentProjectId = 'projectId' in route ? route.projectId : null
  const currentManholeId = 'manholeId' in route ? route.manholeId : null
  const currentProject = currentProjectId ? projects.find((item) => item.id === currentProjectId) ?? null : null
  const currentManhole = currentManholeId ? manholes.find((item) => item.id === currentManholeId) ?? null : null

  const getProjectSummary = (projectId: string): ProjectInspectionSummary => {
    const projectManholes = manholes.filter((item) => item.projectId === projectId)
    return {
      projectId,
      ...summarizeInspections(projectManholes.flatMap((item) => results[item.id] ?? [])),
    }
  }

  const getManholeSummary = (projectId: string, manholeId: string): ManholeInspectionSummary => ({
    projectId,
    manholeId,
    ...summarizeInspections(results[manholeId] ?? []),
  })

  const addEvent = (message: string) => setEvents((current) => [message, ...current].slice(0, 8))

  const page = (() => {
    if (route.key === 'dashboard') {
      return (
        <DashboardPage
          projects={projectSummaries}
          showAllProjects={showAllProjects}
          onToggleProjects={() => setShowAllProjects((current) => !current)}
          onNewProject={() => navigate('/projects/new')}
          onOpenProject={(projectId) => {
            const firstManhole = manholes.find((item) => item.projectId === projectId)
            navigate(firstManhole ? `/projects/${projectId}/summary` : `/projects/${projectId}/manholes/new`)
          }}
        />
      )
    }

    if (route.key === 'create-project') {
      return (
        <CreateProjectPage
          todayLabel={new Intl.DateTimeFormat('en-GB', { dateStyle: 'full' }).format(new Date())}
          onBack={() => navigate('/')}
          onSave={async (input: CreateProjectInput) => {
            const timestamp = formatNow()
            const project = {
              id: createId('project'),
              name: input.name.trim(),
              siteName: input.siteName?.trim(),
              createdAt: timestamp,
              updatedAt: timestamp,
            }
            setProjects((current) => [project, ...current])
            navigate(`/projects/${project.id}/manholes/new`)
          }}
        />
      )
    }

    if (route.key === 'new-manhole' || route.key === 'edit-manhole') {
      return (
        <ManholeSetupPage
          projectId={route.projectId}
          projectName={currentProject?.name ?? 'Untitled project'}
          manhole={route.key === 'edit-manhole' ? currentManhole : null}
          onBack={() => navigate(route.key === 'new-manhole' ? '/' : `/projects/${route.projectId}/summary`)}
          onEstimate={async ({ meterRun, pipeType }) => calculateEstimate(meterRun, pipeType)}
          onSave={async (input: CreateManholeInput, existingManholeId?: string) => {
            const estimate = calculateEstimate(input.meterRun, input.pipeType)
            const spec = pipeSpecs[input.pipeType]
            const timestamp = formatNow()
            const manhole: Manhole = {
              id: existingManholeId ?? createId('manhole'),
              projectId: input.projectId,
              manholeId: input.manholeId.trim(),
              type: input.type,
              meterRun: input.meterRun,
              pipeType: input.pipeType,
              pipeDiameterMm: spec.diameterMm,
              unitLengthM: estimate.unitLengthM,
              estimatedPipeCount: estimate.pipesNeeded,
              estimatedJointCount: estimate.jointsNeeded,
              createdAt: currentManhole?.createdAt ?? timestamp,
              updatedAt: timestamp,
            }
            setManholes((current) => {
              if (!existingManholeId) return [...current, manhole]
              return current.map((item) => (item.id === existingManholeId ? manhole : item))
            })
            navigate(`/projects/${route.projectId}/manholes/${manhole.id}/upload`)
          }}
        />
      )
    }

    if (route.key === 'upload') {
      const queue = queues[route.manholeId] ?? []
      return (
        <PhotoUploadPage
          projectName={currentProject?.name ?? 'Untitled project'}
          manholeLabel={currentManhole?.manholeId ?? 'Unassigned manhole'}
          queue={queue}
          events={events}
          onBack={() => navigate(`/projects/${route.projectId}/manholes/${route.manholeId}`)}
          onAddFiles={async (files) => {
            const nextItems = files.map((file, index) => {
              const orderIndex = queue.length + index + 1
              return {
                id: createId('image'),
                projectId: route.projectId,
                manholeId: route.manholeId,
                fileName: file.name,
                mimeType: file.type || 'image/jpeg',
                blobKey: createId('blob'),
                orderIndex,
                jointLabel: `${orderIndex}-${orderIndex + 1}`,
                captureSource: 'upload' as const,
                queueStatus: 'queued' as const,
                createdAt: formatNow(),
                previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
                progress: 0,
              }
            })
            setQueues((current) => ({ ...current, [route.manholeId]: [...(current[route.manholeId] ?? []), ...nextItems] }))
            addEvent(`[QUEUED] ${nextItems.length} photo${nextItems.length > 1 ? 's' : ''} added`)
          }}
          onLoadSample={async () => {
            const nextItems = ['joint_1-2.jpg', 'joint_2-3.jpg', 'joint_3-4.jpg'].map((fileName, index) => {
              const orderIndex = queue.length + index + 1
              return {
                id: createId('image'),
                projectId: route.projectId,
                manholeId: route.manholeId,
                fileName,
                mimeType: 'image/jpeg',
                blobKey: createId('blob'),
                orderIndex,
                jointLabel: `${orderIndex}-${orderIndex + 1}`,
                captureSource: 'upload' as const,
                queueStatus: 'queued' as const,
                createdAt: formatNow(),
                progress: 0,
              }
            })
            setQueues((current) => ({ ...current, [route.manholeId]: [...(current[route.manholeId] ?? []), ...nextItems] }))
            addEvent('[QUEUED] Sample queue loaded')
          }}
          onRemoveFile={async (imageId) => {
            setQueues((current) => ({
              ...current,
              [route.manholeId]: (current[route.manholeId] ?? []).filter((item) => item.id !== imageId),
            }))
          }}
          onClearQueue={async () => {
            setQueues((current) => ({ ...current, [route.manholeId]: [] }))
            setResults((current) => ({ ...current, [route.manholeId]: [] }))
            addEvent('[CLEARED] Queue reset')
          }}
          onStartInspection={async () => {
            const activeQueue = queues[route.manholeId] ?? []
            const generated: InspectionResult[] = []

            for (const [index, image] of activeQueue.entries()) {
              setQueues((current) => ({
                ...current,
                [route.manholeId]: (current[route.manholeId] ?? []).map((item) =>
                  item.id === image.id ? { ...item, queueStatus: 'processing', progress: 24 } : item,
                ),
              }))
              addEvent(`[STARTED] ${image.jointLabel}`)
              await delay(140)

              setQueues((current) => ({
                ...current,
                [route.manholeId]: (current[route.manholeId] ?? []).map((item) =>
                  item.id === image.id ? { ...item, progress: 76 } : item,
                ),
              }))
              await delay(140)

              const gap = Number((3 + index * 4.8 + Math.random() * 2.2).toFixed(1))
              const result: InspectionResult = {
                id: createId('inspection'),
                imageId: image.id,
                projectId: route.projectId,
                manholeId: route.manholeId,
                jointLabel: image.jointLabel,
                originalGapMm: gap,
                finalGapMm: gap,
                status: classifyGap(gap),
                confidence: Number((0.78 + index * 0.05).toFixed(2)),
                notes: gap <= 15 ? 'Initial pass looks within tolerance.' : 'Highlight this joint for closer review.',
                processedAt: formatNow(),
                overrideApplied: false,
              }
              generated.push(result)

              setQueues((current) => ({
                ...current,
                [route.manholeId]: (current[route.manholeId] ?? []).map((item) =>
                  item.id === image.id ? { ...item, queueStatus: 'completed', progress: 100 } : item,
                ),
              }))
              addEvent(`[COMPLETED] ${image.jointLabel} measured at ${gap.toFixed(1)} mm`)
            }

            setResults((current) => ({ ...current, [route.manholeId]: generated }))
            navigate(`/projects/${route.projectId}/manholes/${route.manholeId}/results`)
            return { manholeId: route.manholeId, processed: generated.length, failed: 0 }
          }}
        />
      )
    }

    if (route.key === 'results') {
      return (
        <InspectionResultsPage
          projectName={currentProject?.name ?? 'Untitled project'}
          manholeLabel={currentManhole?.manholeId ?? 'Unassigned manhole'}
          results={results[route.manholeId] ?? []}
          summary={getManholeSummary(route.projectId, route.manholeId)}
          onBack={() => navigate(`/projects/${route.projectId}/manholes/${route.manholeId}/upload`)}
          onSaveNote={async (inspectionId, note) => {
            setResults((current) => ({
              ...current,
              [route.manholeId]: (current[route.manholeId] ?? []).map((item) =>
                item.id === inspectionId ? { ...item, notes: note } : item,
              ),
            }))
          }}
          onRemeasure={async (inspectionId) => {
            setResults((current) => ({
              ...current,
              [route.manholeId]: (current[route.manholeId] ?? []).map((item) => {
                if (item.id !== inspectionId) return item
                const nextGap = Number(Math.max(0.8, item.originalGapMm - 0.5 + Math.random() * 1.1).toFixed(1))
                const finalGap = item.overrideApplied ? item.finalGapMm : nextGap
                return {
                  ...item,
                  originalGapMm: nextGap,
                  finalGapMm: finalGap,
                  status: classifyGap(finalGap),
                  confidence: Number(Math.min(0.99, item.confidence + 0.03).toFixed(2)),
                }
              }),
            }))
          }}
          onApplyOverride={async (inspectionId, overrideValueMm, overrideReason) => {
            setResults((current) => ({
              ...current,
              [route.manholeId]: (current[route.manholeId] ?? []).map((item) =>
                item.id === inspectionId
                  ? {
                      ...item,
                      finalGapMm: overrideValueMm,
                      status: classifyGap(overrideValueMm),
                      overrideApplied: true,
                      overrideReason,
                      overrideValueMm,
                      overrideAt: formatNow(),
                    }
                  : item,
              ),
            }))
          }}
          onClearOverride={async (inspectionId) => {
            setResults((current) => ({
              ...current,
              [route.manholeId]: (current[route.manholeId] ?? []).map((item) =>
                item.id === inspectionId
                  ? {
                      ...item,
                      finalGapMm: item.originalGapMm,
                      status: classifyGap(item.originalGapMm),
                      overrideApplied: false,
                      overrideReason: undefined,
                      overrideValueMm: undefined,
                      overrideAt: undefined,
                    }
                  : item,
              ),
            }))
          }}
          onNext={() => navigate(`/projects/${route.projectId}/summary`)}
        />
      )
    }

    if (route.key === 'summary') {
      return (
        <InspectionSummaryPage
          projectName={currentProject?.name ?? 'Untitled project'}
          projectId={route.projectId}
          summary={getProjectSummary(route.projectId)}
          onBack={() => {
            const firstManhole = manholes.find((item) => item.projectId === route.projectId)
            navigate(firstManhole ? `/projects/${route.projectId}/manholes/${firstManhole.id}/results` : '/')
          }}
          onOpenFlagged={() => {
            const firstManhole = manholes.find((item) => item.projectId === route.projectId)
            if (firstManhole) navigate(`/projects/${route.projectId}/manholes/${firstManhole.id}/results`)
          }}
          onExport={async (format) => {
            const payload = {
              project: currentProject,
              manholes: manholes.filter((item) => item.projectId === route.projectId),
              queue: manholes
                .filter((item) => item.projectId === route.projectId)
                .flatMap((item) => queues[item.id] ?? []),
              inspections: manholes
                .filter((item) => item.projectId === route.projectId)
                .flatMap((item) => results[item.id] ?? []),
              disclaimer: 'Guidance only — not a formal adoption assessment.',
            }

            if (format === 'json') {
              downloadBlob(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }), `${route.projectId}-ui-summary.json`)
              return
            }
            if (format === 'pdf') {
              downloadBlob(
                new Blob(
                  [
                    `JointInspect frontend summary\nProject: ${currentProject?.name ?? route.projectId}\nFlagged items: ${getProjectSummary(route.projectId).flaggedJoints.length}\nGuidance only — not a formal adoption assessment.`,
                  ],
                  { type: 'application/pdf' },
                ),
                `${route.projectId}-ui-summary.pdf`,
              )
              return
            }
            downloadBlob(
              new Blob(['Frontend-only evidence pack placeholder.'], { type: 'application/zip' }),
              `${route.projectId}-ui-evidence-pack.zip`,
            )
          }}
        />
      )
    }

    return null
  })()

  return (
    <AppShell
      online={online}
      navKey={route.key === 'dashboard' ? 'dashboard' : 'projects'}
      onNavigateHome={() => navigate('/')}
      onNavigateProjects={() => navigate('/')}
    >
      {page}
    </AppShell>
  )
}

export default App
