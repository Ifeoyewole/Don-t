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
  FlaggedInspectionSummary,
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
  | { key: 'upload-inspection'; inspectionId: string }
  | { key: 'results'; inspectionId: string }
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
  if (segments[0] === 'inspections' && segments[2] === 'upload') {
    return { key: 'upload-inspection', inspectionId: segments[1] }
  }
  if (segments[0] === 'inspections' && segments[2] === 'results') {
    return { key: 'results', inspectionId: segments[1] }
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

const withDefaultProgress = (image: InspectionImage) => ({
  ...image,
  progress:
    image.progress ??
    (image.queueStatus === 'completed'
      ? 100
      : image.queueStatus === 'processing'
        ? 65
        : image.queueStatus === 'failed'
          ? 100
          : 0),
})

const createPreviewUrl = (blob?: Blob, mimeType?: string) =>
  blob && mimeType?.startsWith('image/') ? URL.createObjectURL(blob) : undefined

const revokeUrl = (url?: string) => {
  if (url?.startsWith('blob:')) {
    URL.revokeObjectURL(url)
  }
}

const revokeQueuePreviews = (queue: InspectionImage[]) => {
  for (const image of queue) {
    revokeUrl(image.previewUrl)
  }
}

const revokeResultPreviews = (results: InspectionResult[]) => {
  for (const result of results) {
    revokeUrl(result.previewUrl)
  }
}

const revokeSummaryPreviews = (summary: ProjectInspectionSummary | null) => {
  summary?.flaggedJoints.forEach((item) => revokeUrl(item.previewUrl))
}

const inspectionRouteStorageKey = 'jointinspect:inspection-route-map'

const readInspectionRouteMap = (): Record<string, { projectId: string; manholeId: string }> => {
  try {
    const raw = window.localStorage.getItem(inspectionRouteStorageKey)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

const writeInspectionRouteMapEntry = (inspectionId: string, projectId: string, manholeId: string) => {
  const current = readInspectionRouteMap()
  current[inspectionId] = { projectId, manholeId }
  window.localStorage.setItem(inspectionRouteStorageKey, JSON.stringify(current))
}

const enrichQueueForUi = async (queue: InspectionImage[]) =>
  Promise.all(
    queue.map(async (image) => {
      const blobRecord = await db.inspectionBlobs.get(image.blobKey)
      return {
        ...withDefaultProgress(image),
        previewUrl: createPreviewUrl(blobRecord?.blob, blobRecord?.mimeType),
      }
    }),
  )

const enrichResultsForUi = async (results: InspectionResult[], manholes: Manhole[]) => {
  const manholeMap = new Map(manholes.map((manhole) => [manhole.id, manhole]))

  return Promise.all(
    results.map(async (result) => {
      const image = await db.inspectionImages.get(result.imageId)
      const blobRecord = image ? await db.inspectionBlobs.get(image.blobKey) : undefined
      const manhole = manholeMap.get(result.manholeId)

      return {
        ...result,
        fileName: image?.fileName ?? result.fileName,
        manholeLabel: manhole?.manholeId ?? result.manholeLabel,
        previewUrl: createPreviewUrl(blobRecord?.blob, blobRecord?.mimeType),
      }
    }),
  )
}

const enrichFlaggedSummary = async (summary: ProjectInspectionSummary, manholes: Manhole[]) => {
  const manholeMap = new Map(manholes.map((manhole) => [manhole.id, manhole]))
  const flaggedJoints: FlaggedInspectionSummary[] = await Promise.all(
    summary.flaggedJoints.map(async (item) => {
      const result = await inspectionService.getInspection(item.inspectionId)
      const image = result ? await db.inspectionImages.get(result.imageId) : undefined
      const blobRecord = image ? await db.inspectionBlobs.get(image.blobKey) : undefined
      const manhole = result ? manholeMap.get(result.manholeId) : undefined

      return {
        ...item,
        finalGapMm: result?.finalGapMm ?? item.finalGapMm,
        measurementSource: result?.measurementSource ?? item.measurementSource,
        overrideApplied: result?.overrideApplied ?? item.overrideApplied,
        note: result?.notes ?? item.note,
        processedAt: result?.processedAt ?? item.processedAt,
        photoCount: image ? 1 : item.photoCount,
        fileName: image?.fileName ?? item.fileName,
        manholeLabel: manhole?.manholeId ?? item.manholeLabel,
        previewUrl: createPreviewUrl(blobRecord?.blob, blobRecord?.mimeType),
      }
    }),
  )

  return {
    ...summary,
    flaggedJoints,
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
  const [projectManholes, setProjectManholes] = useState<Manhole[]>([])
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
      setEvents((current) => [label, ...current].slice(0, 12))
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

  useEffect(() => () => revokeQueuePreviews(currentQueue), [currentQueue])
  useEffect(() => () => revokeResultPreviews(currentResults), [currentResults])
  useEffect(() => () => revokeSummaryPreviews(currentProjectSummary), [currentProjectSummary])

  const navigate = (pathname: string, options?: { keepLoading?: boolean }) => {
    if (!options?.keepLoading) {
      setLoading(true)
    }
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

  const clearVisualState = () => {
    setCurrentQueue((previous) => {
      revokeQueuePreviews(previous)
      return []
    })
    setCurrentResults((previous) => {
      revokeResultPreviews(previous)
      return []
    })
    setCurrentProjectSummary((previous) => {
      revokeSummaryPreviews(previous)
      return null
    })
  }

  const refreshRouteData = useCallback(async () => {
    try {
      await refreshProjects()

      if (route.key === 'dashboard' || route.key === 'create-project') {
        clearVisualState()
        setCurrentProject(null)
        setProjectManholes([])
        setCurrentManhole(null)
        setCurrentManholeSummary(null)
        return
      }

      const targetProjectId =
        route.key === 'results' || route.key === 'upload-inspection'
          ? ((await inspectionService.getInspection(route.inspectionId))?.projectId ??
            readInspectionRouteMap()[route.inspectionId]?.projectId ??
            null)
          : route.projectId

      if (!targetProjectId) {
        clearVisualState()
        setCurrentProject(null)
        setProjectManholes([])
        setCurrentManhole(null)
        setCurrentManholeSummary(null)
        return
      }

      const project = await projectService.getProject(targetProjectId)
      setCurrentProject(project)
      setProjectManholes(project?.manholes ?? [])

      if (!project) {
        clearVisualState()
        setCurrentManhole(null)
        setCurrentManholeSummary(null)
        return
      }

      const rawProjectSummary = await summaryService.getProjectSummary(targetProjectId)
      if (route.key === 'summary') {
        const enrichedProjectSummary = await enrichFlaggedSummary(rawProjectSummary, project.manholes)
        setCurrentProjectSummary((previous) => {
          revokeSummaryPreviews(previous)
          return enrichedProjectSummary
        })
      } else {
        setCurrentProjectSummary((previous) => {
          revokeSummaryPreviews(previous)
          return rawProjectSummary
        })
      }

      if (route.key === 'new-manhole' || route.key === 'summary') {
        setCurrentQueue((previous) => {
          revokeQueuePreviews(previous)
          return []
        })
        setCurrentResults((previous) => {
          revokeResultPreviews(previous)
          return []
        })
        setCurrentManhole(null)
        setCurrentManholeSummary(null)
        return
      }

      const focusInspection =
        route.key === 'results' || route.key === 'upload-inspection'
          ? await inspectionService.getInspection(route.inspectionId)
          : null
      const targetManholeId =
        route.key === 'results' || route.key === 'upload-inspection'
          ? (focusInspection?.manholeId ?? readInspectionRouteMap()[route.inspectionId]?.manholeId ?? null)
          : route.manholeId

      if (route.key === 'results' || route.key === 'upload-inspection') {
        console.log('ROUTE INSPECTION ID:', route.inspectionId)
      }

      if (!targetManholeId) {
        setCurrentQueue((previous) => {
          revokeQueuePreviews(previous)
          return []
        })
        setCurrentResults((previous) => {
          revokeResultPreviews(previous)
          return []
        })
        setCurrentManhole(null)
        setCurrentManholeSummary(null)
        return
      }

      const manhole = await manholeService.getManhole(targetManholeId)
      setCurrentManhole(manhole)

      if (!manhole) {
        setCurrentQueue((previous) => {
          revokeQueuePreviews(previous)
          return []
        })
        setCurrentResults((previous) => {
          revokeResultPreviews(previous)
          return []
        })
        setCurrentManholeSummary(null)
        return
      }

      const [queue, rawResults, manholeSummary] = await Promise.all([
        inspectionQueue.listQueue(targetManholeId),
        inspectionService.listByManhole(targetManholeId),
        summaryService.getManholeSummary(targetManholeId),
      ])

      const [queueWithPreviews, enrichedResults] = await Promise.all([
        enrichQueueForUi(queue),
        enrichResultsForUi(rawResults, project.manholes),
      ])

      setCurrentQueue((previous) => {
        revokeQueuePreviews(previous)
        return queueWithPreviews
      })
      setCurrentResults((previous) => {
        revokeResultPreviews(previous)
        if (route.key === 'results') {
          console.log('LOADED RESULTS:', enrichedResults)
        }
        return enrichedResults
      })
      setCurrentManholeSummary({ ...manholeSummary, projectId: targetProjectId })
    } finally {
      setLoading(false)
    }
  }, [refreshProjects, route])

  useEffect(() => {
    void refreshRouteData()
  }, [refreshRouteData])

  const currentProjectId = 'projectId' in route ? route.projectId : null
  const currentProjectDetail = currentProject as (Project & { manholes?: Manhole[] }) | null

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
          todayValue={new Date().toISOString().slice(0, 10)}
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

    if (route.key === 'upload' || route.key === 'upload-inspection') {
      const uploadProjectId = route.key === 'upload' ? route.projectId : currentProject?.id ?? ''
      const uploadManholeId = route.key === 'upload' ? route.manholeId : currentManhole?.id ?? ''

      return (
        <PhotoUploadPage
          online={online}
          projectName={currentProject?.name ?? 'Untitled project'}
          manholeLabel={currentManhole?.manholeId ?? 'Unassigned manhole'}
          queue={currentQueue}
          events={events}
          onBack={() => {
            if (!uploadProjectId || !uploadManholeId) {
              navigate('/')
              return
            }
            navigate(`/projects/${uploadProjectId}/manholes/${uploadManholeId}`)
          }}
          onAddFiles={async (files) => {
            await inspectionQueue.addFiles({
              projectId: uploadProjectId,
              manholeId: uploadManholeId,
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
              projectId: uploadProjectId,
              manholeId: uploadManholeId,
              files: sampleFiles,
            })
            await refreshRouteData()
          }}
          onRemoveFile={async (imageId) => {
            await inspectionQueue.removeFile(imageId)
            await refreshRouteData()
          }}
          onClearQueue={async () => {
            await inspectionQueue.clearManholeQueue(uploadManholeId)
            await refreshRouteData()
          }}
          onStartInspection={async () => {
            const result = await processor.processQueuedImages(uploadManholeId)
            console.log('PROCESS RESULT:', result)
            if (!result.success || !result.inspectionId) {
              throw new Error(result.message || 'Inspection processing failed')
            }

            const focusInspection = await inspectionService.getInspection(result.inspectionId)
            if (!focusInspection) {
              throw new Error('Inspection result was saved but could not be reloaded')
            }
            writeInspectionRouteMapEntry(result.inspectionId, focusInspection.projectId, focusInspection.manholeId)

            const [project, manhole, queue, rawResults, manholeSummary, rawProjectSummary] = await Promise.all([
              projectService.getProject(focusInspection.projectId),
              manholeService.getManhole(focusInspection.manholeId),
              inspectionQueue.listQueue(focusInspection.manholeId),
              inspectionService.listByManhole(focusInspection.manholeId),
              summaryService.getManholeSummary(focusInspection.manholeId),
              summaryService.getProjectSummary(focusInspection.projectId),
            ])

            const projectManholes = project?.manholes ?? []
            const [queueWithPreviews, enrichedResults] = await Promise.all([
              enrichQueueForUi(queue),
              enrichResultsForUi(rawResults, projectManholes),
            ])

            await refreshProjects()

            setCurrentProject(project)
            setProjectManholes(projectManholes)
            setCurrentManhole(manhole)
            setCurrentQueue((previous) => {
              revokeQueuePreviews(previous)
              return queueWithPreviews
            })
            setCurrentResults((previous) => {
              revokeResultPreviews(previous)
              return enrichedResults
            })
            setCurrentManholeSummary({ ...manholeSummary, projectId: focusInspection.projectId })
            setCurrentProjectSummary((previous) => {
              revokeSummaryPreviews(previous)
              return rawProjectSummary
            })
            setLoading(false)
            navigate(`/inspections/${result.inspectionId}/results`, { keepLoading: true })
            return {
              success: result.success,
              manholeId: result.manholeId,
              inspectionId: result.inspectionId,
              processed: result.completed ?? 0,
              failed: result.failed,
              completed: result.completed,
              total: result.total,
              resultIds: result.resultIds,
              queueStatus: result.queueStatus,
              message: result.message,
            }
          }}
        />
      )
    }

    if (route.key === 'results') {
      return (
        <InspectionResultsPage
          inspectionId={route.inspectionId}
          loading={loading}
          online={online}
          projectId={currentProject?.id ?? ''}
          projectName={currentProject?.name ?? 'Untitled project'}
          siteName={currentProject?.siteName}
          manholeLabel={currentManhole?.manholeId ?? 'Unassigned manhole'}
          results={currentResults}
          summary={currentManholeSummary}
          onBack={() => {
            if (!currentProject?.id || !currentManhole?.id) {
              navigate('/')
              return
            }
            navigate(`/projects/${currentProject.id}/manholes/${currentManhole.id}/upload`)
          }}
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
          onNext={() => {
            if (!currentProject?.id) {
              navigate('/')
              return
            }
            navigate(`/projects/${currentProject.id}/summary`)
          }}
        />
      )
    }

    if (route.key === 'summary') {
      return (
        <InspectionSummaryPage
          online={online}
          projectName={currentProject?.name ?? 'Untitled project'}
          projectId={route.projectId}
          projectSiteName={currentProject?.siteName}
          manholes={projectManholes}
          lastUpdatedAt={currentProjectDetail?.updatedAt}
          summary={currentProjectSummary}
          onBack={() => {
            if (!currentProjectId) {
              navigate('/')
              return
            }
            navigate(`/projects/${currentProjectId}/manholes/new`)
          }}
          onOpenFlagged={(inspectionId) => {
            const targetInspectionId = inspectionId ?? currentProjectSummary?.flaggedJoints[0]?.inspectionId
            if (!targetInspectionId) {
              navigate('/')
              return
            }
            navigate(`/inspections/${targetInspectionId}/results`)
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
