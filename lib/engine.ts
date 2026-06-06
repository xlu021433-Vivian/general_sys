// 分析引擎调度层：根据 engine 选择 Scanpy(Python) 或 Seurat(R)
// MVP 阶段 Scanpy 为已实现路径，Seurat 为预留可插拔接口。
import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import type { Project } from "./types";
import { projectDir, uploadsDir, resultsDir, saveProject } from "./store";

// venv 中的 python，跨平台兼容
function pythonExe(): string {
  const win = path.join(process.cwd(), ".venv", "Scripts", "python.exe");
  const nix = path.join(process.cwd(), ".venv", "bin", "python");
  if (fs.existsSync(win)) return win;
  if (fs.existsSync(nix)) return nix;
  return process.env.PYTHON || "python";
}

export interface EngineResult {
  ok: boolean;
  log: string;
  error?: string;
  resultJson?: any;
}

// 运行分析。结果写入 data/<id>/results/，并返回 result.json 内容。
export function runAnalysis(project: Project): Promise<EngineResult> {
  if (project.engine === "seurat") {
    return runSeurat(project);
  }
  return runScanpy(project);
}

function runScanpy(project: Project): Promise<EngineResult> {
  const script = path.join(process.cwd(), "engines", "scanpy_pipeline.py");
  const config = {
    projectId: project.id,
    species: project.species,
    dataType: project.dataType,
    steps: project.steps,
    uploadsDir: uploadsDir(project.id),
    resultsDir: resultsDir(project.id),
    files: project.files.map((f) => f.storedName),
  };

  return new Promise((resolve) => {
    const env = { ...process.env, SETUPTOOLS_USE_DISTUTILS: "stdlib", MPLBACKEND: "Agg" };
    const proc = spawn(pythonExe(), [script, JSON.stringify(config)], {
      cwd: process.cwd(),
      env,
    });

    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d.toString()));
    proc.stderr.on("data", (d) => (stderr += d.toString()));

    proc.on("close", (code) => {
      const log = stderr + "\n" + stdout;
      const resultPath = path.join(resultsDir(project.id), "result.json");
      if (code === 0 && fs.existsSync(resultPath)) {
        try {
          const resultJson = JSON.parse(fs.readFileSync(resultPath, "utf-8"));
          resolve({ ok: true, log, resultJson });
          return;
        } catch (e: any) {
          resolve({ ok: false, log, error: "结果解析失败: " + e.message });
          return;
        }
      }
      resolve({
        ok: false,
        log,
        error: `分析进程退出码 ${code}。请检查上传文件格式是否正确。`,
      });
    });

    proc.on("error", (err) => {
      resolve({ ok: false, log: stderr, error: "无法启动分析进程: " + err.message });
    });
  });
}

// Seurat 预留接口：当前返回未实现提示，后续接入 R + Seurat 脚本。
function runSeurat(project: Project): Promise<EngineResult> {
  void project;
  return Promise.resolve({
    ok: false,
    log: "",
    error:
      "Seurat (R) 引擎为预留接口，MVP 阶段尚未实现。请在创建项目时选择 Scanpy 引擎。",
  });
}

// 后台执行分析并把结果写回 project.json
export async function executeProjectAnalysis(project: Project): Promise<void> {
  project.status = "running";
  project.error = undefined;
  saveProject(project);

  const result = await runAnalysis(project);

  if (result.ok && result.resultJson) {
    const r = result.resultJson;
    project.status = "done";
    project.log = result.log;
    project.summary = r.summary;
    project.figures = r.figures;
    project.tables = r.tables;
  } else {
    project.status = "failed";
    project.log = result.log;
    project.error = result.error;
  }
  saveProject(project);
}

export { projectDir };
