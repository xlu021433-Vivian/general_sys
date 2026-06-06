import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { resultsDir } from "@/lib/store";

export const dynamic = "force-dynamic";

const MIME: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".csv": "text/csv; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".json": "application/json",
};

// 提供 data/<id>/results/<name> 下的产物（图/表）
export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string; name: string } }
) {
  // 防目录穿越
  const safe = path.basename(params.name);
  const filePath = path.join(resultsDir(params.id), safe);
  if (!filePath.startsWith(resultsDir(params.id)) || !fs.existsSync(filePath)) {
    return NextResponse.json({ error: "文件不存在" }, { status: 404 });
  }
  const ext = path.extname(safe).toLowerCase();
  const data = fs.readFileSync(filePath);
  return new NextResponse(data, {
    headers: {
      "Content-Type": MIME[ext] || "application/octet-stream",
      "Cache-Control": "no-store",
    },
  });
}
