import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SkipNavigation } from "@/app/components/SkipNavigation";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Command Center | Project Atlas",
  description: "Project Atlas operator command center for runtime status and bounded research visibility.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} antialiased`}>
        <SkipNavigation />
        {children}
        <nav aria-label="Atlas research navigation" className="fixed bottom-4 right-4 z-50">
          <a href="/research" className="rounded-lg border border-cyan-500/20 bg-[#0b0d12]/90 px-3 py-2 text-[11px] uppercase tracking-wider text-cyan-300 shadow-lg backdrop-blur hover:border-cyan-400/40 focus:outline-none focus-visible:border-cyan-300 focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080b]">
            Research Evidence
          </a>
        </nav>
      </body>
    </html>
  );
}