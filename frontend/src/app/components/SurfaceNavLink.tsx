import Link from "next/link";
import type { ReactNode } from "react";

const VARIANT_CLASS = {
  primary: "rounded-lg border border-cyan-500/20 px-3 py-2 text-xs text-cyan-300",
  secondary: "rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400",
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
