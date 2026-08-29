"use client";

import { useEffect, useState, type ReactNode } from "react";

const API = "http://127.0.0.1:8000";

type Live = {
  updated_at?: string;
  note?: string;
  health?: Record<string, unknown>;
  gates?: Record<string, number>;
  funnel_24h?: Record<string, number>;
  why_no_trade?: { headline?: string; bottleneck?: string; session?: Record<string, number> };
  bottleneck?: string;
  warnings?: string[];
  activity?: Record<string, unknown>;
  journal?: Record<string, number | string>;
  open_trades?: Array<Record<string, unknown>>;
  opportunities?: Array<Record<string, unknown>>;
  quality_dips?: { last_scan_at?: string; candidates?: Array<Record<string, unknown>> };
  investment?: { enabled?: boolean; running?: boolean; last_cycle?: Record<string, unknown> };
};

const FUNNEL: Array<{ key: string; label: string }> = [
  { key: "markets", label: "Markets" },
  { key: "liquid", label: "Liquid" },
  { key: "evaluated", label: "Evaluated" },
  { key: "extension_passed", label: "Extension" },
  { key: "rsi_passed", label: "RSI" },
  { key: "quality_passed", label: "Quality" },
  { key: "rr_passed", label: "R:R" },
  { key: "qualified", label: "Qualified" },
  { key: "paper_trades", label: "Paper" },
];

function ago(iso?: unknown): string {
  if (!iso || typeof iso !== "string") return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(t).toLocaleString();
}

function n(v: unknown, d = 0): number {
  const x = Number(v);
  return Number.isFinite(x) ? x : d;
}

function fmt(v: unknown, digits = 2): string {
  const x = Number(v);
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function Dashboard() {
  const [live, setLive] = useState<Live | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let stop = false;
    async function load() {
      try {
        const res = await fetch(`${API}/api/live`);
        if (!res.ok) throw new Error(`live ${res.status}`);
        const data = (await res.json()) as Live;
        if (!stop) {
          setLive(data);
          setError(null);
        }
      } catch {
        if (!stop) setError("API not reachable on port 8000. Keep the Atlas window open.");
      }
    }
    load();
    const id = setInterval(() => {
      load();
      setTick((t) => t + 1);
    }, 8000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, []);

  if (!live && !error) {
    return (
      <div className="min-h-screen bg-[#07080b] text-zinc-200 flex items-center justify-center">
        <p className="text-sm tracking-wide text-zinc-500">Connecting to Atlas…</p>
      </div>
    );
  }

  const h = live?.health || {};
  const funnel = live?.funnel_24h || {};
  const journal = live?.journal || {};
  const why = live?.why_no_trade || {};
  const gates = live?.gates || {};
  const dips = live?.quality_dips?.candidates || [];
  const opens = live?.open_trades || [];
  const opps = live?.opportunities || [];
  const maxFunnel = Math.max(1, ...FUNNEL.map((s) => n(funnel[s.key])));

  return (
    <div className="min-h-screen bg-[#07080b] text-zinc-200">
      <header className="border-b border-white/5 bg-[#0b0d12]/90 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-emerald-500/80">Live command center</p>
            <h1 className="text-2xl font-semibold tracking-tight text-white">Project Atlas</h1>
            <p className="text-xs text-zinc-500 mt-1">
              Bot runs in the Atlas window. This page is watch-only. Discord is the alert feed.
            </p>
          </div>
          <div className="text-right text-xs text-zinc-500">
            <div>Refresh {tick === 0 ? "just now" : "every 8s"} · {ago(live?.updated_at)}</div>
            <div className={error ? "text-rose-400" : "text-emerald-400"}>
              {error ? "API down" : "API connected"}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}

        <section className="flex flex-wrap gap-2">
          <Pill label="Scanner" on={!!h.scanner} />
          <Pill label="Perp micro" on={!!h.perp_micro} />
          <Pill label="Paper" on={!!h.paper_tracker} />
          <Pill label="Discord" on={!!h.discord} />
          <Pill label="Quality dip" on={!!h.quality_dip} />
          <Pill label="HL data" on={h.hyperliquid_data === "OK"} />
          <span className="px-2.5 py-1 rounded-full text-[11px] border border-white/10 text-zinc-400">
            Liquid names {n(h.liquid_count)}
          </span>
          <span className="px-2.5 py-1 rounded-full text-[11px] border border-white/10 text-zinc-400">
            Last scan {ago(h.last_cycle_at)}
          </span>
        </section>

        <section className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-5 py-4">
          <p className="text-[11px] uppercase tracking-widest text-amber-400/80">Why no paper trade</p>
          <p className="text-lg text-zinc-100 mt-1">{why.headline || live?.bottleneck || "Waiting on first scan cycle."}</p>
          {live?.bottleneck && (
            <p className="text-sm text-zinc-500 mt-1">{String(live.bottleneck)}</p>
          )}
        </section>

        <section>
          <h2 className="text-sm font-medium text-zinc-400 mb-3">Last 24 hours — perp funnel</h2>
          <div className="grid grid-cols-3 md:grid-cols-9 gap-2">
            {FUNNEL.map((s) => {
              const val = n(funnel[s.key]);
              const hgt = Math.max(8, Math.round((val / maxFunnel) * 64));
              return (
                <div key={s.key} className="rounded-xl border border-white/8 bg-[#10131a] p-3">
                  <div className="h-16 flex items-end mb-2">
                    <div className="w-full rounded-sm bg-emerald-500/70" style={{ height: hgt }} />
                  </div>
                  <div className="text-lg font-semibold text-white tabular-nums">{val}</div>
                  <div className="text-[11px] text-zinc-500">{s.label}</div>
                </div>
              );
            })}
          </div>
          <p className="text-[11px] text-zinc-600 mt-2">
            Gates are sequential. Empty paper is normal until RSI {fmt(gates.rsi_long, 0)}/{fmt(gates.rsi_short, 0)},
            extension {fmt(gates.extension_pct, 1)}%, and R:R {fmt(gates.min_rr, 1)} all pass.
          </p>
        </section>

        <section className="grid md:grid-cols-4 gap-3">
          <Stat label="Paper open" value={n(journal.open)} />
          <Stat label="Paper closed" value={n(journal.closed)} />
          <Stat
            label="Win rate"
            value={`${(n(journal.winrate) * 100).toFixed(0)}%`}
            hint="from paper journal"
          />
          <Stat label="Avg R" value={fmt(journal.avg_r, 2)} />
        </section>

        <section className="grid lg:grid-cols-2 gap-4">
          <Card title="Open paper trades">
            {opens.length === 0 ? (
              <Empty text="No open paper trades. Bot is scanning — Discord fires when one qualifies." />
            ) : (
              <table className="w-full text-sm">
                <thead className="text-zinc-500 text-left text-xs">
                  <tr>
                    <th className="py-2">Symbol</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Mark</th>
                    <th>Stop</th>
                    <th>MFE R</th>
                  </tr>
                </thead>
                <tbody>
                  {opens.map((t, i) => (
                    <tr key={String(t.trade_id || i)} className="border-t border-white/5">
                      <td className="py-2 font-medium text-white">{String(t.symbol)}</td>
                      <td className={String(t.side) === "LONG" ? "text-emerald-400" : "text-rose-400"}>
                        {String(t.side || "—")}
                      </td>
                      <td className="tabular-nums">{fmt(t.entry, 4)}</td>
                      <td className="tabular-nums">{fmt(t.mark, 4)}</td>
                      <td className="tabular-nums">{fmt(t.stop, 4)}</td>
                      <td className="tabular-nums">{fmt(t.mfe_r, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card title="Live activity">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <Dt k="Last HL data" v={ago(live?.activity?.last_market_data)} />
              <Dt k="Last candles" v={ago(live?.activity?.last_candles)} />
              <Dt k="Last evaluation" v={ago(live?.activity?.last_evaluation)} />
              <Dt k="Last qualified" v={ago(live?.activity?.last_qualified)} />
              <Dt k="Last paper open" v={ago(live?.activity?.last_paper_open)} />
              <Dt k="Last Discord" v={ago(live?.activity?.last_discord_alert)} />
              <Dt k="Discord subs" v={String(live?.activity?.discord_subscribers ?? "—")} />
              <Dt k="Last error" v={h.last_error ? String(h.last_error) : "none"} />
            </dl>
          </Card>
        </section>

        <section className="grid lg:grid-cols-2 gap-4">
          <Card title="Quality dip watchlist (latest scan)">
            <p className="text-[11px] text-zinc-500 mb-3">
              Research ranking only. Same names Discord already DMs. Scan {ago(live?.quality_dips?.last_scan_at)}.
            </p>
            {dips.length === 0 ? (
              <Empty text="No dip snapshot yet — scanner runs about once an hour. Alerts still go to Discord." />
            ) : (
              <table className="w-full text-sm">
                <thead className="text-zinc-500 text-left text-xs">
                  <tr>
                    <th className="py-2">Symbol</th>
                    <th>Off high</th>
                    <th>5d</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {dips.slice(0, 10).map((d) => (
                    <tr key={String(d.symbol)} className="border-t border-white/5">
                      <td className="py-2 font-medium text-white">{String(d.symbol)}</td>
                      <td className="tabular-nums">{fmt(d.pct_from_high, 1)}%</td>
                      <td className="tabular-nums">{d.chg_5d == null ? "—" : `${fmt(d.chg_5d, 1)}%`}</td>
                      <td className="tabular-nums text-emerald-400">{fmt(d.score, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card title="Perp opportunities">
            {opps.length === 0 ? (
              <Empty text="No stored perp setups yet. Strict gates on purpose — do not loosen them from this page." />
            ) : (
              <table className="w-full text-sm">
                <thead className="text-zinc-500 text-left text-xs">
                  <tr>
                    <th className="py-2">Symbol</th>
                    <th>Status</th>
                    <th>Side</th>
                    <th>Entry</th>
                  </tr>
                </thead>
                <tbody>
                  {opps.slice(0, 12).map((o, i) => (
                    <tr key={i} className="border-t border-white/5">
                      <td className="py-2 font-medium text-white">{String(o.symbol)}</td>
                      <td className="text-zinc-400">{String(o.status)}</td>
                      <td>{String(o.recommendation || "—")}</td>
                      <td className="tabular-nums">{fmt(o.entry_price, 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </section>

        <section className="rounded-2xl border border-white/8 bg-[#10131a] px-5 py-4">
          <h2 className="text-sm font-medium text-zinc-300 mb-3">Active gates (not editable here)</h2>
          <div className="flex flex-wrap gap-2 text-xs">
            <Chip>RSI {fmt(gates.rsi_long, 0)} / {fmt(gates.rsi_short, 0)}</Chip>
            <Chip>Extension {fmt(gates.extension_pct, 1)}%</Chip>
            <Chip>Min R:R {fmt(gates.min_rr, 1)}</Chip>
            <Chip>Min volume {fmt(gates.min_volume, 0)}</Chip>
            <Chip>Max open {fmt(gates.max_open, 0)}</Chip>
          </div>
        </section>
      </main>
    </div>
  );
}

function Pill({ label, on }: { label: string; on: boolean }) {
  return (
    <span
      className={`px-2.5 py-1 rounded-full text-[11px] font-medium border ${
        on
          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
          : "bg-zinc-900 text-zinc-500 border-white/10"
      }`}
    >
      {label} {on ? "on" : "off"}
    </span>
  );
}

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-[#10131a] p-4">
      <p className="text-[11px] uppercase tracking-wider text-zinc-500">{label}</p>
      <p className="text-2xl font-semibold text-white mt-1 tabular-nums">{value}</p>
      {hint && <p className="text-[11px] text-zinc-600 mt-1">{hint}</p>}
    </div>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-[#10131a] p-5">
      <h2 className="text-sm font-medium text-zinc-300 mb-3">{title}</h2>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm text-zinc-500 leading-relaxed">{text}</p>;
}

function Dt({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="text-zinc-500">{k}</dt>
      <dd className="text-zinc-200 text-right">{v}</dd>
    </>
  );
}

function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="px-2.5 py-1 rounded-md bg-black/40 border border-white/10 text-zinc-300">{children}</span>
  );
}
