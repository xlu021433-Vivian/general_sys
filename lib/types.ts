// 单细胞分析助手 - 核心数据类型定义

export type Species = "human" | "mouse" | "other";

export type Engine = "scanpy" | "seurat";

export type DataType = "h5ad" | "10x_mtx" | "marker_csv";

export type AnalysisStep =
  | "qc" // 质量控制
  | "cluster" // 降维聚类
  | "umap" // UMAP 可视化
  | "marker" // Marker 基因识别
  | "annotate" // 细胞类型辅助注释
  | "deg" // 差异分析
  | "enrich"; // 富集分析

export type ProjectStatus =
  | "created" // 已创建
  | "uploaded" // 已上传文件
  | "running" // 分析中
  | "done" // 分析完成
  | "failed"; // 分析失败

export interface UploadedFile {
  originalName: string;
  storedName: string;
  size: number;
  uploadedAt: string;
}

export interface AnalysisResultFigure {
  step: AnalysisStep;
  title: string;
  // 相对 data/<id>/results 的文件名
  file: string;
}

export interface AnalysisResultTable {
  step: AnalysisStep;
  title: string;
  file: string; // csv 文件名
}

export interface AnalysisSummary {
  nCells?: number;
  nGenes?: number;
  nCellsAfterQC?: number;
  nClusters?: number;
  // 各步骤的关键数值，供 AI 解读和报告使用
  metrics?: Record<string, number | string>;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  species: Species;
  engine: Engine;
  dataType?: DataType;
  steps: AnalysisStep[];
  status: ProjectStatus;
  files: UploadedFile[];
  createdAt: string;
  updatedAt: string;
  // 分析产物
  log?: string;
  error?: string;
  summary?: AnalysisSummary;
  figures?: AnalysisResultFigure[];
  tables?: AnalysisResultTable[];
  // AI 中文解读（占位）
  interpretation?: string;
}

export const STEP_LABELS: Record<AnalysisStep, string> = {
  qc: "质量控制 QC",
  cluster: "降维聚类",
  umap: "UMAP 可视化",
  marker: "Marker 基因识别",
  annotate: "细胞类型辅助注释",
  deg: "差异分析",
  enrich: "富集分析",
};

export const SPECIES_LABELS: Record<Species, string> = {
  human: "人 Human",
  mouse: "小鼠 Mouse",
  other: "其他 Other",
};

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  created: "已创建",
  uploaded: "已上传",
  running: "分析中",
  done: "已完成",
  failed: "失败",
};
