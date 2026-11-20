import type { ReactNode } from "react";

const EYEBROW_CLASS = {
  operational: "text-[11px] uppercase tracking-[0.22em] text-emerald-500/80",
  research: "text-[11px] uppercase tracking-[0.22em] text-cyan-400/80",
} as const;

export function PageIdentity({
  eyebrow,
  title,
  description,
  tone = "research",
  constrainDescription = false,
}: {
  eyebrow: string;
  title: string;
  description: ReactNode;
  tone?: keyof typeof EYEBROW_CLASS;
  constrainDescription?: boolean;
}) {
  return (
    <div>
      <p className={EYEBROW_CLASS[tone]}>{eyebrow}</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">{title}</h1>
      <p className={`mt-1 text-xs text-zinc-500${constrainDescription ? " max-w-2xl" : ""}`}>
        {description}
      </p>
    </div>
  );
}
