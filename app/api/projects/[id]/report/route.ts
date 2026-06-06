import { NextRequest, NextResponse } from "next/server";
import { getProject } from "@/lib/store";
import { SPECIES_LABELS, STEP_LABELS, STATUS_LABELS } from "@/lib/types";

export const dynamic = "force-dynamic";

// 生成可下载的 HTML 报告（用户可在浏览器中打印为 PDF）
export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const p = getProject(params.id);
  if (!p) return NextResponse.json({ error: "项目不存在" }, { status: 404 });

  const base = `/api/projects/${p.id}/file`;
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const figuresHtml = (p.figures || [])
    .map(
      (f) => `
      <div class="fig">
        <h3>${esc(f.title)}</h3>
        <img src="${base}/${encodeURIComponent(f.file)}" alt="${esc(f.title)}"/>
      </div>`
    )
    .join("");

  const tablesHtml = (p.tables || [])
    .map(
      (t) => `<li>${esc(t.title)} — <a href="${base}/${encodeURIComponent(t.file)}">${esc(t.file)}</a></li>`
    )
    .join("");

  const interp = p.interpretation
    ? `<section><h2>AI 中文解读</h2><pre class="interp">${esc(p.interpretation)}</pre></section>`
    : "";

  const metricsHtml = p.summary?.metrics
    ? Object.entries(p.summary.metrics)
        .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(String(v))}</td></tr>`)
        .join("")
    : "";

  const html = `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>${esc(p.name)} - 分析报告</title>
<style>
  body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;max-width:900px;margin:0 auto;padding:40px 24px;color:#1a202c;line-height:1.7}
  h1{border-bottom:3px solid #4f46e5;padding-bottom:12px}
  h2{color:#4f46e5;margin-top:36px}
  .meta{background:#f7f8fc;border-radius:8px;padding:16px 20px}
  .meta div{margin:4px 0}
  table{border-collapse:collapse;width:100%;margin:12px 0}
  td,th{border:1px solid #e2e8f0;padding:8px 12px;text-align:left}
  .fig{margin:20px 0}
  .fig img{max-width:100%;border:1px solid #eee;border-radius:6px}
  .interp{white-space:pre-wrap;background:#f7f8fc;padding:16px;border-radius:8px;font-family:inherit}
  .foot{margin-top:48px;color:#888;font-size:13px;border-top:1px solid #eee;padding-top:12px}
</style></head><body>
<h1>${esc(p.name)} — 单细胞分析报告</h1>
<div class="meta">
  <div><b>物种：</b>${SPECIES_LABELS[p.species]}</div>
  <div><b>分析引擎：</b>${p.engine === "scanpy" ? "Scanpy (Python)" : "Seurat (R)"}</div>
  <div><b>分析步骤：</b>${p.steps.map((s) => STEP_LABELS[s]).join("、")}</div>
  <div><b>状态：</b>${STATUS_LABELS[p.status]}</div>
  <div><b>创建时间：</b>${new Date(p.createdAt).toLocaleString("zh-CN")}</div>
</div>
${metricsHtml ? `<section><h2>关键指标</h2><table><tr><th>指标</th><th>数值</th></tr>${metricsHtml}</table></section>` : ""}
${figuresHtml ? `<section><h2>可视化结果</h2>${figuresHtml}</section>` : ""}
${tablesHtml ? `<section><h2>结果数据表</h2><ul>${tablesHtml}</ul></section>` : ""}
${interp}
<div class="foot">本报告由「单细胞分析助手 SingleCell Easy」自动生成。结果仅供科研参考。</div>
</body></html>`;

  return new NextResponse(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Disposition": `inline; filename="report-${p.id}.html"`,
    },
  });
}
