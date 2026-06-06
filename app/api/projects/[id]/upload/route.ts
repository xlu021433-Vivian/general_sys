import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { getProject, saveProject, uploadsDir } from "@/lib/store";
import type { DataType, UploadedFile } from "@/lib/types";

export const dynamic = "force-dynamic";

// 根据上传文件名集合推断数据类型
function detectDataType(names: string[]): DataType | undefined {
  const lower = names.map((n) => n.toLowerCase());
  if (lower.some((n) => n.endsWith(".h5ad"))) return "h5ad";
  const hasMtx = lower.some((n) => n.includes("matrix.mtx") || n.endsWith(".mtx"));
  const hasBarcodes = lower.some((n) => n.includes("barcodes") || n.includes("barcode"));
  if (hasMtx && hasBarcodes) return "10x_mtx";
  // GEO 数据常打包成 zip：交给 Python 解压并宽容加载
  if (lower.some((n) => n.endsWith(".zip"))) return "10x_mtx";
  if (lower.some((n) => n.endsWith(".csv"))) return "marker_csv";
  return undefined;
}

// 把上传的 10x 文件名规范化为 scanpy read_10x_mtx 期望的标准名
function normalize10xName(original: string): string {
  const l = original.toLowerCase();
  const gz = l.endsWith(".gz");
  if (l.includes("matrix.mtx")) return gz ? "matrix.mtx.gz" : "matrix.mtx";
  if (l.includes("barcodes.tsv")) return gz ? "barcodes.tsv.gz" : "barcodes.tsv";
  if (l.includes("features.tsv") || l.includes("genes.tsv"))
    return gz ? "features.tsv.gz" : "features.tsv";
  return original;
}

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const project = getProject(params.id);
  if (!project) {
    return NextResponse.json({ error: "项目不存在" }, { status: 404 });
  }

  const form = await req.formData();
  const files = form.getAll("files") as File[];
  if (!files.length) {
    return NextResponse.json({ error: "未收到文件" }, { status: 400 });
  }

  const dir = uploadsDir(project.id);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  const originalNames = files.map((f) => f.name);
  const detected = detectDataType(originalNames);

  const stored: UploadedFile[] = [];
  for (const file of files) {
    const buf = Buffer.from(await file.arrayBuffer());
    const storedName =
      detected === "10x_mtx" ? normalize10xName(file.name) : file.name;
    fs.writeFileSync(path.join(dir, storedName), buf);
    stored.push({
      originalName: file.name,
      storedName,
      size: buf.length,
      uploadedAt: new Date().toISOString(),
    });
  }

  project.files = stored;
  project.dataType = detected;
  project.status = "uploaded";
  saveProject(project);

  return NextResponse.json({ project, detectedDataType: detected });
}
