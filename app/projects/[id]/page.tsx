import { getProject } from "@/lib/store";
import { notFound } from "next/navigation";
import ProjectDetail from "./ProjectDetail";

export const dynamic = "force-dynamic";

export default function Page({ params }: { params: { id: string } }) {
  const project = getProject(params.id);
  if (!project) notFound();
  return <ProjectDetail initial={project} />;
}
