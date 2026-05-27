import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

interface LogEntry {
  id: number
  action: string
  actor_name: string
  record_id: number | null
  run_id: number | null
  description: string
  before_state: object | null
  after_state: object | null
  timestamp: string
}

const ACTION_COLORS: Record<string, string> = {
  INGESTION_STARTED: 'bg-blue-500/10 text-blue-600 border border-blue-500/20',
  INGESTION_COMPLETED: 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20',
  INGESTION_FAILED: 'bg-rose-500/10 text-rose-600 border border-rose-500/20',
  RECORD_APPROVED: 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20',
  RECORD_FLAGGED: 'bg-amber-500/10 text-amber-600 border border-amber-500/20',
  RECORD_REJECTED: 'bg-rose-500/10 text-rose-600 border border-rose-500/20',
  RECORD_EDITED: 'bg-slate-500/10 text-slate-600 border border-slate-500/20',
  RECORD_LOCKED: 'bg-slate-900 text-white border border-slate-950',
  BULK_APPROVED: 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20',
}

const ACTION_ICONS: Record<string, React.ReactNode> = {
  INGESTION_STARTED: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
    </svg>
  ),
  INGESTION_COMPLETED: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  INGESTION_FAILED: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  ),
  RECORD_APPROVED: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  ),
  RECORD_FLAGGED: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
    </svg>
  ),
  RECORD_REJECTED: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
}

export default function AuditLog() {
  const { data, isLoading } = useQuery<{ count: number; results: LogEntry[] }>({
    queryKey: ['audit'],
    queryFn: () => api.get('/api/audit/').then((r) => r.data),
  })

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Audit Trail</h1>
          <p className="text-slate-500 text-sm mt-1">
            Immutable system logs of ingestion activities and analyst review actions for compliance.
          </p>
        </div>
        <div className="text-xs font-semibold text-slate-500 bg-slate-100 border border-slate-200 px-3.5 py-2 rounded-xl self-start md:self-auto shadow-sm">
          📋 <span className="text-slate-700 font-bold">{data?.count ?? 0}</span> actions recorded
        </div>
      </div>

      {/* Main timeline box */}
      <div className="premium-card overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">Compliance Activity Ledger</h2>
        </div>

        {isLoading && (
          <div className="p-12 text-center text-slate-400">
            <div className="flex flex-col items-center justify-center gap-2">
              <svg className="animate-spin h-6 w-6 text-emerald-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="text-xs font-semibold">Reading audit logs...</span>
            </div>
          </div>
        )}

        <div className="divide-y divide-slate-100">
          {(data?.results || []).map((entry) => (
            <div key={entry.id} className="px-6 py-5 flex items-start gap-4 hover:bg-slate-50/20 transition-colors duration-200">
              {/* Left timeline visual node */}
              <div className="flex flex-col items-center flex-shrink-0 mt-1">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${
                  ACTION_COLORS[entry.action] || 'bg-slate-100 text-slate-500'
                }`}>
                  {ACTION_ICONS[entry.action] || (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                </div>
              </div>

              {/* Center event content */}
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-1.5">
                  <span
                    className={`text-[9px] px-2 py-0.5 rounded-md font-bold uppercase tracking-wider ${
                      ACTION_COLORS[entry.action] || 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {entry.action.replace(/_/g, ' ')}
                  </span>
                  <span className="text-slate-300 text-xs select-none">•</span>
                  <span className="text-xs text-slate-500 font-bold">{entry.actor_name}</span>
                  {entry.record_id && (
                    <span className="text-[10px] bg-slate-100 text-slate-600 font-mono font-semibold px-1.5 py-0.5 rounded border border-slate-200/50">
                      Record #{entry.record_id}
                    </span>
                  )}
                  {entry.run_id && (
                    <span className="text-[10px] bg-slate-100 text-slate-600 font-mono font-semibold px-1.5 py-0.5 rounded border border-slate-200/50">
                      Run #{entry.run_id}
                    </span>
                  )}
                </div>
                <p className="text-xs font-semibold text-slate-700 leading-relaxed">{entry.description}</p>

                {/* Split state diff visualization */}
                {(entry.before_state || entry.after_state) && (
                  <details className="mt-3 group/details">
                    <summary className="text-[11px] font-bold text-emerald-600 hover:text-emerald-700 cursor-pointer select-none outline-none flex items-center gap-1">
                      <svg className="w-3.5 h-3.5 transition-transform duration-200 group-open/details:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                      View state modifications
                    </summary>
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4 animate-fade-in">
                      {entry.before_state && (
                        <div className="bg-rose-500/[0.02] border border-rose-500/10 rounded-xl p-3.5">
                          <p className="text-[10px] font-bold text-rose-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                            Pre-Modification State
                          </p>
                          <pre className="text-[11px] text-rose-700 font-mono whitespace-pre-wrap leading-relaxed overflow-auto max-h-48 bg-rose-500/[0.01] p-2.5 rounded-lg border border-rose-500/5">
                            {JSON.stringify(entry.before_state, null, 2)}
                          </pre>
                        </div>
                      )}
                      {entry.after_state && (
                        <div className="bg-emerald-500/[0.02] border border-emerald-500/10 rounded-xl p-3.5">
                          <p className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse-soft"></span>
                            Post-Modification State
                          </p>
                          <pre className="text-[11px] text-emerald-700 font-mono whitespace-pre-wrap leading-relaxed overflow-auto max-h-48 bg-emerald-500/[0.01] p-2.5 rounded-lg border border-emerald-500/5">
                            {JSON.stringify(entry.after_state, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </details>
                )}
              </div>

              {/* Right time info */}
              <div className="text-[11px] text-slate-400 font-semibold whitespace-nowrap self-start mt-0.5">
                {new Date(entry.timestamp).toLocaleString(undefined, {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </div>
            </div>
          ))}

          {!isLoading && !data?.results?.length && (
            <div className="px-6 py-12 text-center text-slate-400">No events logged.</div>
          )}
        </div>
      </div>
    </div>
  )
}
