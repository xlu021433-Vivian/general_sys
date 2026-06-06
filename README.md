# 单细胞分析助手 · SingleCell Easy（MVP）

零代码单细胞生信分析平台。面向不懂 R / Python / Linux 的科研人员：上传数据即可自动完成
质控、降维聚类、UMAP、Marker 识别、细胞类型辅助注释、差异/富集分析，并生成中文解读与报告。

## 技术栈

- **前端 + 后端**：Next.js 14（App Router + TypeScript）全栈
- **分析引擎**：Python + Scanpy（已实现）；Seurat (R) 为预留可插拔接口
- **AI 解读**：预留接口（`lib/ai.ts`），当前为中文模板占位，配置 `ANTHROPIC_API_KEY` 后可接入 Claude API
- **存储**：文件系统（`data/<projectId>/`），MVP 无数据库

## 目录结构

```
app/
  page.tsx                 首页 + 项目列表
  projects/new/            创建项目 + 上传文件
  projects/[id]/           项目详情：开始分析 / 结果展示 / AI 解读 / 报告
  api/projects/...         REST API（创建/上传/分析/解读/报告/产物下载）
lib/
  types.ts                 核心数据模型
  store.ts                 文件存储层
  engine.ts                引擎调度（Scanpy/Seurat）
  ai.ts                    AI 中文解读（预留接口）
engines/
  scanpy_pipeline.py       Scanpy 分析流程（核心）
  seurat_pipeline.R        Seurat 预留接口（未实现）
samples/
  sample_pbmc_like.h5ad    h5ad 示例数据
  10x_pbmc_like/           10X 三件套示例（mtx + barcodes + features）
  sample_markers.csv       marker 基因表示例
.venv/                     Python 虚拟环境（已装 scanpy/leidenalg/igraph）
data/                      运行时项目数据（gitignore）
```

## 本地运行

```bash
# 1. 安装前端依赖（已完成）
npm install

# 2. Python 环境（已在 .venv 中安装 scanpy 等依赖）
#    引擎默认调用 .venv/Scripts/python.exe（Windows）或 .venv/bin/python

# 3. 启动
npm run dev
# 打开 http://localhost:3000
```

## 使用流程

首页 → 创建分析项目 → 上传文件（h5ad / 10X 三件套 / marker CSV）→ 选物种 →
选分析步骤 → 开始分析 → 查看图表 → 生成 AI 中文解读 → 下载报告。

可用 `samples/sample_pbmc_like.h5ad` 测试完整流程。

## 支持的数据类型

| 类型 | 说明 |
|------|------|
| `.h5ad` | AnnData 格式，自动完整分析 |
| 10X `mtx` | matrix.mtx + barcodes.tsv + features.tsv（可 .gz），自动规范化命名 |
| marker `.csv` | marker 基因表，轻量处理 |

## 接入真实大模型（AI 解读）

编辑 `lib/ai.ts` 中的 `callClaude()`，使用 `@anthropic-ai/sdk` 调用 Claude API，
并设置环境变量 `ANTHROPIC_API_KEY`。接口签名不变，无需改动前端。

## 后续可扩展

- Seurat (R) 引擎实现（`engines/seurat_pipeline.R`，契约已对齐）
- 富集分析接入 gseapy / Enrichr
- 异步任务队列（当前为同步分析）
- 用户系统与数据库
```
