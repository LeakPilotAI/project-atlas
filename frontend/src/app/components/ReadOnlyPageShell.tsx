import type { ReactNode } from "react";

export function ReadOnlyPageShell({children}:{children:ReactNode}){
 return <div className="min-h-screen bg-[#07080b] text-zinc-200"><main className="mx-auto max-w-6xl space-y-5 px-5 py-7 sm:px-6 sm:py-8">{children}</main></div>
}
