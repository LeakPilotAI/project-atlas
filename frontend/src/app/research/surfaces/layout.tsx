import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Research Surfaces | Project Atlas",
  description: "Read-only map of Project Atlas operator and research surfaces with authority boundaries preserved.",
};

export default function ResearchSurfacesLayout({ children }: { children: ReactNode }) {
  return children;
}
