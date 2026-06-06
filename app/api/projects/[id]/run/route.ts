import { NextRequest, NextResponse } from "next/server";
import { getProject } from "@/lib/store";
import { executeProjectAnalysis } from "@/lib/engine";

export const dynamic = "force-dynamic";
export const maxDuration = 600;

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const project = getProject(params.id);
  if (!project) {
    return NextResponse.json({ error: "项目不存在" }, { status: 404 });
  }
  if (!project.files.length) {
    return NextResponse.json({ error: "请先上传数据文件" }, { status: 400 });
  }

  // 同步执行（MVP）：分析完成后再返回。前端轮询/等待。
  await executeProjectAnalysis(project);

  const updated = getProject(project.id);
  return NextResponse.json({ project: updated });
}
