# -*- coding: utf-8 -*-
"""
SingleCell Easy - Scanpy 分析流程
被 Node 后端以子进程方式调用：
    python scanpy_pipeline.py '<config-json>'
config 字段见 lib/engine.ts。
所有产物写入 resultsDir，最终写出 result.json 供后端读取。
"""
import os
import sys
import json
import glob
import traceback

# 无界面后端，避免服务器无显示环境报错
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 配置中文字体，避免图内中文标题显示为方块
_installed = {f.name for f in font_manager.fontManager.ttflist}
for _cf in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC", "WenQuanYi Zen Hei"]:
    if _cf in _installed:
        plt.rcParams["font.sans-serif"] = [_cf, "DejaVu Sans"]
        break
plt.rcParams["axes.unicode_minus"] = False
import numpy as np
import pandas as pd
import scanpy as sc

sc.settings.verbosity = 1


def log(msg):
    print(f"[scanpy] {msg}", file=sys.stderr, flush=True)


# 经典 marker 基因（极简版，用于辅助注释占位）
HUMAN_MARKERS = {
    "T 细胞": ["CD3D", "CD3E", "CD2"],
    "B 细胞": ["CD79A", "CD79B", "MS4A1"],
    "NK 细胞": ["NKG7", "GNLY", "KLRD1"],
    "单核/巨噬细胞": ["LYZ", "CD14", "FCGR3A"],
    "树突状细胞": ["FCER1A", "CST3"],
    "血小板": ["PPBP", "PF4"],
}
MOUSE_MARKERS = {
    "T 细胞": ["Cd3d", "Cd3e", "Cd2"],
    "B 细胞": ["Cd79a", "Cd79b", "Ms4a1"],
    "NK 细胞": ["Nkg7", "Gnly", "Klrd1"],
    "单核/巨噬细胞": ["Lyz2", "Cd14", "Fcgr3"],
    "树突状细胞": ["Fcer1a", "Cst3"],
}


def load_data(cfg):
    """根据数据类型加载为 AnnData。"""
    up = cfg["uploadsDir"]
    dtype = cfg.get("dataType")
    files = cfg.get("files", [])
    log(f"加载数据 dataType={dtype} files={files}")

    if dtype == "h5ad":
        h5 = next((f for f in files if f.lower().endswith(".h5ad")), None)
        if not h5:
            raise ValueError("未找到 .h5ad 文件")
        adata = sc.read_h5ad(os.path.join(up, h5))

    elif dtype == "10x_mtx":
        # 期望 uploads 目录下存在 matrix.mtx(.gz), barcodes.tsv(.gz), features/genes.tsv(.gz)
        adata = sc.read_10x_mtx(up, var_names="gene_symbols", cache=False)

    elif dtype == "marker_csv":
        # marker 基因表：仅做轻量处理，不构成完整单细胞对象
        csv = next((f for f in files if f.lower().endswith(".csv")), None)
        if not csv:
            raise ValueError("未找到 .csv 文件")
        df = pd.read_csv(os.path.join(up, csv))
        # 包装成一个最小 AnnData 以复用下游报告结构
        adata = None
        return adata, df
    else:
        raise ValueError(f"不支持的数据类型: {dtype}")

    adata.var_names_make_unique()
    return adata, None


def step_qc(adata, cfg, figures, results_dir, summary):
    species = cfg.get("species", "human")
    mito_prefix = "MT-" if species != "mouse" else "mt-"
    adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True, percent_top=None)

    summary["nCells"] = int(adata.n_obs)
    summary["nGenes"] = int(adata.n_vars)

    # QC 小提琴图
    sc.pl.violin(
        adata,
        ["n_genes_by_counts", "total_counts", "pct_counts_mt"],
        jitter=0.4, multi_panel=True, show=False,
    )
    f = "qc_violin.png"
    plt.savefig(os.path.join(results_dir, f), dpi=120, bbox_inches="tight")
    plt.close()
    figures.append({"step": "qc", "title": "质控指标分布（基因数/UMI/线粒体比例）", "file": f})

    # 过滤
    sc.pp.filter_cells(adata, min_genes=200)
    sc.pp.filter_genes(adata, min_cells=3)
    adata = adata[adata.obs["pct_counts_mt"] < 20].copy()
    summary["nCellsAfterQC"] = int(adata.n_obs)
    summary.setdefault("metrics", {})["质控后细胞数"] = int(adata.n_obs)
    summary["metrics"]["线粒体比例阈值"] = "20%"
    void = mito_prefix
    return adata


def step_cluster(adata, cfg, figures, results_dir, summary):
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=2000)
    adata.raw = adata
    adata = adata[:, adata.var.highly_variable].copy()
    sc.pp.scale(adata, max_value=10)
    sc.tl.pca(adata, n_comps=min(50, adata.n_obs - 1, adata.n_vars - 1))
    sc.pp.neighbors(adata, n_neighbors=15)
    sc.tl.leiden(adata, resolution=1.0)
    n_clusters = adata.obs["leiden"].nunique()
    summary["nClusters"] = int(n_clusters)
    summary.setdefault("metrics", {})["聚类数(Leiden)"] = int(n_clusters)
    return adata


def step_umap(adata, cfg, figures, results_dir, summary):
    if "X_pca" not in adata.obsm:
        log("UMAP 需要先聚类，跳过")
        return adata
    sc.tl.umap(adata)
    color = "leiden" if "leiden" in adata.obs else None
    sc.pl.umap(adata, color=color, legend_loc="on data", show=False, title="UMAP - 细胞聚类")
    f = "umap.png"
    plt.savefig(os.path.join(results_dir, f), dpi=120, bbox_inches="tight")
    plt.close()
    figures.append({"step": "umap", "title": "UMAP 降维聚类图", "file": f})
    return adata


def step_marker(adata, cfg, figures, tables, results_dir, summary):
    if "leiden" not in adata.obs:
        log("Marker 需要先聚类，跳过")
        return adata
    sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")
    # 导出每个 cluster 前若干 marker
    res = adata.uns["rank_genes_groups"]
    groups = res["names"].dtype.names
    rows = []
    for g in groups:
        names = res["names"][g][:20]
        lfc = res["logfoldchanges"][g][:20]
        pvals = res["pvals_adj"][g][:20]
        for rank, (n, l, p) in enumerate(zip(names, lfc, pvals), 1):
            rows.append({"cluster": g, "rank": rank, "gene": n,
                         "log2FC": round(float(l), 3), "pval_adj": float(p)})
    df = pd.DataFrame(rows)
    tf = "markers.csv"
    df.to_csv(os.path.join(results_dir, tf), index=False, encoding="utf-8-sig")
    tables.append({"step": "marker", "title": "各 Cluster Marker 基因 (Top20)", "file": tf})

    # marker 热图（top5）
    try:
        sc.pl.rank_genes_groups_heatmap(adata, n_genes=5, show=False, show_gene_labels=True)
        f = "marker_heatmap.png"
        plt.savefig(os.path.join(results_dir, f), dpi=120, bbox_inches="tight")
        plt.close()
        figures.append({"step": "marker", "title": "Marker 基因热图 (Top5/Cluster)", "file": f})
    except Exception as e:
        log(f"热图生成失败: {e}")
    return adata


def step_annotate(adata, cfg, figures, tables, results_dir, summary):
    if "leiden" not in adata.obs:
        return adata
    species = cfg.get("species", "human")
    markers = MOUSE_MARKERS if species == "mouse" else HUMAN_MARKERS
    # 基于平均表达的简单打分注释
    use = adata.raw.to_adata() if adata.raw is not None else adata
    cluster_anno = {}
    for cl in adata.obs["leiden"].cat.categories:
        mask = (adata.obs["leiden"] == cl).values
        best, best_score = "未知", -1e9
        for ctype, genes in markers.items():
            present = [g for g in genes if g in use.var_names]
            if not present:
                continue
            expr = use[mask, present].X
            score = float(np.asarray(expr.mean()))
            if score > best_score:
                best_score, best = score, ctype
        cluster_anno[cl] = best
    df = pd.DataFrame(
        [{"cluster": k, "predicted_cell_type": v} for k, v in cluster_anno.items()]
    )
    tf = "annotation.csv"
    df.to_csv(os.path.join(results_dir, tf), index=False, encoding="utf-8-sig")
    tables.append({"step": "annotate", "title": "细胞类型辅助注释（基于经典 marker）", "file": tf})

    adata.obs["cell_type"] = adata.obs["leiden"].map(cluster_anno).astype("category")
    if "X_umap" in adata.obsm:
        sc.pl.umap(adata, color="cell_type", show=False, title="UMAP - 细胞类型注释")
        f = "umap_celltype.png"
        plt.savefig(os.path.join(results_dir, f), dpi=120, bbox_inches="tight")
        plt.close()
        figures.append({"step": "annotate", "title": "UMAP 细胞类型注释图", "file": f})
    return adata


def step_deg(adata, cfg, figures, tables, results_dir, summary):
    # MVP：以 cluster 间 rank_genes_groups 结果作为差异分析代表，导出 top 表
    if "rank_genes_groups" not in adata.uns:
        if "leiden" in adata.obs:
            sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")
        else:
            return adata
    summary.setdefault("metrics", {})["差异分析"] = "已基于聚类计算组间差异基因"
    return adata


def step_enrich(adata, cfg, figures, tables, results_dir, summary):
    # 富集分析占位：MVP 暂以提示形式记录，预留接入 gseapy / Enrichr 的接口。
    summary.setdefault("metrics", {})["富集分析"] = "预留接口（可接入 gseapy/Enrichr）"
    note = os.path.join(results_dir, "enrichment_note.txt")
    with open(note, "w", encoding="utf-8") as fh:
        fh.write("富集分析为预留接口，后续可接入 gseapy / Enrichr 对 marker 基因做通路富集。")
    return adata


def handle_marker_csv(cfg, df, results_dir, figures, tables, summary):
    """仅上传 marker 基因表的轻量路径。"""
    tf = "input_markers.csv"
    df.to_csv(os.path.join(results_dir, tf), index=False, encoding="utf-8-sig")
    tables.append({"step": "marker", "title": "上传的 Marker 基因表", "file": tf})
    summary["metrics"] = {"基因数": int(df.shape[0]), "列数": int(df.shape[1])}
    summary.setdefault("metrics", {})["富集分析"] = "预留接口（可接入 gseapy/Enrichr）"


def main():
    cfg = json.loads(sys.argv[1])
    results_dir = cfg["resultsDir"]
    os.makedirs(results_dir, exist_ok=True)
    steps = cfg.get("steps", [])

    figures, tables = [], []
    summary = {}

    try:
        adata, marker_df = load_data(cfg)

        if marker_df is not None:
            handle_marker_csv(cfg, marker_df, results_dir, figures, tables, summary)
        else:
            if "qc" in steps:
                adata = step_qc(adata, cfg, figures, results_dir, summary)
            if "cluster" in steps:
                adata = step_cluster(adata, cfg, figures, results_dir, summary)
            if "umap" in steps:
                adata = step_umap(adata, cfg, figures, results_dir, summary)
            if "marker" in steps:
                adata = step_marker(adata, cfg, figures, tables, results_dir, summary)
            if "annotate" in steps:
                adata = step_annotate(adata, cfg, figures, tables, results_dir, summary)
            if "deg" in steps:
                adata = step_deg(adata, cfg, figures, tables, results_dir, summary)
            if "enrich" in steps:
                adata = step_enrich(adata, cfg, figures, tables, results_dir, summary)

        result = {"summary": summary, "figures": figures, "tables": tables}
        with open(os.path.join(results_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        log("分析完成")
    except Exception as e:
        traceback.print_exc()
        log(f"分析失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
