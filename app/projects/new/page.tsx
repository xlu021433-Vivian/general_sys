"use client";
import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { STEP_LABELS, SPECIES_LABELS } from "@/lib/types";
import type { AnalysisStep, Engine, Species } from "@/lib/types";

const ALL_STEPS = Object.keys(STEP_LABELS) as AnalysisStep[];
const DEFAULT_STEPS: AnalysisStep[] = ["qc", "cluster", "umap", "marker", "annotate"];

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [species, setSpecies] = useState<Species>("human");
  const [engine, setEngine] = useState<Engine>("scanpy");
  const [steps, setSteps] = useState<AnalysisStep[]>(DEFAULT_STEPS);
  const [files, setFiles] = useState<File[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function toggleStep(s: AnalysisStep) {
    setSteps((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  }

  function onFiles(list: FileList | null) {
    if (!list) return;
    setFiles(Array.from(list));
  }

  async function submit() {
    setError("");
    if (!name.trim()) return setError("请填写项目名称");
    if (!files.length) return setError("请至少上传一个数据文件");
    setBusy(true);
    try {
      // 1. 创建项目
      const orderedSteps = ALL_STEPS.filter((s) => steps.includes(s));
      const r1 = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description, species, engine, steps: orderedSteps }),
      });
      const d1 = await r1.json();
      if (!r1.ok) throw new Error(d1.error || "创建失败");
      const id = d1.project.id;

      // 2. 上传文件
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f));
      const r2 = await fetch(`/api/projects/${id}/upload`, { method: "POST", body: fd });
      const d2 = await r2.json();
      if (!r2.ok) throw new Error(d2.error || "上传失败");

      // 3. 跳转到项目详情页（在那里开始分析）
      router.push(`/projects/${id}`);
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>创建分析项目</h2>

      <label>项目名称 *</label>
      <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：PBMC 外周血单细胞分析" />

      <label>项目描述</label>
      <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="可选，简单描述样本来源与分析目的" />

      <label>物种 *</label>
      <div className="radio-row">
        {(Object.keys(SPECIES_LABELS) as Species[]).map((s) => (
          <div key={s} className={`radio-card ${species === s ? "active" : ""}`} onClick={() => setSpecies(s)}>
            <div className="t">{SPECIES_LABELS[s]}</div>
          </div>
        ))}
      </div>

      <label>分析引擎 *</label>
      <div className="radio-row">
        <div className={`radio-card ${engine === "scanpy" ? "active" : ""}`} onClick={() => setEngine("scanpy")}>
          <div className="t">Scanpy (Python)</div>
          <div className="d">推荐 · 已支持</div>
        </div>
        <div className={`radio-card ${engine === "seurat" ? "active" : ""}`} onClick={() => setEngine("seurat")}>
          <div className="t">Seurat (R)</div>
          <div className="d">预留接口 · 暂未实现</div>
        </div>
      </div>

      <label>分析步骤</label>
      <div className="checks">
        {ALL_STEPS.map((s) => (
          <label key={s} className={`check ${steps.includes(s) ? "active" : ""}`}>
            <input type="checkbox" checked={steps.includes(s)} onChange={() => toggleStep(s)} />
            {STEP_LABELS[s]}
          </label>
        ))}
      </div>

      <label>上传数据文件 *</label>
      <div
        className={`dropzone ${drag ? "drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles(e.dataTransfer.files); }}
      >
        <div style={{ fontSize: 28 }}>📁</div>
        <div>点击或拖拽文件到此处上传</div>
        <div className="hint">
          支持：.h5ad ｜ 10X 三件套(matrix.mtx + barcodes.tsv + features.tsv，可含 .gz) ｜
          GEO 下载的 .zip 压缩包 ｜ marker .csv
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          style={{ display: "none" }}
          onChange={(e) => onFiles(e.target.files)}
        />
      </div>

      <details style={{ marginTop: 10 }}>
        <summary style={{ cursor: "pointer", color: "#4f46e5", fontSize: 14 }}>
          📥 如何从 NCBI GEO 下载单细胞数据？
        </summary>
        <div className="hint" style={{ marginTop: 8, lineHeight: 1.7 }}>
          1. 打开 GEO 数据集页面（如 <code>ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSExxxxxx</code>），
          在底部 <b>Supplementary file</b> 中找到表达矩阵。<br />
          2. 单细胞数据通常是三个文件：<code>barcodes.tsv.gz</code>、
          <code>features.tsv.gz</code>（或 <code>genes.tsv.gz</code>）、<code>matrix.mtx.gz</code>。<br />
          3. 把这三个文件一起选中上传，<b>或打包成一个 .zip 直接上传</b> —— 平台会自动解压。<br />
          4. GEO 数据常见的<b>表头不规范、列数不一</b>等问题，平台已自动处理，无需手动删表头。<br />
          5. 若只给了原始测序数据(SRA / fastq)，需先用 Cell Ranger 比对成矩阵，暂不支持直接上传。
        </div>
      </details>

      {files.length > 0 && (
        <ul className="filelist">
          {files.map((f) => (
            <li key={f.name}>📄 {f.name} <span className="hint">({(f.size / 1024 / 1024).toFixed(2)} MB)</span></li>
          ))}
        </ul>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      <div style={{ marginTop: 24 }}>
        <button className="btn" onClick={submit} disabled={busy}>
          {busy && <span className="spinner" />}
          {busy ? "处理中…" : "创建并上传"}
        </button>
      </div>
    </div>
  );
}
