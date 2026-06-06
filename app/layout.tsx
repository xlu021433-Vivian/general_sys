import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "单细胞分析助手 SingleCell Easy",
  description: "零代码单细胞生信分析平台 — 上传数据，自动完成 QC、聚类、UMAP、Marker、注释与中文解读",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            🧬 单细胞分析助手 <span className="brand-en">SingleCell Easy</span>
          </Link>
          <nav>
            <Link href="/">首页</Link>
            <Link href="/projects/new" className="btn-nav">＋ 新建分析</Link>
          </nav>
        </header>
        <main className="container">{children}</main>
        <footer className="footer">
          MVP · 支持 h5ad / 10X(mtx) / marker CSV · 分析引擎 Scanpy（Seurat 预留）
        </footer>
      </body>
    </html>
  );
}
