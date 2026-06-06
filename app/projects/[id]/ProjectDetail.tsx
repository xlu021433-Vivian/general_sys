"use client";
import { useState } from "react";
import Link from "next/link";
import {
  STEP_LABELS,
  SPECIES_LABELS,
  STATUS_LABELS,
} from "@/lib/types";
import type { Project } from "@/lib/types";

export default function ProjectDetail({ initial }: { initial: Project }) {
  const [project, setProject] = useState<Project>(initial);
  const [running, setRunning] = useState(false);
  const [interpreting, setInterpreting] = useState(false);
  const [error, setError] = useState("");

  const base = `/api/projects/${project.id}`;

  async function refresh() {
    const r = await fetch(base, { cache: "no-store" });
    const d = await r.json();
    if (r.ok) setProject(d.project);
  }

  async function runAnalysis() {
    setError("");
    setRunning(true);
    setProject((p) => ({ ...p, status: "running" }));
    try {
      const r = await fetch(`${base}/run`, { method: "POST" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "分析失败");
      setProject(d.project);
    } catch (e: any) {
      setError(e.message);
      await refresh();
    } finally {
      setRunning(false);
    }
  }

  async function interpret() {
    setInterpreting(true);
    try {
      const r = await fetch(`${base}/interpret`, { method: "POST" });
      const d = await r.json();
      if (r.ok) setProject((p) => ({ ...p, interpretation: d.interpretation }));
    } finally {
      setInterpreting(false);
    }
  }

  const fileUrl = (name: string) => `${base}/file/${encodeURIComponent(name)}`;

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Link href="/">← 返回首页</Link>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>{project.name}</h2>
          <span className={`badge ${project.status}`}>{STATUS_LABELS[project.status]}</span>
        </div>
        {project.description && <p className="hint">{project.description}</p>}
        <div className="sub" style={{ color: "#6b7280", fontSize: 14 }}>
          物种：{SPECIES_LABELS[project.species]} ｜ 引擎：{project.engine} ｜ 数据类型：
          {project.dataType || "未识别"}
        </div>

        <div className="steps-flow">
          {project.steps.map((s, i) => (
            <span key={s} style={{ display: "contents" }}>
              <span className="s">{STEP_LABELS[s]}</span>
              {i < project.steps.length - 1 && <span className="arrow">→</span>}
            </span>
          ))}
        </div>

        <div style={{ marginTop: 12 }}>
          已上传 {project.files.length} 个文件：
          <span className="hint"> {project.files.map((f) => f.originalName).join("，")}</span>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div style={{ marginTop: 18, display: "flex", gap: 12, flexWrap: "wrap" }}>
          {project.status !== "running" && (
            <button className="btn" onClick={runAnalysis} disabled={running}>
              {running && <span className="spinner" />}
              {project.status === "done" || project.status === "failed" ? "重新分析" : "▶ 开始分析"}
            </button>
          )}
          {running && (
            <span className="alert alert-info" style={{ margin: 0 }}>
              <span className="spinner" style={{ borderColor: "#1e40af", borderTopColor: "transparent" }} />
              正在执行分析，单细胞数据计算可能需要数十秒到几分钟，请耐心等待…
            </span>
          )}
        </div>
      </div>

      {project.status === "failed" && (
        <div className="card">
          <h2>❌ 分析失败</h2>
          <div className="alert alert-error">{project.error}</div>
          {project.log && <pre className="log-box">{project.log.slice(-3000)}</pre>}
        </div>
      )}

      {project.status === "done" && (
        <>
          {project.summary?.metrics && (
            <div className="card">
              <h2>📈 关键指标</h2>
              <table style={{ borderCollapse: "collapse", width: "100%" }}>
                <tbody>
                  {Object.entries(project.summary.metrics).map(([k, v]) => (
                    <tr key={k}>
                      <td style={{ border: "1px solid #e5e7eb", padding: "8px 12px", fontWeight: 600 }}>{k}</td>
                      <td style={{ border: "1px solid #e5e7eb", padding: "8px 12px" }}>{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {project.figures && project.figures.length > 0 && (
            <div className="card">
              <h2>🖼️ 可视化结果</h2>
              {project.figures.map((f) => (
                <div className="result-fig" key={f.file}>
                  <h3>{f.title}</h3>
                  <img src={fileUrl(f.file)} alt={f.title} />
                </div>
              ))}
            </div>
          )}

          {project.tables && project.tables.length > 0 && (
            <div className="card">
              <h2>📋 结果数据表</h2>
              <ul>
                {project.tables.map((t) => (
                  <li key={t.file}>
                    {t.title} — <a href={fileUrl(t.file)} target="_blank" rel="noreferrer">下载 {t.file}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card">
            <h2>🤖 AI 中文解读</h2>
            {!project.interpretation ? (
              <>
                <p className="hint">点击生成对本次分析结果的中文解读（当前为占位模板，可接入大模型）。</p>
                <button className="btn btn-ghost" onClick={interpret} disabled={interpreting}>
                  {interpreting && <span className="spinner" style={{ borderColor: "#4f46e5", borderTopColor: "transparent" }} />}
                  {interpreting ? "生成中…" : "生成 AI 解读"}
                </button>
              </>
            ) : (
              <>
                <pre className="interp">{project.interpretation}</pre>
                <button className="btn btn-ghost" onClick={interpret} disabled={interpreting}>重新生成</button>
              </>
            )}
          </div>

          <div className="card">
            <h2>📥 下载报告</h2>
            <p className="hint">生成包含全部图表与解读的 HTML 报告，可在浏览器中打印为 PDF。</p>
            <a className="btn" href={`${base}/report`} target="_blank" rel="noreferrer">查看 / 下载报告</a>
          </div>
        </>
      )}
    </>
  );
}
