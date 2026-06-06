// 基于文件系统的简易项目存储（MVP 无数据库）
import fs from "fs";
import path from "path";
import crypto from "crypto";
import type { Project } from "./types";

// 运行时数据根目录：data/<projectId>/
export const DATA_ROOT = path.join(process.cwd(), "data");

function ensureDir(dir: string) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

export function projectDir(id: string) {
  return path.join(DATA_ROOT, id);
}
export function uploadsDir(id: string) {
  return path.join(projectDir(id), "uploads");
}
export function resultsDir(id: string) {
  return path.join(projectDir(id), "results");
}
function metaPath(id: string) {
  return path.join(projectDir(id), "project.json");
}

export function newId(): string {
  return crypto.randomBytes(6).toString("hex");
}

export function createProject(
  partial: Omit<Project, "id" | "createdAt" | "updatedAt" | "status" | "files">
): Project {
  const id = newId();
  const now = new Date().toISOString();
  const project: Project = {
    ...partial,
    id,
    status: "created",
    files: [],
    createdAt: now,
    updatedAt: now,
  };
  ensureDir(projectDir(id));
  ensureDir(uploadsDir(id));
  ensureDir(resultsDir(id));
  saveProject(project);
  return project;
}

export function saveProject(project: Project) {
  ensureDir(projectDir(project.id));
  project.updatedAt = new Date().toISOString();
  fs.writeFileSync(metaPath(project.id), JSON.stringify(project, null, 2), "utf-8");
}

export function getProject(id: string): Project | null {
  const p = metaPath(id);
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf-8")) as Project;
  } catch {
    return null;
  }
}

export function listProjects(): Project[] {
  ensureDir(DATA_ROOT);
  const ids = fs
    .readdirSync(DATA_ROOT, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);
  const projects = ids
    .map((id) => getProject(id))
    .filter((p): p is Project => p !== null);
  projects.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  return projects;
}

export function updateProject(id: string, patch: Partial<Project>): Project | null {
  const project = getProject(id);
  if (!project) return null;
  const updated = { ...project, ...patch };
  saveProject(updated);
  return updated;
}
