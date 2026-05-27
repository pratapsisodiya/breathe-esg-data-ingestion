import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts'

interface Summary {
  by_scope: Record<string, number>
  by_source: Record<string, number>
  pending_count: number
  flagged_count: number
  total_tco2e: number
}

interface Run {
  id: number
  source_name: string
  source_type: string
  status: string
  rows_ok: number
  rows_failed: number
  rows_flagged: number
  started_at: string
  original_filename: string
}

const scopeColors: Record<string, string> = {
  SCOPE_1: '#3b82f6', // modern blue
  SCOPE_2: '#8b5cf6', // modern violet
  SCOPE_3: '#10b981', // modern emerald
}

const scopeLabels: Record<string, string> = {
  SCOPE_1: 'Scope 1 (Direct)',
  SCOPE_2: 'Scope 2 (Indirect)',
  SCOPE_3: 'Scope 3 (Value Chain)',
}

const statusColors: Record<string, string> = {
  DONE: 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20',
  RUNNING: 'bg-blue-500/10 text-blue-500 border border-blue-500/20',
  FAILED: 'bg-rose-500/10 text-rose-500 border border-rose-500/20',
  PENDING: 'bg-slate-500/10 text-slate-500 border border-slate-500/20',
}

function fmt(n: number) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Custom glassmorphic tooltip component for Recharts
const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload
    return (
      <div className="bg-slate-950/90 backdrop-blur-md border border-slate-800 p-3.5 rounded-xl shadow-xl">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{data.name}</p>
        <p className="text-lg font-bold text-white mt-1">
          {fmt(data.tCO2e)} <span className="text-xs font-medium text-slate-300">tCO2e</span>
        </p>
      </div>
    )
  }
  return null
}

export default function Dashboard() {
  const { data: summary, isLoading: sumLoading } = useQuery<Summary>({
    queryKey: ['summary'],
    queryFn: () => api.get('/api/records/summary/').then((r) => r.data),
  })

  const { data: runsData } = useQuery<{ results: Run[] }>({
    queryKey: ['runs'],
    queryFn: () => api.get('/api/ingestion/runs/').then((r) => r.data),
  })

  const scopeChartData = summary
    ? Object.entries(summary.by_scope).map(([scope, val]) => ({
        name: scopeLabels[scope] || scope,
        tCO2e: val,
        scope,
      }))
    : []

  const getSourceIcon = (type: string) => {
    if (type?.includes('SAP')) {
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      )
    }
    if (type?.includes('UTILITY') || type?.includes('ELECTRIC')) {
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      )
    }
    return (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
      </svg>
    )
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Emissions Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time Greenhouse Gas (GHG) footprint tracking and auditing activity.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 px-3 py-1.5 rounded-full font-semibold animate-pulse-soft self-start md:self-auto">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          Data Stream Live
        </div>
      </div>

      {sumLoading ? (
        <div className="flex items-center justify-center h-96">
          <div className="flex flex-col items-center gap-3">
            <svg className="animate-spin h-8 w-8 text-emerald-500" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <p className="text-slate-400 text-sm font-semibold">Loading emissions summary...</p>
          </div>
        </div>
      ) : (
        <div className="space-y-8 animate-fade-in">
          {/* Summary metrics cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="premium-card p-6 bg-gradient-to-br from-white to-slate-50/30 flex flex-col justify-between min-h-[140px] relative overflow-hidden group">
              <div className="absolute right-[-10px] top-[-10px] w-24 h-24 bg-emerald-500/5 rounded-full blur-xl group-hover:scale-125 transition-transform duration-500" />
              <div className="flex items-start justify-between">
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Total Carbon Footprint</p>
                <span className="text-emerald-500 bg-emerald-500/10 p-2 rounded-xl border border-emerald-500/15">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 002 2h2.945M11.01 9H9M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
              </div>
              <div className="mt-4">
                <p className="text-3xl font-extrabold text-slate-900 tracking-tight">{fmt(summary?.total_tco2e || 0)}</p>
                <p className="text-[11px] text-slate-400 font-medium mt-1">tCO2e (tonnes) combined</p>
              </div>
            </div>

            <div className="premium-card p-6 bg-gradient-to-br from-white to-slate-50/30 flex flex-col justify-between min-h-[140px] relative overflow-hidden group">
              <div className="absolute right-[-10px] top-[-10px] w-24 h-24 bg-amber-500/5 rounded-full blur-xl group-hover:scale-125 transition-transform duration-500" />
              <div className="flex items-start justify-between">
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Awaiting Review</p>
                <span className="text-amber-500 bg-amber-500/10 p-2 rounded-xl border border-amber-500/15">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </span>
              </div>
              <div className="mt-4">
                <p className="text-3xl font-extrabold text-amber-600 tracking-tight">{summary?.pending_count || 0}</p>
                <p className="text-[11px] text-slate-400 font-medium mt-1">Pending analyst sign-off</p>
              </div>
            </div>

            <div className="premium-card p-6 bg-gradient-to-br from-white to-slate-50/30 flex flex-col justify-between min-h-[140px] relative overflow-hidden group">
              <div className="absolute right-[-10px] top-[-10px] w-24 h-24 bg-red-500/5 rounded-full blur-xl group-hover:scale-125 transition-transform duration-500" />
              <div className="flex items-start justify-between">
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Flagged Anomalies</p>
                <span className="text-rose-500 bg-rose-500/10 p-2 rounded-xl border border-rose-500/15">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </span>
              </div>
              <div className="mt-4">
                <p className="text-3xl font-extrabold text-rose-600 tracking-tight">{summary?.flagged_count || 0}</p>
                <p className="text-[11px] text-slate-400 font-medium mt-1">Parser flags to resolve</p>
              </div>
            </div>

            <div className="premium-card p-6 bg-gradient-to-br from-white to-slate-50/30 flex flex-col justify-between min-h-[140px] relative overflow-hidden group">
              <div className="absolute right-[-10px] top-[-10px] w-24 h-24 bg-blue-500/5 rounded-full blur-xl group-hover:scale-125 transition-transform duration-500" />
              <div className="flex items-start justify-between">
                <p className="text-xs text-slate-500 font-bold uppercase tracking-wider">Scope 1 (Direct)</p>
                <span className="text-blue-500 bg-blue-500/10 p-2 rounded-xl border border-blue-500/15">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </span>
              </div>
              <div className="mt-4">
                <p className="text-3xl font-extrabold text-blue-600 tracking-tight">{fmt(summary?.by_scope?.SCOPE_1 || 0)}</p>
                <p className="text-[11px] text-slate-400 font-medium mt-1">Direct fuels & heating</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Chart Column */}
            <div className="lg:col-span-2 premium-card p-6 flex flex-col justify-between">
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-slate-900">Emissions by Scope Type</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Distribution across scopes in metric tonnes of CO2e</p>
                </div>
              </div>
              <div className="h-[250px] w-full mt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={scopeChartData} barSize={36} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="name"
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 11, fill: '#64748b', fontWeight: 500 }}
                    />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 11, fill: '#64748b', fontWeight: 500 }}
                    />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
                    <Bar dataKey="tCO2e" radius={[6, 6, 0, 0]}>
                      {scopeChartData.map((entry) => (
                        <Cell key={entry.scope} fill={scopeColors[entry.scope] || '#64748b'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Scope legend card */}
            <div className="premium-card p-6 flex flex-col justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-900">Scope Overview</h2>
                <p className="text-xs text-slate-400 mt-0.5">Quick references to GHG protocol definitions</p>
              </div>
              <div className="space-y-4 my-4 flex-1 flex flex-col justify-center">
                <div className="flex items-start gap-3.5 p-3 rounded-xl hover:bg-slate-50/50 transition-colors">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-500 mt-1 flex-shrink-0"></span>
                  <div>
                    <h3 className="text-xs font-bold text-slate-800">Scope 1 (Direct)</h3>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">Emissions from operations, company vehicles, and onsite combustion.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3.5 p-3 rounded-xl hover:bg-slate-50/50 transition-colors">
                  <span className="w-2.5 h-2.5 rounded-full bg-violet-500 mt-1 flex-shrink-0"></span>
                  <div>
                    <h3 className="text-xs font-bold text-slate-800">Scope 2 (Indirect)</h3>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">Purchased electricity, steam, heating, and cooling consumed by the firm.</p>
                  </div>
                </div>
                <div className="flex items-start gap-3.5 p-3 rounded-xl hover:bg-slate-50/50 transition-colors">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 mt-1 flex-shrink-0"></span>
                  <div>
                    <h3 className="text-xs font-bold text-slate-800">Scope 3 (Value Chain)</h3>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">All other indirect emissions, e.g. corporate travel, logistics, and vendor products.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Recent runs table */}
          <div className="premium-card overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-900">Recent Ingestion Runs</h2>
                <p className="text-xs text-slate-400 mt-0.5">Logs of files processed and normalized into the carbon ledger</p>
              </div>
            </div>
            <div className="divide-y divide-slate-100">
              {(runsData?.results || []).slice(0, 5).map((run) => (
                <div key={run.id} className="px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 hover:bg-slate-50/20 transition-colors">
                  <div className="flex items-center gap-3.5">
                    <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500 border border-slate-200/50">
                      {getSourceIcon(run.source_type || '')}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-800">{run.source_name}</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {run.original_filename} <span className="text-slate-300">·</span> {new Date(run.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between sm:justify-end gap-6">
                    <div className="flex gap-4 text-xs font-semibold">
                      <span className="text-emerald-600 bg-emerald-500/5 border border-emerald-500/10 px-2 py-0.5 rounded-lg">{run.rows_ok} parsed</span>
                      {run.rows_failed > 0 && (
                        <span className="text-rose-500 bg-rose-500/5 border border-rose-500/10 px-2 py-0.5 rounded-lg">{run.rows_failed} failed</span>
                      )}
                      {run.rows_flagged > 0 && (
                        <span className="text-amber-600 bg-amber-500/5 border border-amber-500/10 px-2 py-0.5 rounded-lg">{run.rows_flagged} flagged</span>
                      )}
                    </div>
                    <span className={`text-[10px] px-2.5 py-1 rounded-full font-bold uppercase tracking-wider ${statusColors[run.status] || 'bg-slate-100 text-slate-500'}`}>
                      {run.status}
                    </span>
                  </div>
                </div>
              ))}
              {!runsData?.results?.length && (
                <div className="px-6 py-12 flex flex-col items-center justify-center text-slate-400">
                  <span className="text-3xl">📭</span>
                  <p className="text-sm font-medium mt-3">No ingestion runs recorded yet.</p>
                  <p className="text-xs mt-1">Upload carbon data on the Ingest Data page.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
