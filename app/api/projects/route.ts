import { NextRequest, NextResponse } from "next/server";
import { createProject, listProjects } from "@/lib/store";
import type { AnalysisStep, Engine, Species } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ projects: listProjects() });
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { name, description, species, engine, steps } = body as {
    name: string;
    description?: string;
    species: Species;
    engine: Engine;
    steps: AnalysisStep[];
  };

  if (!name || !species || !engine) {
    return NextResponse.json({ error: "缺少必要字段" }, { status: 400 });
  }

  const project = createProject({
    name,
    description,
    species,
    engine,
    steps: steps && steps.length ? steps : ["qc", "cluster", "umap", "marker"],
  });

  return NextResponse.json({ project });
}
