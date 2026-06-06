import { NextRequest, NextResponse } from "next/server";
import { getProject, saveProject } from "@/lib/store";
import { generateInterpretation } from "@/lib/ai";

export const dynamic = "force-dynamic";

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const project = getProject(params.id);
  if (!project) {
    return NextResponse.json({ error: "项目不存在" }, { status: 404 });
  }
  if (project.status !== "done") {
    return NextResponse.json({ error: "请先完成分析" }, { status: 400 });
  }

  const interpretation = await generateInterpretation(project);
  project.interpretation = interpretation;
  saveProject(project);

  return NextResponse.json({ interpretation });
}
