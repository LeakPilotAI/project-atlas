import type { ReactNode } from "react";

const LAYOUT_CLASS={surfaces:"mx-auto max-w-6xl space-y-5 px-5 py-7 sm:px-6 sm:py-8",evidence:"max-w-6xl mx-auto px-6 py-8 space-y-6"} as const;

export function ReadOnlyPageShell({children,layout="surfaces"}:{children:ReactNode;layout?:keyof typeof LAYOUT_CLASS}){
 return <div className="min-h-screen bg-[#07080b] text-zinc-200"><main className={LAYOUT_CLASS[layout]}>{children}</main></div>
}
