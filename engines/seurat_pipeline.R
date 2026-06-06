# SingleCell Easy - Seurat 分析流程（预留接口，MVP 阶段未实现）
#
# 设计目标：与 scanpy_pipeline.py 保持相同的输入/输出契约：
#   - 输入：命令行传入 config JSON（projectId/species/dataType/steps/uploadsDir/resultsDir/files）
#   - 输出：在 resultsDir 写出 result.json，结构为 { summary, figures, tables }
#
# 后续实现要点：
#   library(Seurat)
#   读取 10x/h5ad(via SeuratDisk) -> CreateSeuratObject
#   PercentageFeatureSet (线粒体) -> subset 质控
#   NormalizeData -> FindVariableFeatures -> ScaleData -> RunPCA
#   FindNeighbors -> FindClusters -> RunUMAP
#   FindAllMarkers (Wilcoxon)
#   导出 PNG 图与 CSV 表，写出 result.json
#
# 当前直接退出并提示未实现。
args <- commandArgs(trailingOnly = TRUE)
cat("Seurat 引擎为预留接口，MVP 阶段尚未实现。\n", file = stderr())
quit(status = 1)
