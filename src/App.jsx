import { useState, useEffect } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler)

function App() {
  const [account, setAccount] = useState(null)
  const [positions, setPositions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        setLoading(true)
        const [a, p] = await Promise.all([
          fetch('/api/account'),
          fetch('/api/positions')
        ])
        if (!a.ok) throw new Error('Account API failed')
        if (!p.ok) throw new Error('Positions API failed')
        const accountData = await a.json()
        const positionsData = await p.json()
        if (!cancelled) {
          setAccount(accountData)
          setPositions(Array.isArray(positionsData) ? positionsData : [])
          setError(null)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    const id = setInterval(load, 5000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8">
      {/* Background glow blobs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-20 left-1/4 h-72 w-72 rounded-full bg-sky-500/20 blur-3xl" />
        <div className="absolute top-1/3 -right-20 h-80 w-80 rounded-full bg-blue-600/20 blur-3xl" />
        <div className="absolute -bottom-40 left-1/3 h-96 w-96 rounded-full bg-indigo-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 to-blue-600 text-white shadow-lg shadow-sky-500/20">
              <span className="text-sm font-bold">MT5</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-white">Account Dashboard</h1>
              <p className="text-xs text-slate-400">JustMarkets-Live2 · XAUUSD.m</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusChip label="Login" value={account?.login ?? '...'} />
            <StatusChip label="Server" value={account?.server ?? '...'} />
            <StatusChip
              label="Status"
              value={loading ? 'Loading' : error ? 'Offline' : 'Live'}
              active={!loading && !error}
            />
          </div>
        </header>

        <main className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Balance"
            value={account?.balance}
            prefix="$"
            trend={0}
          />
          <MetricCard
            title="Equity"
            value={account?.equity}
            prefix="$"
            trend={account?.profit}
          />
          <MetricCard
            title="Profit"
            value={account?.profit}
            prefix="$"
            accent
          />
          <MetricCard
            title="Symbol"
            value={account?.symbol ?? 'XAUUSD.m'}
            sub="Trading instrument"
            mono
          />
        </main>

        <section className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-2xl shadow-black/40 backdrop-blur-md">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-100">Open Positions</h2>
                  <p className="text-xs text-slate-400">Live MT5 positions for this account</p>
                </div>
                <span className="rounded-full bg-sky-500/10 px-2.5 py-1 text-xs font-medium text-sky-300 ring-1 ring-sky-500/20">
                  {positions.length} active
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-slate-400">
                      <th className="pb-3 font-medium">Ticket</th>
                      <th className="pb-3 font-medium">Type</th>
                      <th className="pb-3 font-medium">Volume</th>
                      <th className="pb-3 font-medium">Open Price</th>
                      <th className="pb-3 font-medium">SL / TP</th>
                      <th className="pb-3 font-medium text-right">Profit</th>
                    </tr>
                  </thead>
                  {positions.length === 0 && !loading ? (
                    <tbody>
                      <tr>
                        <td colSpan="6" className="py-10 text-center text-slate-500">
                          No open positions bound to this dashboard.
                        </td>
                      </tr>
                    </tbody>
                  ) : (
                    <tbody className="divide-y divide-white/5">
                      {positions.map((pos) => (
                        <tr
                          key={pos.ticket}
                          className="group transition-colors hover:bg-white/5"
                        >
                          <td className="py-3 font-mono text-slate-200">
                            {pos.ticket ?? '—'}
                          </td>
                          <td className="py-3">
                            <span
                              className={
                                'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ' +
                                (String(pos.type).toLowerCase().includes('buy')
                                  ? 'bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/20'
                                  : 'bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/20')
                              }
                            >
                              {String(pos.type).toLowerCase().includes('buy') ? 'BUY' : 'SELL'}
                            </span>
                          </td>
                          <td className="py-3 font-mono text-slate-200">
                            {Number(pos.volume).toFixed(2)}
                          </td>
                          <td className="py-3 font-mono text-slate-200">
                            {Number(pos.price_open).toFixed(5)}
                          </td>
                          <td className="py-3 text-slate-300">
                            {(Number(pos.sl) || 0).toFixed(5)} /{' '}
                            {(Number(pos.tp) || 0).toFixed(5)}
                          </td>
                          <td
                            className={`py-3 text-right font-mono ${
                              Number(pos.profit) > 0
                                ? 'text-emerald-300'
                                : Number(pos.profit) < 0
                                  ? 'text-rose-300'
                                  : 'text-slate-400'
                            }`}
                          >
                            {Number(pos.profit).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  )}
                </table>
              </div>
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-2xl shadow-black/40 backdrop-blur-md">
              <h3 className="text-sm font-semibold text-slate-100">Profit distribution</h3>
              <p className="text-xs text-slate-400">Per-open-position breakdown</p>
              <div className="mt-4">
                {positions.length === 0 && !loading ? (
                  <p className="py-8 text-center text-slate-500">No data yet</p>
                ) : (
                  <div className="space-y-3">
                    {positions.map((pos) => {
                      const profit = Number(pos.profit) || 0
                      const width = Math.min(100, Math.max(0, Math.abs(profit) / 50))
                      const positive = profit >= 0
                      return (
                        <div key={pos.ticket}>
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="font-mono text-slate-300">#{pos.ticket}</span>
                            <span
                              className={
                                positive
                                  ? 'text-emerald-300'
                                  : 'text-rose-300'
                              }
                            >
                              {profit.toFixed(2)}
                            </span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-slate-800">
                            <div
                              className={
                                'h-2 rounded-full transition-all duration-500 ' +
                                (positive ? 'bg-emerald-400' : 'bg-rose-400')
                              }
                              style={{ width: `${width}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            {positions.length > 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-2xl shadow-black/40 backdrop-blur-md">
                <h3 className="text-sm font-semibold text-slate-100">Risk snapshot</h3>
                <p className="text-xs text-slate-400">Aggregated from open positions</p>
                <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-400">Buy side</div>
                    <div className="text-lg font-semibold text-white">
                      {positions.filter((p) => String(p.type).toLowerCase().includes('buy')).length}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400">Sell side</div>
                    <div className="text-lg font-semibold text-white">
                      {positions.filter((p) => String(p.type).toLowerCase().includes('sell')).length}
                    </div>
                  </div>
                  <div className="col-span-2">
                    <div className="text-xs text-slate-400">Total exposure</div>
                    <div className="text-lg font-semibold text-white">
                      {positions.reduce((sum, p) => sum + (Number(p.volume) || 0), 0).toFixed(2)} lots
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        <footer className="py-6 text-center text-xs text-slate-500">
          Auto-refreshes every 5 seconds · React + Vite + Tailwind backend
        </footer>
      </div>
    </div>
  )
}

function MetricCard({ title, value, prefix = '', sub, mono, accent, trend }) {
  const numeric = typeof value === 'number' ? value : null
  const isNegative = typeof trend === 'number' && trend < 0
  const isPositive = typeof trend === 'number' && trend > 0

  return (
    <div className="group rounded-2xl border border-white/10 bg-white/[0.04] p-5 shadow-xl shadow-black/30 backdrop-blur-md transition-all duration-300 hover:-translate-y-1 hover:border-sky-400/40 hover:shadow-[0_24px_60px_rgba(15,23,42,0.6),0_0_30px_rgba(56,189,248,0.35)]">
      <div className="text-xs font-medium text-slate-400">{title}</div>
      {numeric !== null ? (
        <div
          className={
            'mt-2 text-2xl font-semibold tracking-tight ' +
            (accent
              ? 'text-sky-300'
              : isPositive
                ? 'text-emerald-300'
                : isNegative
                  ? 'text-rose-300'
                  : 'text-white')
          }
        >
          {prefix}
          {numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
      ) : (
        <div className="mt-2 text-2xl font-semibold tracking-tight text-white">
          {value ?? '—'}
        </div>
      )}
      {(sub || typeof trend === 'number') && (
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
          {typeof trend === 'number' && (
            <span className={isPositive ? 'text-emerald-300' : isNegative ? 'text-rose-300' : 'text-slate-300'}>
              {trend > 0 ? '+' : ''}{trend.toFixed(2)}
            </span>
          )}
          {sub && <span>{sub}</span>}
        </div>
      )}
    </div>
  )
}

function StatusChip({ label, value, active }) {
  return (
    <div
      className={
        'flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium backdrop-blur-md ' +
        (active
          ? 'border-sky-500/30 bg-sky-500/10 text-sky-200'
          : 'border-slate-700/60 bg-slate-900/40 text-slate-300')
      }
    >
      <span
        className={
          'h-2 w-2 rounded-full ' +
          (active
            ? 'animate-pulse bg-sky-400 shadow-[0_0_6px_rgba(56,189,248,0.8)]'
            : 'bg-slate-500')
        }
      />
      <span className="text-slate-400">{label}:</span>
      <span className="font-mono text-slate-100">{value}</span>
    </div>
  )
}

export default App
