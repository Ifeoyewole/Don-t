import { useCallback, useEffect, useState } from 'react'
import { db } from './db'
import { AppShell } from './components/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { CreateProjectPage } from './pages/CreateProjectPage'
import { InspectionResultsPage } from './pages/InspectionResultsPage'
import { InspectionSummaryPage } from './pages/InspectionSummaryPage'
import { ManholeSetupPage } from './pages/ManholeSetupPage'
import { PhotoUploadPage } from './pages/PhotoUploadPage'
import {
  estimatorService,
  exportService,
  inspectionQueue,
  inspectionService,
  manholeService,
  processor,
  projectService,
  summaryService,
} from './services'
import type {
  CreateManholeInput,
  CreateProjectInput,
  InspectionImage,
  InspectionResult,
  InspectionStatus,
  Manhole,
  ManholeInspectionSummary,
  Project,
  ProjectInspectionSummary,
  ProjectSummary,
} from './types'

type Route =
  | { key: 'dashboard' }
  | { key: 'create-project' }
  | { key: 'new-manhole'; projectId: string }
  | { key: 'edit-manhole'; projectId: string; manholeId: string }
  | { key: 'upload'; projectId: string; manholeId: string }
  | { key: 'results'; projectId: string; manholeId: string }
  | { key: 'summary'; projectId: string }

type UiProjectSummary = ProjectSummary & {
  totalManholes: number
  totalJoints: number
  completedInspections: number
  status: InspectionStatus | 'IN PROGRESS'
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

const formatProjectStatus = (summary: ProjectInspectionSummary): UiProjectSummary['status'] => {
  if (summary.failCount > 0) return 'FAIL'
  if (summary.reviewCount > 0) return 'REVIEW'
  if (summary.totalJoints > 0) return 'PASS'
  return 'IN PROGRESS'
}

const enrichQueueForUi = async (queue: InspectionImage[]) => {
  return Promise.all(
    queue.map(async (image) => {
      const blobRecord = await db.inspectionBlobs.get(image.blobKey)
      const previewUrl =
        blobRecord?.blob && blobRecord.mimeType.startsWith('image/')
          ? URL.createObjectURL(blobRecord.blob)
          : undefined

      return {
        ...image,
        previewUrl,
        progress:
          image.progress ??
          (image.queueStatus === 'completed'
            ? 100
            : image.queueStatus === 'processing'
              ? 65
              : image.queueStatus === 'failed'
                ? 100
                : 0),
      }
    }),
  )
}

const revokeQueuePreviews = (queue: InspectionImage[]) => {
  for (const image of queue) {
    if (image.previewUrl?.startsWith('blob:')) {
      URL.revokeObjectURL(image.previewUrl)
    }
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

function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname))
  const [online, setOnline] = useState(() => window.navigator.onLine)
  const [showAllProjects, setShowAllProjects] = useState(false)
  const [events, setEvents] = useState<string[]>([])
  const [projects, setProjects] = useState<UiProjectSummary[]>([])
  const [currentProject, setCurrentProject] = useState<Project | null>(null)
  const [currentManhole, setCurrentManhole] = useState<Manhole | null>(null)
  const [currentQueue, setCurrentQueue] = useState<InspectionImage[]>([])
  const [currentResults, setCurrentResults] = useState<InspectionResult[]>([])
  const [currentProjectSummary, setCurrentProjectSummary] = useState<ProjectInspectionSummary | null>(null)
  const [currentManholeSummary, setCurrentManholeSummary] = useState<ManholeInspectionSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const onPopstate = () => {
      setLoading(true)
      setRoute(parseRoute(window.location.pathname))
    }
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

  useEffect(() => {
    const unsubscribe = processor.subscribe((event) => {
      const label = `[${event.type.toUpperCase()}] ${event.progress ? `${event.progress}% ` : ''}${event.message ?? event.imageId}`
      setEvents((current) => [label, ...current].slice(0, 10))
      setCurrentQueue((current) =>
        current.map((image) => {
          if (image.id !== event.imageId) {
            return image
          }

          if (event.type === 'started') {
            return {
              ...image,
              queueStatus: 'processing',
              progress: 5,
              errorMessage: undefined,
            }
          }

          if (event.type === 'progress') {
            return {
              ...image,
              queueStatus: 'processing',
              progress: event.progress ?? image.progress ?? 0,
              errorMessage: event.message,
            }
          }

          if (event.type === 'completed') {
            return {
              ...image,
              queueStatus: 'completed',
              progress: 100,
              errorMessage: undefined,
            }
          }

          if (event.type === 'failed') {
            return {
              ...image,
              queueStatus: 'failed',
              progress: 100,
              errorMessage: event.message ?? 'Processing failed',
            }
          }

          return image
        }),
      )
    })

    return unsubscribe
  }, [])

  useEffect(() => {
    return () => {
      revokeQueuePreviews(currentQueue)
    }
  }, [currentQueue])

  const navigate = (pathname: string) => {
    setLoading(true)
    window.history.pushState({}, '', pathname)
    setRoute(parseRoute(pathname))
  }

  const refreshProjects = useCallback(async () => {
    const listed = await projectService.listProjects()
    const enriched = await Promise.all(
      listed.map(async (project) => {
        const summary = await summaryService.getProjectSummary(project.id)
        return {
          ...project,
          totalManholes: project.manholeCount ?? 0,
          totalJoints: summary.totalJoints,
          completedInspections: project.inspectionCount ?? 0,
          status: formatProjectStatus(summary),
        }
      }),
    )
    setProjects(enriched)
    return enriched
  }, [])

  const refreshRouteData = useCallback(async () => {
    try {
      await refreshProjects()

      if (route.key === 'dashboard' || route.key === 'create-project') {
        setCurrentQueue((previous) => {
          revokeQueuePreviews(previous)
          return []
        })
        setCurrentProject(null)
        setCurrentManhole(null)
        setCurrentResults([])
        setCurrentProjectSummary(null)
        setCurrentManholeSummary(null)
        return
      }

      const project = await projectService.getProject(route.projectId)
      setCurrentProject(project)

      if (!project) {
        setCurrentQueue((previous) => {
          revokeQueuePreviews(previous)
          return []
        })
        setCurrentManhole(null)
        setCurrentResults([])
        setCurrentProjectSummary(null)
        setCurrentManholeSummary(null)
        return
      }

      const projectSummary = await summaryService.getProjectSummary(route.projectId)
      setCurrentProjectSummary(projectSummary)

      if (route.key === 'new-manhole' || route.key === 'summary') {
        setCurrentQueue((previous) => {
          revokeQueuePreviews(previous)
          return []
        })
        setCurrentManhole(null)
        setCurrentResults([])
        setCurrentManholeSummary(null)
        return
      }

      const manhole = await manholeService.getManhole(route.manholeId)
      setCurrentManhole(manhole)

      if (!manhole) {
        setCurrentQueue((previous) => {
          revokeQueuePreviews(previous)
          return []
        })
        setCurrentResults([])
        setCurrentManholeSummary(null)
        return
      }

      const [queue, results, manholeSummary] = await Promise.all([
        inspectionQueue.listQueue(route.manholeId),
        inspectionService.listByManhole(route.manholeId),
        summaryService.getManholeSummary(route.manholeId),
      ])

      const queueWithPreviews = await enrichQueueForUi(queue)
      setCurrentQueue((previous) => {
        revokeQueuePreviews(previous)
        return queueWithPreviews
      })
      setCurrentResults(results)
      setCurrentManholeSummary({ ...manholeSummary, projectId: route.projectId })
    } finally {
      setLoading(false)
    }
  }, [refreshProjects, route])

  useEffect(() => {
    void refreshRouteData()
  }, [refreshRouteData])

  const currentProjectId = 'projectId' in route ? route.projectId : null

  const page = (() => {
    if (loading) {
      return (
        <div className="page-grid">
          <section className="empty-state">
            <strong>Loading workspace...</strong>
            <p>Opening your latest inspection data.</p>
          </section>
        </div>
      )
    }

    if (route.key === 'dashboard') {
      return (
        <DashboardPage
          projects={projects}
          showAllProjects={showAllProjects}
          onToggleProjects={() => setShowAllProjects((current) => !current)}
          onNewProject={() => navigate('/projects/new')}
          onOpenProject={(projectId) => {
            const project = projects.find((item) => item.id === projectId)
            if ((project?.totalManholes ?? 0) > 0) {
              navigate(`/projects/${projectId}/summary`)
              return
            }
            navigate(`/projects/${projectId}/manholes/new`)
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
            const project = await projectService.createProject(input)
            await refreshProjects()
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
          onEstimate={estimatorService.calculate}
          onSave={async (input: CreateManholeInput, existingManholeId?: string) => {
            const manhole = existingManholeId
              ? await manholeService.updateManhole(existingManholeId, input)
              : await manholeService.createManhole(input)
            await refreshProjects()
            navigate(`/projects/${route.projectId}/manholes/${manhole.id}/upload`)
          }}
        />
      )
    }

    if (route.key === 'upload') {
      return (
        <PhotoUploadPage
          projectName={currentProject?.name ?? 'Untitled project'}
          manholeLabel={currentManhole?.manholeId ?? 'Unassigned manhole'}
          queue={currentQueue}
          events={events}
          onBack={() => navigate(`/projects/${route.projectId}/manholes/${route.manholeId}`)}
          onAddFiles={async (files) => {
            await inspectionQueue.addFiles({
              projectId: route.projectId,
              manholeId: route.manholeId,
              files,
            })
            await refreshRouteData()
          }}
          onLoadSample={async () => {
            const sampleFiles = [
              new File(['sample-one'], 'joint_1-2.jpg', { type: 'image/jpeg' }),
              new File(['sample-two'], 'joint_2-3.jpg', { type: 'image/jpeg' }),
              new File(['sample-three'], 'joint_3-4.jpg', { type: 'image/jpeg' }),
            ]
            await inspectionQueue.addFiles({
              projectId: route.projectId,
              manholeId: route.manholeId,
              files: sampleFiles,
            })
            await refreshRouteData()
          }}
          onRemoveFile={async (imageId) => {
            await inspectionQueue.removeFile(imageId)
            await refreshRouteData()
          }}
          onClearQueue={async () => {
            await inspectionQueue.clearManholeQueue(route.manholeId)
            await refreshRouteData()
          }}
          onStartInspection={async () => {
            const result = await processor.processQueuedImages(route.manholeId)
            await refreshProjects()
            await refreshRouteData()
            navigate(`/projects/${route.projectId}/manholes/${route.manholeId}/results`)
            return {
              manholeId: result.manholeId,
              processed: result.completed ?? 0,
              failed: result.failed,
              completed: result.completed,
              total: result.total,
              inspectionIds: result.inspectionIds,
            }
          }}
        />
      )
    }

    if (route.key === 'results') {
      return (
        <InspectionResultsPage
          projectName={currentProject?.name ?? 'Untitled project'}
          manholeLabel={currentManhole?.manholeId ?? 'Unassigned manhole'}
          results={currentResults}
          summary={currentManholeSummary}
          onBack={() => navigate(`/projects/${route.projectId}/manholes/${route.manholeId}/upload`)}
          onSaveNote={async (inspectionId, note) => {
            await inspectionService.saveInspectorNote(inspectionId, note)
            await refreshRouteData()
          }}
          onRemeasure={async (inspectionId) => {
            await processor.remeasureInspection(inspectionId)
            await refreshProjects()
            await refreshRouteData()
          }}
          onApplyOverride={async (inspectionId, overrideValueMm, overrideReason) => {
            await inspectionService.applyOverride({ inspectionId, overrideValueMm, overrideReason })
            await refreshProjects()
            await refreshRouteData()
          }}
          onClearOverride={async (inspectionId) => {
            await inspectionService.clearOverride(inspectionId)
            await refreshProjects()
            await refreshRouteData()
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
          summary={currentProjectSummary}
          onBack={() => {
            if (!currentProjectId) {
              navigate('/')
              return
            }
            navigate(`/projects/${currentProjectId}/manholes/new`)
          }}
          onOpenFlagged={() => {
            const firstFlaggedId = currentProjectSummary?.flaggedJoints[0]?.inspectionId
            if (!firstFlaggedId || !currentProjectId) {
              navigate('/')
              return
            }
            void inspectionService.getInspection(firstFlaggedId).then((inspection) => {
              if (inspection) {
                navigate(`/projects/${currentProjectId}/manholes/${inspection.manholeId}/results`)
              }
            })
          }}
          onExport={async (format) => {
            if (format === 'json') {
              const blob = await exportService.exportJson(route.projectId)
              downloadBlob(blob, `${route.projectId}-summary.json`)
              return
            }
            if (format === 'pdf') {
              const blob = await exportService.exportPdf(route.projectId)
              downloadBlob(blob, `${route.projectId}-summary.pdf`)
              return
            }
            const blob = await exportService.exportEvidenceZip(route.projectId)
            downloadBlob(blob, `${route.projectId}-evidence-pack.zip`)
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
