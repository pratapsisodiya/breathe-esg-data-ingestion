import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

interface Source {
  id: number
  name: string
  source_type: string
}

interface Run {
  id: number
  source_name: string
  status: string
  rows_ok: number
  rows_failed: number
  rows_flagged: number
  error_log: { row: number; error: string }[]
  original_filename: string
  started_at: string
}

const statusColors: Record<string, string> = {
  DONE: 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20',
  FAILED: 'bg-rose-500/10 text-rose-500 border border-rose-500/20',
  PENDING: 'bg-slate-500/10 text-slate-500 border border-slate-500/20',
  RUNNING: 'bg-blue-500/10 text-blue-500 border border-blue-500/20',
}

export default function Ingest() {
  const [selectedSourceId, setSelectedSourceId] = useState<string>('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const qc = useQueryClient()

  const { data: sources } = useQuery<Source[]>({
    queryKey: ['sources'],
    queryFn: () => api.get('/api/ingestion/sources/').then((r) => r.data),
  })

  const { data: runsData } = useQuery<{ results: Run[] }>({
    queryKey: ['runs'],
    queryFn: () => api.get('/api/ingestion/runs/').then((r) => r.data),
  })

  const upload = useMutation({
    mutationFn: async () => {
      if (!selectedFile || !selectedSourceId) throw new Error('Select source and file')
      const form = new FormData()
      form.append('file', selectedFile)
      form.append('source_id', selectedSourceId)
      return api.post('/api/ingestion/upload/', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      setSelectedFile(null)
    },
  })

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) setSelectedFile(f)
  }

  const getSourceHelpText = (sourceId: string) => {
    const src = sources?.find(s => String(s.id) === sourceId)
    if (!src) return null
    if (src.source_type.includes('SAP')) {
      return (
        <div className="mt-3 bg-blue-50/50 border border-blue-100 rounded-xl p-3.5 text-xs text-blue-800">
          <p className="font-bold flex items-center gap-1.5 mb-1 text-[11px] uppercase tracking-wider">
            <span>⚙️</span> SAP mb51 Layout
          </p>
          <p className="leading-relaxed">Expects fields: <code className="bg-blue-100 px-1 rounded font-mono text-[10px]">Posting Date</code>, <code className="bg-blue-100 px-1 rounded font-mono text-[10px]">Material Description</code>, <code className="bg-blue-100 px-1 rounded font-mono text-[10px]">Quantity</code>, <code className="bg-blue-100 px-1 rounded font-mono text-[10px]">Base Unit of Measure</code>.</p>
        </div>
      )
    }
    if (src.source_type.includes('UTILITY')) {
      return (
        <div className="mt-3 bg-purple-50/50 border border-purple-100 rounded-xl p-3.5 text-xs text-purple-800">
          <p className="font-bold flex items-center gap-1.5 mb-1 text-[11px] uppercase tracking-wider">
            <span>⚡</span> Utility Portal Layout
          </p>
          <p className="leading-relaxed">Expects fields: <code className="bg-purple-100 px-1 rounded font-mono text-[10px]">Bill Start Date</code>, <code className="bg-purple-100 px-1 rounded font-mono text-[10px]">Bill End Date</code>, <code className="bg-purple-100 px-1 rounded font-mono text-[10px]">Usage kWh</code>, <code className="bg-purple-100 px-1 rounded font-mono text-[10px]">Account Number</code>.</p>
        </div>
      )
    }
    return (
      <div className="mt-3 bg-amber-50/50 border border-amber-100 rounded-xl p-3.5 text-xs text-amber-800">
        <p className="font-bold flex items-center gap-1.5 mb-1 text-[11px] uppercase tracking-wider">
          <span>✈️</span> Concur Travel Layout
        </p>
        <p className="leading-relaxed">Expects fields: <code className="bg-amber-100 px-1 rounded font-mono text-[10px]">Expense Date</code>, <code className="bg-amber-100 px-1 rounded font-mono text-[10px]">Expense Type</code>, <code className="bg-amber-100 px-1 rounded font-mono text-[10px]">Transaction Amount</code>, <code className="bg-amber-100 px-1 rounded font-mono text-[10px]">Segment Details</code>.</p>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Ingest Carbon Data</h1>
        <p className="text-slate-500 text-sm mt-1">
          Upload and normalize emissions reports from SAP exports, utility utility bills, or Concur expenses.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Upload Form Panel */}
        <div className="lg:col-span-2 space-y-6">
          <div className="premium-card p-6 bg-white">
            {/* Step 1: Select Source */}
            <div className="mb-5">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Step 1: Select Data Source
              </label>
              <select
                id="source-select"
                value={selectedSourceId}
                onChange={(e) => setSelectedSourceId(e.target.value)}
                className="w-full border border-slate-200 focus:border-emerald-500 rounded-xl px-4 py-3 text-sm font-medium focus:outline-none focus:ring-4 focus:ring-emerald-500/10 transition-all duration-200 bg-white"
              >
                <option value="">— Select configured source —</option>
                {(sources || []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.source_type.replace('_', ' ')})
                  </option>
                ))}
              </select>
              {getSourceHelpText(selectedSourceId)}
            </div>

            {/* Step 2: Drop Zone */}
            <div className="mb-6">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Step 2: Upload File
              </label>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                onClick={() => fileInput.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300 flex flex-col items-center justify-center ${
                  dragOver
                    ? 'border-emerald-400 bg-emerald-500/5'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
                }`}
              >
                <input
                  ref={fileInput}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  className="hidden"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                />

                {selectedFile ? (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-500">
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-800">{selectedFile.name}</p>
                      <p className="text-xs text-slate-400 mt-1 font-semibold">
                        {(selectedFile.size / 1024).toFixed(1)} KB — Click or drop to replace
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-slate-200/50 flex items-center justify-center text-slate-400">
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-700">Drag & drop files here</p>
                      <p className="text-xs text-slate-400 mt-1">Accepts CSV, XLSX or XLS formats</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {upload.isError && (
              <div className="flex items-center gap-2.5 text-rose-600 bg-rose-50/50 border border-rose-100 rounded-xl p-3.5 text-xs font-semibold mb-4">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                {(upload.error as any)?.response?.data?.error || 'Upload failed. Verify layout requirements.'}
              </div>
            )}

            {upload.isSuccess && (
              <div className="flex items-center gap-2.5 text-emerald-700 bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-3.5 text-xs font-semibold mb-4">
                <svg className="w-4.5 h-4.5 flex-shrink-0 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                ✓ Ingestion run finished. Scroll down to review results.
              </div>
            )}

            <button
              id="upload-submit"
              onClick={() => upload.mutate()}
              disabled={!selectedFile || !selectedSourceId || upload.isPending}
              className="w-full glow-btn-primary py-2.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2"
            >
              {upload.isPending ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Processing & normalizing data...
                </>
              ) : (
                'Upload & Ingest File'
              )}
            </button>
          </div>
        </div>

        {/* Info panel */}
        <div className="space-y-6">
          <div className="premium-card p-6 bg-gradient-to-br from-emerald-950 to-slate-950 text-white min-h-[200px] flex flex-col justify-between">
            <div>
              <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center mb-4">
                <span className="text-emerald-400 text-sm">💡</span>
              </div>
              <h3 className="text-sm font-bold text-white tracking-wide">Automatic Scope Assignment</h3>
              <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                Our parsing engine extracts emissions factors automatically based on post details, utility account numbers, and expense tags, assigning appropriate carbon emission values and greenhouse gas scopes (1, 2, or 3) transparently.
              </p>
            </div>
            <div className="pt-4 border-t border-slate-900/60 mt-4">
              <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-wider">Auditing Compliance</span>
              <p className="text-[11px] text-slate-400 mt-1">All ingest runs are logged permanently into the immutable audit trail.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Runs History */}
      <div className="premium-card overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="text-base font-bold text-slate-900">Ingestion History</h2>
          <p className="text-xs text-slate-400 mt-0.5">Audit log of data upload operations and execution outcomes</p>
        </div>
        <div className="divide-y divide-slate-100">
          {(runsData?.results || []).map((run) => (
            <RunItem key={run.id} run={run} />
          ))}
          {!runsData?.results?.length && (
            <div className="px-6 py-12 text-center text-slate-400">No runs recorded.</div>
          )}
        </div>
      </div>
    </div>
  )
}

function RunItem({ run }: { run: Run }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="px-6 py-4 hover:bg-slate-50/20 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <p className="text-sm font-bold text-slate-800">
              {run.source_name}
            </p>
            <span className="text-slate-300 text-xs">|</span>
            <p className="text-xs text-slate-400 font-mono">{run.original_filename}</p>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            {new Date(run.started_at).toLocaleString(undefined, {
              dateStyle: 'medium',
              timeStyle: 'short',
            })}
          </p>
        </div>

        <div className="flex items-center gap-6 self-end sm:self-auto">
          <div className="flex items-center gap-4 text-xs font-semibold">
            <span className="text-emerald-600 bg-emerald-500/5 border border-emerald-500/10 px-2 py-0.5 rounded-lg">{run.rows_ok} parsed OK</span>
            {run.rows_failed > 0 && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-rose-500 bg-rose-500/5 border border-rose-500/10 px-2 py-0.5 rounded-lg hover:bg-rose-500/10 transition-colors flex items-center gap-1 cursor-pointer"
              >
                {run.rows_failed} failed
                <svg className={`w-3.5 h-3.5 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
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

      {expanded && run.error_log && run.error_log.length > 0 && (
        <div className="mt-4 bg-slate-900 border border-slate-800 rounded-xl p-4 max-h-52 overflow-auto animate-fade-in">
          <p className="text-[11px] font-bold text-rose-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <svg className="w-4 h-4 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Incomplete Rows & Processing Errors
          </p>
          <div className="space-y-1.5 font-mono text-xs">
            {run.error_log.map((err, i) => (
              <div key={i} className="text-slate-300 flex items-start gap-2.5">
                <span className="text-rose-400/80 font-semibold select-none">Row {err.row}:</span>
                <span className="text-slate-400">{err.error}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
