# -*- coding: utf-8 -*-
"""
SingleCell Easy - Scanpy 发表级分析流程
被 Node 后端以子进程方式调用：
    python scanpy_pipeline.py '<config-json>'
config 字段见 lib/engine.ts（projectId/species/dataType/steps/uploadsDir/resultsDir/files，可选 params）。
所有产物写入 resultsDir，最终写出 result.json 供后端读取。

设计原则（面向"结果能用于论文"）：
- 采用单细胞领域标准流程（Scrublet 去双 / 多维 QC / Harmony 批次校正 / Leiden / Wilcoxon marker / GO·KEGG 富集）
- 图内标签一律英文（期刊投稿标准），中文解释放在报告与 AI 解读中
- 图表同时导出 PNG(300dpi) 与 PDF(矢量)，可直接排版
- 关键参数全部记录，便于撰写 Methods 与复现
"""
import os
import sys
import json
import gzip
import glob
import zipfile
import traceback

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 中文字体（仅报告/少量标题用得到；核心图用英文标签）
_installed = {f.name for f in font_manager.fontManager.ttflist}
for _cf in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC", "WenQuanYi Zen Hei"]:
    if _cf in _installed:
        plt.rcParams["font.sans-serif"] = [_cf, "DejaVu Sans"]
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.bbox"] = "tight"

import numpy as np
import pandas as pd
import scanpy as sc

sc.settings.verbosity = 1


def log(msg):
    print(f"[scanpy] {msg}", file=sys.stderr, flush=True)


# ---- 经典 marker（用于辅助注释，AddModuleScore 打分） ----
HUMAN_MARKERS = {
    "T cell": ["CD3D", "CD3E", "CD2", "IL7R"],
    "CD8 T cell": ["CD8A", "CD8B"],
    "B cell": ["CD79A", "CD79B", "MS4A1"],
    "Plasma cell": ["MZB1", "IGHG1", "JCHAIN"],
    "NK cell": ["NKG7", "GNLY", "KLRD1", "NCAM1"],
    "Monocyte/Macrophage": ["LYZ", "CD14", "FCGR3A", "C1QA"],
    "Dendritic cell": ["FCER1A", "CST3", "CD1C"],
    "Neutrophil": ["FCGR3B", "S100A8", "S100A9"],
    "Mast cell": ["CPA3", "TPSAB1", "MS4A2"],
    "Endothelial": ["PECAM1", "VWF", "CLDN5"],
    "Fibroblast": ["DCN", "COL1A1", "LUM"],
    "Epithelial": ["EPCAM", "KRT8", "KRT18"],
    "Platelet": ["PPBP", "PF4"],
}
MOUSE_MARKERS = {
    "T cell": ["Cd3d", "Cd3e", "Cd2", "Il7r"],
    "CD8 T cell": ["Cd8a", "Cd8b1"],
    "B cell": ["Cd79a", "Cd79b", "Ms4a1"],
    "Plasma cell": ["Mzb1", "Jchain"],
    "NK cell": ["Nkg7", "Gnly", "Klrd1", "Ncam1"],
    "Monocyte/Macrophage": ["Lyz2", "Cd14", "C1qa"],
    "Dendritic cell": ["Fcer1a", "Cst3", "Cd1c"],
    "Neutrophil": ["S100a8", "S100a9"],
    "Mast cell": ["Cpa3", "Mcpt4"],
    "Endothelial": ["Pecam1", "Vwf", "Cldn5"],
    "Fibroblast": ["Dcn", "Col1a1", "Lum"],
    "Epithelial": ["Epcam", "Krt8", "Krt18"],
}

# Enrichr 基因集库（GO + KEGG），用于富集分析
ENRICHR_LIBS_HUMAN = ["GO_Biological_Process_2021", "KEGG_2021_Human"]
ENRICHR_LIBS_MOUSE = ["GO_Biological_Process_2021", "KEGG_2019_Mouse"]


def savefig(results_dir, name):
    """同时导出 PNG(300dpi) 与 PDF(矢量)。"""
    base = os.path.join(results_dir, name)
    plt.savefig(base + ".png", dpi=300, bbox_inches="tight")
    try:
        plt.savefig(base + ".pdf", bbox_inches="tight")
    except Exception:
        pass
    plt.close()


def params_of(cfg):
    p = cfg.get("params") or {}
    return {
        "min_genes": int(p.get("min_genes", 200)),
        "min_cells": int(p.get("min_cells", 3)),
        "mito_threshold": float(p.get("mito_threshold", 0.2)),
        "n_top_genes": int(p.get("n_top_genes", 2000)),
        "n_pcs": int(p.get("n_pcs", 30)),
        "resolution": float(p.get("resolution", 0.8)),
        "do_doublet": bool(p.get("do_doublet", True)),
        "do_harmony": p.get("do_harmony", "auto"),  # auto|true|false
    }


# ============ GEO/NCBI 数据宽容加载 ============
# GEO 公共数据常见问题：文件带表头、features 列数不一、文件名/版本不统一、打包成 zip。
# scanpy.read_10x_mtx 对这些很挑剔，这里自写加载器逐一兜底，让"下载即能分析"。

def _extract_zips(updir):
    """解压目录下所有 .zip（GEO/用户常把三件套打包上传）。"""
    for zp in glob.glob(os.path.join(updir, "*.zip")):
        try:
            with zipfile.ZipFile(zp) as z:
                z.extractall(updir)
            log(f"已解压 {os.path.basename(zp)}")
        except Exception as e:
            log(f"解压失败 {zp}: {e}")


def _find(updir, *needles):
    """递归查找文件名包含任一关键字的文件（兼容嵌套文件夹）。"""
    for root, _dirs, fnames in os.walk(updir):
        for fn in fnames:
            low = fn.lower()
            if any(n in low for n in needles):
                return os.path.join(root, fn)
    return None


def _open_any(path):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") \
        else open(path, "rt", encoding="utf-8", errors="replace")


def _looks_like_barcode(tok):
    t = tok.strip().strip('"')
    # 典型 barcode: ACGT 串(可带 -1 后缀)；表头通常是 x/barcode/cell 等
    core = t.split("-")[0]
    return len(core) >= 8 and set(core.upper()) <= set("ACGTN")


def _read_barcodes(path):
    with _open_any(path) as fh:
        lines = [ln.rstrip("\n").split("\t")[0].strip().strip('"') for ln in fh if ln.strip()]
    if lines and not _looks_like_barcode(lines[0]):
        log(f"barcodes 检测到表头 '{lines[0]}'，已剥离")
        lines = lines[1:]
    return lines


def _read_features(path):
    """返回基因 symbol 列表。自动剥离表头、自动选 symbol 列。"""
    rows = []
    with _open_any(path) as fh:
        for ln in fh:
            if not ln.strip():
                continue
            rows.append([c.strip().strip('"') for c in ln.rstrip("\n").split("\t")])
    if not rows:
        raise ValueError("features/genes 文件为空")
    # 表头检测：首行含 'gene'/'ensembl'/'symbol'/'feature' 等字样
    header_kw = ("gene", "ensembl", "symbol", "feature", "name", "id")
    first_join = " ".join(rows[0]).lower()
    if any(k in first_join for k in header_kw) and not rows[0][0].startswith("ENSG") \
            and not rows[0][0].startswith("ENSMUS"):
        log(f"features 检测到表头 '{rows[0]}'，已剥离")
        rows = rows[1:]
    ncol = max(len(r) for r in rows)
    # 列含义：Ensembl ID | Symbol | type。symbol 取第 2 列；若仅 1 列则用之。
    sym_idx = 1 if ncol >= 2 else 0
    return [r[sym_idx] if len(r) > sym_idx else r[0] for r in rows]


def load_10x_flexible(updir):
    """宽容读取 10x/GEO 矩阵，返回 AnnData(cells × genes)。"""
    from scipy.io import mmread
    from scipy.sparse import csr_matrix
    import anndata as ad

    _extract_zips(updir)
    mtx = _find(updir, "matrix.mtx", ".mtx")
    bc = _find(updir, "barcodes.tsv", "barcode")
    ft = _find(updir, "features.tsv", "genes.tsv", "feature")
    if not (mtx and bc and ft):
        raise ValueError(f"未找到完整三件套 (matrix={bool(mtx)}, barcodes={bool(bc)}, features={bool(ft)})")
    log(f"读取矩阵: {os.path.basename(mtx)} / {os.path.basename(bc)} / {os.path.basename(ft)}")

    M = mmread(mtx).tocsr()            # 10x 约定：行=基因, 列=细胞
    barcodes = _read_barcodes(bc)
    genes = _read_features(ft)

    # 对齐方向（matrix 行=基因数 vs 基因列表长度）
    if M.shape[0] == len(genes) and M.shape[1] == len(barcodes):
        X = M.T.tocsr()               # 转成 细胞 × 基因
    elif M.shape[0] == len(barcodes) and M.shape[1] == len(genes):
        X = M.tocsr()
    else:
        raise ValueError(f"矩阵维度 {M.shape} 与 barcodes({len(barcodes)})/genes({len(genes)}) 不匹配")

    adata = ad.AnnData(X=csr_matrix(X))
    adata.obs_names = barcodes
    adata.var_names = genes
    adata.var_names_make_unique()
    adata.obs_names_make_unique()
    log(f"加载完成: {adata.n_obs} 细胞 × {adata.n_vars} 基因")
    return adata


def load_data(cfg):
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
        adata = load_10x_flexible(up)
    elif dtype == "marker_csv":
        csv = next((f for f in files if f.lower().endswith(".csv")), None)
        if not csv:
            raise ValueError("未找到 .csv 文件")
        return None, pd.read_csv(os.path.join(up, csv))
    else:
        raise ValueError(f"不支持的数据类型: {dtype}")

    adata.var_names_make_unique()
    # 识别样本/批次列（多样本则后续可做 Harmony）
    for key in ["sample", "Sample", "batch", "orig.ident", "orig_ident"]:
        if key in adata.obs.columns:
            adata.obs["sample"] = adata.obs[key].astype("category")
            break
    return adata, None


def step_qc(adata, cfg, P, figures, results_dir, summary):
    species = cfg.get("species", "human")
    # 线粒体 / 核糖体基因
    upper = adata.var_names.str.upper()
    adata.var["mt"] = upper.str.startswith("MT-")
    adata.var["ribo"] = upper.str.startswith(("RPS", "RPL"))
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt", "ribo"], inplace=True, percent_top=None)

    summary["nCells"] = int(adata.n_obs)
    summary["nGenes"] = int(adata.n_vars)
    m = summary.setdefault("metrics", {})
    m["原始细胞数"] = int(adata.n_obs)
    m["检测基因数"] = int(adata.n_vars)

    # 双细胞检测 (Scrublet)
    if P["do_doublet"]:
        try:
            sc.pp.scrublet(adata)
            n_dbl = int(adata.obs["predicted_doublet"].sum())
            m["预测双细胞数"] = n_dbl
            m["双细胞率"] = f"{100*n_dbl/adata.n_obs:.1f}%"
            adata = adata[~adata.obs["predicted_doublet"]].copy()
            log(f"Scrublet 去除双细胞 {n_dbl}")
        except Exception as e:
            log(f"Scrublet 跳过: {e}")
            m["双细胞检测"] = "跳过(数据过小或算法不适用)"

    # QC 小提琴图（英文标签）
    sc.pl.violin(adata, ["n_genes_by_counts", "total_counts", "pct_counts_mt"],
                 jitter=0.4, multi_panel=True, show=False)
    savefig(results_dir, "qc_violin")
    figures.append({"step": "qc", "title": "QC metrics distribution (genes / UMI / mito%)", "file": "qc_violin.png"})

    # QC 散点图
    sc.pl.scatter(adata, x="total_counts", y="n_genes_by_counts", color="pct_counts_mt", show=False)
    savefig(results_dir, "qc_scatter")
    figures.append({"step": "qc", "title": "UMI vs genes (colored by mito%)", "file": "qc_scatter.png"})

    # 过滤
    sc.pp.filter_cells(adata, min_genes=P["min_genes"])
    sc.pp.filter_genes(adata, min_cells=P["min_cells"])
    adata = adata[adata.obs["pct_counts_mt"] < P["mito_threshold"] * 100].copy()

    summary["nCellsAfterQC"] = int(adata.n_obs)
    m["质控后细胞数"] = int(adata.n_obs)
    m["线粒体阈值"] = f"{P['mito_threshold']*100:.0f}%"
    m["最少基因数/细胞"] = P["min_genes"]
    return adata


def step_cluster(adata, cfg, P, figures, results_dir, summary):
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=P["n_top_genes"])
    adata.raw = adata
    adata = adata[:, adata.var.highly_variable].copy()
    sc.pp.scale(adata, max_value=10)
    n_comps = min(P["n_pcs"], adata.n_obs - 1, adata.n_vars - 1)
    sc.tl.pca(adata, n_comps=n_comps)

    # 批次校正 Harmony（多样本时）
    rep = "X_pca"
    n_samples = adata.obs["sample"].nunique() if "sample" in adata.obs else 1
    want_harmony = P["do_harmony"] is True or (P["do_harmony"] == "auto" and n_samples > 1)
    m = summary.setdefault("metrics", {})
    if want_harmony and n_samples > 1:
        try:
            sc.external.pp.harmony_integrate(adata, "sample")
            rep = "X_pca_harmony"
            m["批次校正"] = f"Harmony (按 sample，{n_samples} 个样本)"
            log("Harmony 批次校正完成")
        except Exception as e:
            log(f"Harmony 跳过: {e}")
            m["批次校正"] = "未执行"
    else:
        m["批次校正"] = "单样本，无需"

    sc.pp.neighbors(adata, n_neighbors=15, use_rep=rep)
    sc.tl.leiden(adata, resolution=P["resolution"], flavor="igraph", n_iterations=2, directed=False)
    n_clusters = adata.obs["leiden"].nunique()
    summary["nClusters"] = int(n_clusters)
    m["聚类数(Leiden)"] = int(n_clusters)
    m["聚类分辨率"] = P["resolution"]
    m["主成分数(PCs)"] = n_comps
    return adata


def step_umap(adata, cfg, P, figures, results_dir, summary):
    if "X_pca" not in adata.obsm:
        log("UMAP 需先聚类，跳过"); return adata
    sc.tl.umap(adata)
    sc.pl.umap(adata, color="leiden", legend_loc="on data", show=False, title="UMAP (clusters)")
    savefig(results_dir, "umap")
    figures.append({"step": "umap", "title": "UMAP — Leiden clusters", "file": "umap.png"})

    # 多样本时额外出按样本着色的 UMAP（看批次/分布）
    if "sample" in adata.obs and adata.obs["sample"].nunique() > 1:
        sc.pl.umap(adata, color="sample", show=False, title="UMAP (samples)")
        savefig(results_dir, "umap_sample")
        figures.append({"step": "umap", "title": "UMAP — by sample", "file": "umap_sample.png"})
    return adata


def step_marker(adata, cfg, P, figures, tables, results_dir, summary):
    if "leiden" not in adata.obs:
        log("Marker 需先聚类，跳过"); return adata
    sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")
    res = adata.uns["rank_genes_groups"]
    groups = res["names"].dtype.names
    rows = []
    for g in groups:
        for rank in range(min(50, len(res["names"][g]))):
            rows.append({
                "cluster": g, "rank": rank + 1,
                "gene": res["names"][g][rank],
                "log2FC": round(float(res["logfoldchanges"][g][rank]), 3),
                "pval": float(res["pvals"][g][rank]),
                "pval_adj": float(res["pvals_adj"][g][rank]),
            })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(results_dir, "markers.csv"), index=False, encoding="utf-8-sig")
    tables.append({"step": "marker", "title": "Cluster marker genes (top50, Wilcoxon)", "file": "markers.csv"})

    # marker 热图 + 点图（dotplot，论文常用）
    try:
        sc.pl.rank_genes_groups_heatmap(adata, n_genes=5, show=False, show_gene_labels=True)
        savefig(results_dir, "marker_heatmap")
        figures.append({"step": "marker", "title": "Marker heatmap (top5 / cluster)", "file": "marker_heatmap.png"})
    except Exception as e:
        log(f"热图失败: {e}")
    try:
        sc.pl.rank_genes_groups_dotplot(adata, n_genes=5, show=False)
        savefig(results_dir, "marker_dotplot")
        figures.append({"step": "marker", "title": "Marker dot plot (top5 / cluster)", "file": "marker_dotplot.png"})
    except Exception as e:
        log(f"点图失败: {e}")
    return adata


def step_annotate(adata, cfg, P, figures, tables, results_dir, summary):
    if "leiden" not in adata.obs:
        return adata
    species = cfg.get("species", "human")
    markers = MOUSE_MARKERS if species == "mouse" else HUMAN_MARKERS
    use = adata.raw.to_adata() if adata.raw is not None else adata

    # 用 AddModuleScore 思路：对每种类型基因集打分，取每个 cluster 的均值最高者
    score_cols = {}
    for ctype, genes in markers.items():
        present = [g for g in genes if g in use.var_names]
        if not present:
            continue
        col = f"_score_{ctype}"
        sc.tl.score_genes(use, present, score_name=col)
        score_cols[ctype] = col

    cluster_anno = {}
    for cl in adata.obs["leiden"].cat.categories:
        mask = (adata.obs["leiden"] == cl).values
        best, best_score = "Unknown", -1e18
        for ctype, col in score_cols.items():
            s = float(np.nanmean(use.obs[col].values[mask]))
            if s > best_score:
                best_score, best = s, ctype
        cluster_anno[cl] = best

    df = pd.DataFrame([{"cluster": k, "predicted_cell_type": v} for k, v in cluster_anno.items()])
    df.to_csv(os.path.join(results_dir, "annotation.csv"), index=False, encoding="utf-8-sig")
    tables.append({"step": "annotate", "title": "Cell-type annotation (marker-score based)", "file": "annotation.csv"})

    adata.obs["cell_type"] = adata.obs["leiden"].map(cluster_anno).astype("category")
    if "X_umap" in adata.obsm:
        sc.pl.umap(adata, color="cell_type", show=False, title="UMAP (cell types)")
        savefig(results_dir, "umap_celltype")
        figures.append({"step": "annotate", "title": "UMAP — predicted cell types", "file": "umap_celltype.png"})

    # 细胞组成（按 cell type 计数；多样本则堆叠）
    try:
        if "sample" in adata.obs and adata.obs["sample"].nunique() > 1:
            comp = pd.crosstab(adata.obs["sample"], adata.obs["cell_type"], normalize="index")
            comp.plot(kind="bar", stacked=True, figsize=(8, 5), colormap="tab20")
            plt.ylabel("Fraction"); plt.title("Cell-type composition per sample"); plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        else:
            comp = adata.obs["cell_type"].value_counts()
            comp.plot(kind="bar", figsize=(8, 5))
            plt.ylabel("Cells"); plt.title("Cell-type composition")
        savefig(results_dir, "cell_composition")
        figures.append({"step": "annotate", "title": "Cell-type composition", "file": "cell_composition.png"})
        comp.to_csv(os.path.join(results_dir, "cell_composition.csv"), encoding="utf-8-sig")
        tables.append({"step": "annotate", "title": "Cell-type composition table", "file": "cell_composition.csv"})
    except Exception as e:
        log(f"组成图失败: {e}")
    return adata


def step_deg(adata, cfg, P, figures, tables, results_dir, summary):
    """差异分析：默认以 cluster0 vs rest 出火山图作为示范；marker 已覆盖各群差异。"""
    if "leiden" not in adata.obs:
        return adata
    if "rank_genes_groups" not in adata.uns:
        sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")
    res = adata.uns["rank_genes_groups"]
    g0 = res["names"].dtype.names[0]
    de = pd.DataFrame({
        "gene": res["names"][g0],
        "log2FC": res["logfoldchanges"][g0],
        "pval_adj": res["pvals_adj"][g0],
    })
    de["-log10padj"] = -np.log10(de["pval_adj"].clip(lower=1e-300))
    de["significant"] = (de["pval_adj"] < 0.05) & (de["log2FC"].abs() > 1)
    de.to_csv(os.path.join(results_dir, f"deg_cluster{g0}_vs_rest.csv"), index=False, encoding="utf-8-sig")
    tables.append({"step": "deg", "title": f"DEG: cluster {g0} vs rest", "file": f"deg_cluster{g0}_vs_rest.csv"})

    # 火山图
    try:
        plt.figure(figsize=(6, 5))
        plt.scatter(de["log2FC"], de["-log10padj"], s=6, c=np.where(de["significant"], "#d62728", "#bbbbbb"))
        plt.axhline(-np.log10(0.05), ls="--", c="gray", lw=0.8)
        plt.axvline(1, ls="--", c="gray", lw=0.8); plt.axvline(-1, ls="--", c="gray", lw=0.8)
        plt.xlabel("log2 fold change"); plt.ylabel("-log10 adjusted p")
        plt.title(f"Volcano: cluster {g0} vs rest")
        for _, r in de[de["significant"]].head(10).iterrows():
            plt.annotate(r["gene"], (r["log2FC"], r["-log10padj"]), fontsize=7)
        savefig(results_dir, f"volcano_cluster{g0}")
        figures.append({"step": "deg", "title": f"Volcano plot: cluster {g0} vs rest", "file": f"volcano_cluster{g0}.png"})
    except Exception as e:
        log(f"火山图失败: {e}")
    summary.setdefault("metrics", {})["差异分析"] = f"已计算 cluster{g0} vs rest（火山图+表）"
    return adata


def step_enrich(adata, cfg, P, figures, tables, results_dir, summary):
    """GO/KEGG 富集（gseapy/Enrichr，需联网；无网则降级并提示）。"""
    m = summary.setdefault("metrics", {})
    if "rank_genes_groups" not in adata.uns:
        m["富集分析"] = "无 marker，跳过"; return adata
    species = cfg.get("species", "human")
    libs = ENRICHR_LIBS_MOUSE if species == "mouse" else ENRICHR_LIBS_HUMAN
    res = adata.uns["rank_genes_groups"]
    g0 = res["names"].dtype.names[0]
    top_genes = [res["names"][g0][i] for i in range(min(150, len(res["names"][g0])))
                 if float(res["pvals_adj"][g0][i]) < 0.05 and float(res["logfoldchanges"][g0][i]) > 0.5]
    if len(top_genes) < 5:
        top_genes = list(res["names"][g0][:50])

    try:
        import gseapy as gp
        enr = gp.enrichr(gene_list=top_genes, gene_sets=libs, organism="human" if species != "mouse" else "mouse",
                         outdir=None, no_plot=True)
        rdf = enr.results.sort_values("Adjusted P-value").head(100)
        if rdf.empty:
            m["富集分析"] = f"已查询 Enrichr，但 cluster{g0} 的 {len(top_genes)} 个基因未命中显著通路"
            return adata
        rdf.to_csv(os.path.join(results_dir, f"enrichment_cluster{g0}.csv"), index=False, encoding="utf-8-sig")
        tables.append({"step": "enrich", "title": f"GO/KEGG enrichment: cluster {g0}", "file": f"enrichment_cluster{g0}.csv"})
        # 条形图 top15
        top = rdf.head(15).iloc[::-1]
        plt.figure(figsize=(8, 6))
        plt.barh(top["Term"].str.slice(0, 50), -np.log10(top["Adjusted P-value"].clip(lower=1e-300)), color="#4f46e5")
        plt.xlabel("-log10 adjusted p"); plt.title(f"Top enriched terms (cluster {g0})")
        savefig(results_dir, f"enrichment_cluster{g0}")
        figures.append({"step": "enrich", "title": f"Enrichment bar plot (cluster {g0})", "file": f"enrichment_cluster{g0}.png"})
        m["富集分析"] = f"GO/KEGG via Enrichr（cluster{g0}，{len(top_genes)} 基因，{len(rdf)} 条显著通路）"
        log("Enrichr 富集完成")
    except Exception as e:
        log(f"富集失败(可能无网络): {e}")
        m["富集分析"] = "未完成（Enrichr 需联网；离线环境请配置本地 GMT 基因集）"
        # 仍导出基因列表，便于用户自行富集
        pd.DataFrame({"gene": top_genes}).to_csv(
            os.path.join(results_dir, f"enrich_input_cluster{g0}.csv"), index=False, encoding="utf-8-sig")
        tables.append({"step": "enrich", "title": f"Enrichment input gene list (cluster {g0})", "file": f"enrich_input_cluster{g0}.csv"})
    return adata


def handle_marker_csv(cfg, df, results_dir, figures, tables, summary):
    df.to_csv(os.path.join(results_dir, "input_markers.csv"), index=False, encoding="utf-8-sig")
    tables.append({"step": "marker", "title": "Uploaded marker gene table", "file": "input_markers.csv"})
    summary["metrics"] = {"基因数": int(df.shape[0]), "列数": int(df.shape[1])}
    # 若有基因列，尝试富集
    gene_col = next((c for c in df.columns if c.lower() in ("gene", "genes", "symbol", "gene_symbol")), None)
    if gene_col:
        genes = df[gene_col].dropna().astype(str).unique().tolist()
        species = cfg.get("species", "human")
        libs = ENRICHR_LIBS_MOUSE if species == "mouse" else ENRICHR_LIBS_HUMAN
        try:
            import gseapy as gp
            enr = gp.enrichr(gene_list=genes, gene_sets=libs,
                             organism="human" if species != "mouse" else "mouse", outdir=None, no_plot=True)
            rdf = enr.results.sort_values("Adjusted P-value").head(100)
            if rdf.empty:
                summary["metrics"]["富集分析"] = f"已查询 Enrichr，但 {len(genes)} 个基因未命中显著通路"
            else:
                rdf.to_csv(os.path.join(results_dir, "enrichment.csv"), index=False, encoding="utf-8-sig")
                tables.append({"step": "enrich", "title": "GO/KEGG enrichment of uploaded genes", "file": "enrichment.csv"})
                summary["metrics"]["富集分析"] = f"GO/KEGG via Enrichr（{len(genes)} 基因，{len(rdf)} 条显著通路）"
        except Exception as e:
            log(f"CSV 富集失败: {e}")
            summary["metrics"]["富集分析"] = "未完成（Enrichr 需联网）"


def main():
    cfg = json.loads(sys.argv[1])
    results_dir = cfg["resultsDir"]
    os.makedirs(results_dir, exist_ok=True)
    steps = cfg.get("steps", [])
    P = params_of(cfg)

    figures, tables, summary = [], [], {}
    summary["params"] = P  # 记录参数，便于写 Methods 与复现

    try:
        adata, marker_df = load_data(cfg)
        if marker_df is not None:
            handle_marker_csv(cfg, marker_df, results_dir, figures, tables, summary)
        else:
            if "qc" in steps:
                adata = step_qc(adata, cfg, P, figures, results_dir, summary)
            if "cluster" in steps:
                adata = step_cluster(adata, cfg, P, figures, results_dir, summary)
            if "umap" in steps:
                adata = step_umap(adata, cfg, P, figures, results_dir, summary)
            if "marker" in steps:
                adata = step_marker(adata, cfg, P, figures, tables, results_dir, summary)
            if "annotate" in steps:
                adata = step_annotate(adata, cfg, P, figures, tables, results_dir, summary)
            if "deg" in steps:
                adata = step_deg(adata, cfg, P, figures, tables, results_dir, summary)
            if "enrich" in steps:
                adata = step_enrich(adata, cfg, P, figures, tables, results_dir, summary)
            # 保存处理后的对象，供用户下载/复用
            try:
                adata.write(os.path.join(results_dir, "processed.h5ad"))
                tables.append({"step": "qc", "title": "Processed AnnData object (.h5ad)", "file": "processed.h5ad"})
            except Exception as e:
                log(f"保存 h5ad 失败: {e}")

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
