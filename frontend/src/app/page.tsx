"use client";

import { useEffect, useState } from "react";

interface Performance {
  total_closed: number;
  win_rate: number;
  avg_pnl: number;
  best_trade: number;
  worst_trade: number;
}

interface Opportunity {
  symbol: string;
  status: string;
  recommendation: string | null;
  confidence: number | null;
  entry_price: number;
  fired_at: string | null;
}

interface BacktestResult {
  symbol: string;
  total_trades: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl: number;
  best_trade: number;
  worst_trade: number;
  avg_mfe: number;
  avg_mae: number;
  expectancy: number;
  sample_trades?: Array<{
    side: string;
    entry: number;
    exit: number;
    pnl_pct: number;
    confidence: number;
  }>;
  error?: string;
}

interface Health {
  status: string;
  scanner_running: boolean;
  opportunity_tracker_running: boolean;
  paper_trade_tracker_running: boolean;
  discord_ready: boolean;
}

export default function Dashboard() {
  const [perf, setPerf] = useState<Performance | null>(null);
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [btSymbol, setBtSymbol] = useState("BTC");
  const [btLoading, setBtLoading] = useState(false);
  const [btResult, setBtResult] = useState<BacktestResult | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [pRes, oRes, hRes] = await Promise.all([
          fetch("http://localhost:8000/api/performance"),
          fetch("http://localhost:8000/api/opportunities"),
          fetch("http://localhost:8000/health"),
        ]);

        if (!pRes.ok || !oRes.ok) {
          throw new Error("Backend not reachable");
        }

        const p = await pRes.json();
        const o = await oRes.json();
        const h = hRes.ok ? await hRes.json() : null;

        setPerf(p);
        setOpps(o);
        setHealth(h);
        setError(null);
      } catch (err) {
        console.error(err);
        setError("Cannot connect to backend. Is the API running on port 8000?");
      } finally {
        setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  async function runBacktest() {
    if (!btSymbol.trim()) return;
    setBtLoading(true);
    setBtResult(null);
    try {
      const res = await fetch(
        `http://localhost:8000/api/backtest/${btSymbol.trim().toUpperCase()}`
      );
      const data = await res.json();
      setBtResult(data);
    } catch (err) {
      setBtResult({
        symbol: btSymbol,
        total_trades: 0,
        win_rate: 0,
        avg_pnl: 0,
        total_pnl: 0,
        best_trade: 0,
        worst_trade: 0,
        avg_mfe: 0,
        avg_mae: 0,
        expectancy: 0,
        error: "Network error talking to backend",
      });
    } finally {
      setBtLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
        <p className="text-lg">Loading Project Atlas...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <header className="mb-10 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Project Atlas</h1>
          <p className="text-zinc-400 mt-1">
            Advanced Trading & Liquidity Analysis System
          </p>
        </div>

        {health && (
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="Scanner" active={health.scanner_running} />
            <StatusPill label="Opportunities" active={health.opportunity_tracker_running} />
            <StatusPill label="Paper Trades" active={health.paper_trade_tracker_running} />
            <StatusPill label="Discord" active={health.discord_ready} />
          </div>
        )}
      </header>

      {error && (
        <div className="mb-8 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400">
          {error}
        </div>
      )}

      <section className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-12">
        <Card title="Closed Trades" value={perf?.total_closed ?? 0} />
        <Card title="Win Rate" value={`${perf?.win_rate ?? 0}%`} />
        <Card
          title="Avg PnL"
          value={`${(perf?.avg_pnl ?? 0) >= 0 ? "+" : ""}${perf?.avg_pnl ?? 0}%`}
          positive={(perf?.avg_pnl ?? 0) >= 0}
        />
        <Card title="Best Trade" value={`+${perf?.best_trade ?? 0}%`} positive />
        <Card title="Worst Trade" value={`${perf?.worst_trade ?? 0}%`} positive={false} />
      </section>

      <section className="mb-12">
        <h2 className="text-xl font-semibold mb-4">Backtest Runner</h2>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="flex flex-col sm:flex-row gap-3 mb-6">
            <input
              type="text"
              value={btSymbol}
              onChange={(e) => setBtSymbol(e.target.value.toUpperCase())}
              placeholder="Symbol (BTC, ETH, SOL...)"
              className="bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-zinc-500 w-full sm:w-48"
            />
            <button
              onClick={runBacktest}
              disabled={btLoading}
              className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium px-6 py-2.5 rounded-lg text-sm transition"
            >
              {btLoading ? "Running..." : "Run Backtest"}
            </button>
          </div>

          {btResult && !btResult.error && btResult.total_trades > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MiniStat label="Trades" value={btResult.total_trades} />
              <MiniStat label="Win Rate" value={`${btResult.win_rate}%`} />
              <MiniStat
                label="Avg PnL"
                value={`${btResult.avg_pnl >= 0 ? "+" : ""}${btResult.avg_pnl}%`}
                positive={btResult.avg_pnl >= 0}
              />
              <MiniStat
                label="Expectancy"
                value={`${btResult.expectancy >= 0 ? "+" : ""}${btResult.expectancy}%`}
                positive={btResult.expectancy >= 0}
              />
              <MiniStat label="Best" value={`+${btResult.best_trade}%`} positive />
              <MiniStat label="Worst" value={`${btResult.worst_trade}%`} positive={false} />
              <MiniStat label="Avg MFE" value={`+${btResult.avg_mfe}%`} />
              <MiniStat label="Avg MAE" value={`${btResult.avg_mae}%`} />
            </div>
          )}

          {btResult && btResult.total_trades === 0 && !btResult.error && (
            <p className="text-zinc-500 text-sm">
              No valid setups found for this symbol in recent data.
            </p>
          )}

          {btResult?.error && (
            <p className="text-rose-400 text-sm">{btResult.error}</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4">Recent Opportunities</h2>
        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-zinc-400">
              <tr>
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Recommendation</th>
                <th className="px-4 py-3 text-left">Confidence</th>
                <th className="px-4 py-3 text-left">Entry</th>
                <th className="px-4 py-3 text-left">Fired At</th>
              </tr>
            </thead>
            <tbody>
              {opps.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-zinc-500">
                    No opportunities yet — waiting for high-quality setups
                  </td>
                </tr>
              ) : (
                opps.map((o, i) => (
                  <tr key={i} className="border-t border-zinc-800 hover:bg-zinc-900/50">
                    <td className="px-4 py-3 font-medium">{o.symbol}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={o.status} />
                    </td>
                    <td className="px-4 py-3">
                      {o.recommendation ? (
                        <span
                          className={
                            o.recommendation === "LONG"
                              ? "text-emerald-400"
                              : "text-rose-400"
                          }
                        >
                          {o.recommendation}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {o.confidence ? `${o.confidence.toFixed(0)}%` : "—"}
                    </td>
                    <td className="px-4 py-3">${o.entry_price?.toFixed(4)}</td>
                    <td className="px-4 py-3 text-zinc-400">
                      {o.fired_at ? new Date(o.fired_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Card({
  title,
  value,
  positive,
}: {
  title: string;
  value: string | number;
  positive?: boolean;
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <p className="text-zinc-400 text-sm mb-1">{title}</p>
      <p
        className={`text-2xl font-semibold ${
          positive === true
            ? "text-emerald-400"
            : positive === false
            ? "text-rose-400"
            : "text-zinc-100"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function MiniStat({
  label,
  value,
  positive,
}: {
  label: string;
  value: string | number;
  positive?: boolean;
}) {
  return (
    <div className="bg-zinc-950 rounded-lg p-3 border border-zinc-800">
      <p className="text-zinc-500 text-xs mb-1">{label}</p>
      <p
        className={`text-sm font-medium ${
          positive === true
            ? "text-emerald-400"
            : positive === false
            ? "text-rose-400"
            : "text-zinc-200"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    monitoring: "bg-amber-500/20 text-amber-400",
    long_signal: "bg-emerald-500/20 text-emerald-400",
    short_signal: "bg-rose-500/20 text-rose-400",
    expired: "bg-zinc-500/20 text-zinc-400",
  };
  return (
    <span
      className={`px-2 py-1 rounded-md text-xs font-medium ${
        colors[status] || "bg-zinc-700 text-zinc-300"
      }`}
    >
      {status}
    </span>
  );
}

function StatusPill({ label, active }: { label: string; active: boolean }) {
  return (
    <span
      className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
        active
          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
          : "bg-zinc-800 text-zinc-500 border-zinc-700"
      }`}
    >
      {label} {active ? "●" : "○"}
    </span>
  );
}