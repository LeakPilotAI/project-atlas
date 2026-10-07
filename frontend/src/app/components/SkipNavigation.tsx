export function SkipNavigation() {
  return (
    <a
      href="#main-content"
      className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-lg border border-cyan-400/40 bg-[#0b0d12] px-3 py-2 text-sm font-medium text-cyan-200 shadow-lg transition-transform focus:translate-y-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080b]"
    >
      Skip to main content
    </a>
  );
}
