import Link from "next/link";
import type { ReactNode } from "react";

const INTERACTION_CLASS =
  "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080b]";

const VARIANT_CLASS = {
  primary: `rounded-lg border border-cyan-500/20 px-3 py-2 text-xs text-cyan-300 ${INTERACTION_CLASS}`,
  secondary: `rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400 ${INTERACTION_CLASS}`,
} as const;

export function SurfaceNavLink({
  href,
  children,
  variant = "secondary",
}: {
  href: string;
  children: ReactNode;
  variant?: keyof typeof VARIANT_CLASS;
}) {
  return <Link href={href} className={VARIANT_CLASS[variant]}>{children}</Link>;
}
