// AI 中文解读 - 预留接口（占位实现）
// 后续可接入 Claude API / 其他 LLM。当前根据分析结果用规则模板生成中文解读，
// 保证端到端流程可跑通，且替换为真实 LLM 时接口不变。
import type { Project } from "./types";
import { STEP_LABELS } from "./types";

export interface InterpretInput {
  project: Project;
}

// 真实 LLM 接入点：在此处替换为对 Claude API 的调用即可。
// 输入：结构化分析摘要 + 物种 + 步骤；输出：中文解读文本。
export async function generateInterpretation(project: Project): Promise<string> {
  // === 预留：若配置了 API Key，则走真实 LLM ===
  if (process.env.ANTHROPIC_API_KEY) {
    try {
      return await callClaude(project);
    } catch (e) {
      // 失败则降级到模板
    }
  }
  return templateInterpretation(project);
}

async function callClaude(project: Project): Promise<string> {
  // 预留接口占位：真实接入时在此构造 prompt 并请求 Claude API。
  // 例如使用 @anthropic-ai/sdk：
  //   const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  //   const msg = await client.messages.create({...});
  // 当前未实现，直接抛错以降级到模板。
  void project;
  throw new Error("Claude API 尚未接入，使用模板解读");
}

function templateInterpretation(project: Project): string {
  const s = project.summary || {};
  const m = s.metrics || {};
  const parts: string[] = [];

  parts.push(`# ${project.name} — AI 分析解读（示例模板）\n`);
  parts.push(
    `> 注：当前为占位解读，未接入大模型。配置 ANTHROPIC_API_KEY 后将自动生成更智能的中文解读。\n`
  );

  parts.push(`## 数据概况`);
  if (s.nCells != null) {
    parts.push(
      `本次分析的样本物种为 **${labelSpecies(project.species)}**，原始数据包含约 **${s.nCells}** 个细胞、**${s.nGenes}** 个基因。`
    );
  } else {
    parts.push(`本次分析的样本物种为 **${labelSpecies(project.species)}**。`);
  }

  if (project.steps.includes("qc")) {
    parts.push(`\n## 质量控制`);
    if (s.nCellsAfterQC != null) {
      parts.push(
        `经过质量控制过滤（去除低质量细胞、双细胞及高线粒体比例细胞），保留约 **${s.nCellsAfterQC}** 个高质量细胞用于后续分析。质控是单细胞分析的关键第一步，可有效降低技术噪音。`
      );
    } else {
      parts.push(`已执行质量控制流程。`);
    }
  }

  if (project.steps.includes("cluster")) {
    parts.push(`\n## 降维聚类`);
    if (s.nClusters != null) {
      parts.push(
        `通过标准化、高变基因筛选、PCA 降维及 Leiden 聚类，共识别出 **${s.nClusters}** 个细胞群（cluster）。每个 cluster 代表一群转录组特征相似的细胞，通常对应一种或一类细胞状态。`
      );
    }
  }

  if (project.steps.includes("umap")) {
    parts.push(`\n## UMAP 可视化`);
    parts.push(
      `UMAP 图将高维表达数据投影到二维平面，距离相近的细胞表达谱相似。可观察各 cluster 是否分离清晰，以初步判断细胞异质性。`
    );
  }

  if (project.steps.includes("marker")) {
    parts.push(`\n## Marker 基因`);
    parts.push(
      `已为每个 cluster 计算显著高表达的 marker 基因（Wilcoxon 检验）。这些基因是判断细胞类型的核心依据，可结合已知文献 marker 进行细胞类型注释。`
    );
  }

  if (project.steps.includes("annotate")) {
    parts.push(`\n## 细胞类型辅助注释`);
    parts.push(
      `基于经典 marker 基因对各 cluster 进行了初步细胞类型推测，仅供参考，建议结合生物学背景人工核实。`
    );
  }

  if (project.steps.includes("deg")) {
    parts.push(`\n## 差异分析`);
    parts.push(`已计算 cluster 间差异表达基因，可用于发现各细胞群特异表达的功能基因。`);
  }

  if (project.steps.includes("enrich")) {
    parts.push(`\n## 富集分析`);
    parts.push(
      `已对 marker / 差异基因进行通路富集（占位），可揭示各细胞群可能参与的生物学通路与功能。`
    );
  }

  if (Object.keys(m).length) {
    parts.push(`\n## 关键指标`);
    for (const [k, v] of Object.entries(m)) {
      parts.push(`- ${k}: ${v}`);
    }
  }

  parts.push(
    `\n---\n*以上解读由系统模板自动生成，结果仅供科研参考，不能替代专业生物信息学判断。*`
  );

  void STEP_LABELS;
  return parts.join("\n");
}

function labelSpecies(s: string): string {
  return s === "human" ? "人 Human" : s === "mouse" ? "小鼠 Mouse" : "其他 Other";
}
