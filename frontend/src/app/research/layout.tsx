import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Forward Evidence | Project Atlas",
  description: "Read-only Project Atlas forward research evidence and maturity diagnostics for human review.",
};

export default function ResearchLayout({ children }: { children: ReactNode }) {
  return children;
}
