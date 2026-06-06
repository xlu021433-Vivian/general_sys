import Link from "next/link";
import { listProjects } from "@/lib/store";
import { SPECIES_LABELS, STATUS_LABELS } from "@/lib/types";

export const dynamic = "force-dynamic";

const FEATURES = [
  ["📤", "数据上传", "支持 h5ad、10X 矩阵、marker CSV"],
  ["🔬", "质量控制", "自动过滤低质量细胞"],
  ["🧩", "降维聚类", "PCA + Leiden 自动聚类"],
  ["🗺️", "UMAP 可视化", "二维投影直观展示"],
  ["🧬", "Marker 识别", "各群特征基因排序"],
  ["🏷️", "细胞注释", "经典 marker 辅助判断"],
  ["📊", "差异/富集", "差异基因与通路分析"],
  ["🤖", "AI 中文解读", "自动生成易懂结论"],
];

export default function HomePage() {
  const projects = listProjects();
  return (
    <>
      <section className="hero">
        <h1>不写一行代码，完成单细胞数据分析</h1>
        <p>
          面向不懂 R / Python / Linux 的科研人员：上传数据，自动完成质控、聚类、UMAP、Marker
          识别、细胞注释与富集分析，并生成中文解读报告。
        </p>
        <div className="cta">
          <Link href="/projects/new" className="btn">＋ 创建分析项目</Link>
        </div>
      </section>

      <div className="grid" style={{ marginTop: 32 }}>
        {FEATURES.map(([icon, t, d]) => (
          <div className="feature" key={t}>
            <div className="icon">{icon}</div>
            <h3>{t}</h3>
            <p>{d}</p>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>我的分析项目</h2>
        {projects.length === 0 ? (
          <p className="hint">还没有项目。点击右上角「＋ 新建分析」开始。</p>
        ) : (
          projects.map((p) => (
            <Link href={`/projects/${p.id}`} key={p.id} className="proj-row" style={{ color: "inherit" }}>
              <div>
                <div className="name">{p.name}</div>
                <div className="sub">
                  {SPECIES_LABELS[p.species]} · {p.engine} · {new Date(p.createdAt).toLocaleString("zh-CN")}
                </div>
              </div>
              <span className={`badge ${p.status}`}>{STATUS_LABELS[p.status]}</span>
            </Link>
          ))
        )}
      </div>
    </>
  );
}
