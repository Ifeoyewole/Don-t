import { db } from '../db'
import type {
  CreateProjectInput,
  Project,
  ProjectDetail,
  ProjectSummary,
  UpdateProjectInput,
} from '../types'
import { createId, createTimestamp } from '../utils/identity'

export const projectService = {
  async listProjects(): Promise<ProjectSummary[]> {
    const projects = await db.projects.orderBy('updatedAt').reverse().toArray()

    return Promise.all(
      projects.map(async (project) => {
        const manholeCount = await db.manholes.where('projectId').equals(project.id).count()
        const inspectionCount = await db.inspectionResults.where('projectId').equals(project.id).count()
        const failCount = await db.inspectionResults
          .where('projectId')
          .equals(project.id)
          .and((result) => result.status === 'FAIL')
          .count()
        const reviewCount = await db.inspectionResults
          .where('projectId')
          .equals(project.id)
          .and((result) => result.status === 'REVIEW')
          .count()

        return {
          ...project,
          manholeCount,
          inspectionCount,
          failCount,
          reviewCount,
        }
      }),
    )
  },

  async getProject(projectId: string): Promise<ProjectDetail | null> {
    const project = await db.projects.get(projectId)
    if (!project) {
      return null
    }

    const manholes = await db.manholes.where('projectId').equals(projectId).sortBy('createdAt')

    return {
      ...project,
      manholes,
    }
  },

  async createProject(input: CreateProjectInput): Promise<Project> {
    const timestamp = createTimestamp()
    const project: Project = {
      id: createId(),
      name: input.name.trim(),
      siteName: input.siteName?.trim() || undefined,
      createdAt: timestamp,
      updatedAt: timestamp,
    }

    await db.projects.add(project)
    return project
  },

  async updateProject(projectId: string, input: UpdateProjectInput): Promise<Project> {
    const existing = await db.projects.get(projectId)
    if (!existing) {
      throw new Error(`Project not found: ${projectId}`)
    }

    const updated: Project = {
      ...existing,
      name: input.name?.trim() ?? existing.name,
      siteName:
        input.siteName !== undefined
          ? input.siteName.trim() || undefined
          : existing.siteName,
      updatedAt: createTimestamp(),
    }

    await db.projects.put(updated)
    return updated
  },

  async deleteProject(projectId: string): Promise<void> {
    await db.transaction('rw', [db.projects, db.manholes, db.inspectionImages, db.inspectionBlobs, db.inspectionResults], async () => {
      const manholes = await db.manholes.where('projectId').equals(projectId).toArray()
      const manholeIds = new Set(manholes.map((manhole) => manhole.id))

      await db.projects.delete(projectId)
      await db.manholes.where('projectId').equals(projectId).delete()

      const images = await db.inspectionImages.where('projectId').equals(projectId).toArray()
      for (const image of images) {
        await db.inspectionImages.delete(image.id)
        await db.inspectionBlobs.delete(image.blobKey)
      }

      const results = await db.inspectionResults.where('projectId').equals(projectId).toArray()
      for (const result of results) {
        if (manholeIds.has(result.manholeId) || result.projectId === projectId) {
          await db.inspectionResults.delete(result.id)
        }
      }
    })
  },
}
