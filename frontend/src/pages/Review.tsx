import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

interface EmissionsRecord {
  id: number
  source_type: string
  scope: string
  category: string
  activity_description: string
  activity_quantity: number
  activity_unit: string
  co2e_kg: number | null
  co2e_tonnes: number | null
  period_start: string
  period_end: string
  location: string
  status: string
  needs_review: boolean
  needs_review_reason: string
  is_locked: boolean
  reviewed_by_name: string | null
  run_id: number
  review_note: string
}

const STATUS_BADGE: Record<string, string> = {
  PENDING: 'bg-slate-500/10 text-slate-600 border border-slate-500/10',
  APPROVED: 'bg-emerald-500/10 text-emerald-700 border border-emerald-500/10',
  FLAGGED: 'bg-amber-500/10 text-amber-700 border border-amber-500/10',
  REJECTED: 'bg-rose-500/10 text-rose-700 border border-rose-500/10',
}

const SOURCE_BADGE: Record<string, string> = {
  SAP_FUEL: 'bg-blue-500/10 text-blue-700 border border-blue-500/10',
  UTILITY: 'bg-purple-500/10 text-purple-700 border border-purple-500/10',
  CONCUR: 'bg-orange-500/10 text-orange-700 border border-orange-500/10',
}

const SCOPE_BADGE: Record<string, string> = {
  SCOPE_1: 'bg-blue-500/10 text-blue-700 border border-blue-500/20 font-bold',
  SCOPE_2: 'bg-violet-500/10 text-violet-700 border border-violet-500/20 font-bold',
  SCOPE_3: 'bg-emerald-500/10 text-emerald-700 border border-emerald-500/20 font-bold',
}

const SCOPE_LABEL: Record<string, string> = {
  SCOPE_1: 'Scope 1',
  SCOPE_2: 'Scope 2',
  SCOPE_3: 'Scope 3',
}

export default function Review() {
  const [filters, setFilters] = useState({
    status: '',
    scope: '',
    source_type: '',
    needs_review: '',
  })
  const [page, setPage] = useState(1)
  const [flaggingRecordId, setFlaggingRecordId] = useState<number | null>(null)
  const [flagNote, setFlagNote] = useState('')
  
  // Edit Modal State
  const [editingRecord, setEditingRecord] = useState<EmissionsRecord | null>(null)
  const [editQuantity, setEditQuantity] = useState('')
  const [editUnit, setEditUnit] = useState('')
  const [editNote, setEditNote] = useState('')
  const [editError, setEditError] = useState('')

  const qc = useQueryClient()

  const params = Object.fromEntries(
    Object.entries({ ...filters, page }).filter(([, v]) => v !== '')
  )

  const { data, isLoading } = useQuery<{ count: number; results: EmissionsRecord[] }>({
    queryKey: ['records', params],
    queryFn: () => api.get('/api/records/', { params }).then((r) => r.data),
  })

  const approve = useMutation({
    mutationFn: (id: number) => api.post(`/api/records/${id}/approve/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['records'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
    },
  })

  const flag = useMutation({
    mutationFn: ({ id, note }: { id: number; note: string }) =>
      api.post(`/api/records/${id}/flag/`, { note }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['records'] })
      setFlaggingRecordId(null)
      setFlagNote('')
    },
  })

  const reject = useMutation({
    mutationFn: (id: number) => api.post(`/api/records/${id}/reject/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['records'] }),
  })

  const editRecord = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { activity_quantity: number; activity_unit: string; review_note: string } }) =>
      api.patch(`/api/records/${id}/`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['records'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      setEditingRecord(null)
      setEditError('')
    },
    onError: (err: any) => {
      setEditError(err.response?.data?.error || 'Failed to update record. Verify your input.')
    }
  })

  const handleEditOpen = (rec: EmissionsRecord) => {
    setEditingRecord(rec)
    setEditQuantity(String(rec.activity_quantity))
    setEditUnit(rec.activity_unit)
    setEditNote(rec.review_note || '')
    setEditError('')
  }

  const getUnitOptions = (sourceType: string, category: string) => {
    if (sourceType === 'SAP_FUEL') {
      return ['L', 'GAL', 'KG', 'G', 'T', 'M3']
    }
    if (sourceType === 'UTILITY') {
      return ['kWh', 'MWh', 'GWh']
    }
    if (sourceType === 'CONCUR') {
      if (category.toLowerCase().includes('hotel')) {
        return ['room-nights']
      }
      return ['km', 'miles']
    }
    return ['units']
  }


  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Emissions Review</h1>
          <p className="text-slate-500 text-sm mt-1">
            Audit ledger workspace. Verify activity records, flag anomalies, and sign off for compliance.
          </p>
        </div>
        <div className="text-xs font-semibold text-slate-500 bg-slate-100 border border-slate-200 px-3.5 py-2 rounded-xl self-start md:self-auto shadow-sm">
          💡 <span className="text-slate-700">{data?.count ?? 0}</span> records matching
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="w-full flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 bg-white p-4 border border-slate-100 rounded-2xl shadow-sm">
        <div className="w-full lg:w-auto flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
          <select
            id="filter-status"
            value={filters.status}
            onChange={(e) => { setFilters(f => ({ ...f, status: e.target.value })); setPage(1) }}
            className="w-full sm:w-auto border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold bg-white focus:border-emerald-500 focus:outline-none focus:ring-4 focus:ring-emerald-500/5 transition-all duration-200 sm:min-w-[130px]"
          >
            <option value="">All Statuses</option>
            <option value="PENDING">Pending</option>
            <option value="APPROVED">Approved</option>
            <option value="FLAGGED">Flagged</option>
            <option value="REJECTED">Rejected</option>
          </select>

          <select
            id="filter-scope"
            value={filters.scope}
            onChange={(e) => { setFilters(f => ({ ...f, scope: e.target.value })); setPage(1) }}
            className="w-full sm:w-auto border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold bg-white focus:border-emerald-500 focus:outline-none focus:ring-4 focus:ring-emerald-500/5 transition-all duration-200 sm:min-w-[130px]"
          >
            <option value="">All Scopes</option>
            <option value="SCOPE_1">Scope 1</option>
            <option value="SCOPE_2">Scope 2</option>
            <option value="SCOPE_3">Scope 3</option>
          </select>

          <select
            id="filter-source"
            value={filters.source_type}
            onChange={(e) => { setFilters(f => ({ ...f, source_type: e.target.value })); setPage(1) }}
            className="w-full sm:w-auto border border-slate-200 rounded-xl px-3 py-2.5 text-xs font-semibold bg-white focus:border-emerald-500 focus:outline-none focus:ring-4 focus:ring-emerald-500/5 transition-all duration-200 sm:min-w-[140px]"
          >
            <option value="">All Source Types</option>
            <option value="SAP_FUEL">SAP Fuel & Proc.</option>
            <option value="UTILITY">Utility Electric</option>
            <option value="CONCUR">Concur Travel</option>
          </select>

          <label className="w-full sm:w-auto flex items-center justify-center sm:justify-start gap-2 text-xs font-bold text-slate-500 cursor-pointer border border-slate-200 px-3.5 py-2.5 rounded-xl bg-white hover:bg-slate-50 select-none transition-colors">
            <input
              type="checkbox"
              checked={filters.needs_review === 'true'}
              onChange={(e) => {
                setFilters(f => ({ ...f, needs_review: e.target.checked ? 'true' : '' }))
                setPage(1)
              }}
              className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
            />
            Anomalies Only
          </label>
        </div>

        <button
          onClick={() => { setFilters({ status: '', scope: '', source_type: '', needs_review: '' }); setPage(1) }}
          className="w-full lg:w-auto text-xs font-semibold text-slate-500 hover:text-slate-700 bg-slate-50 border border-slate-200 px-4 py-2.5 rounded-xl transition-colors cursor-pointer text-center"
        >
          Reset Filters
        </button>
      </div>

      {/* Table Container */}
      <div className="premium-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 border-b border-slate-100">
                <th className="px-5 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Source / Scope</th>
                <th className="px-5 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Description</th>
                <th className="hidden md:table-cell px-5 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider text-right">Quantity</th>
                <th className="px-5 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider text-right">Calculated tCO2e</th>
                <th className="hidden sm:table-cell px-5 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Period</th>
                <th className="px-5 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Audit Status</th>
                <th className="px-5 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading && (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <svg className="animate-spin h-6 w-6 text-emerald-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span className="text-xs font-semibold">Fetching ledger records...</span>
                    </div>
                  </td>
                </tr>
              )}
              {!isLoading && !data?.results?.length && (
                <tr>
                  <td colSpan={7} className="px-5 py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-2.5">
                      <span className="text-2xl">📋</span>
                      <p className="text-sm font-semibold">No records match filters.</p>
                      <p className="text-xs">Try adjusting your status, scope or source filters above.</p>
                    </div>
                  </td>
                </tr>
              )}
              {(data?.results || []).map((rec) => {
                const borderClass = rec.needs_review ? 'border-l-4 border-l-amber-500' : ''
                return (
                  <tr
                    key={rec.id}
                    className={`hover:bg-slate-50/40 transition-colors duration-200 group ${
                      rec.needs_review ? 'bg-amber-500/[0.02]' : ''
                    }`}
                  >
                    <td className={`px-5 py-4 whitespace-nowrap ${borderClass}`}>
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] px-2 py-0.5 rounded-md font-bold uppercase tracking-wider ${SOURCE_BADGE[rec.source_type] || 'bg-slate-100 text-slate-500'}`}>
                          {rec.source_type.replace('_', ' ')}
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-md font-bold uppercase tracking-wider ${SCOPE_BADGE[rec.scope] || 'bg-slate-100 text-slate-500'}`}>
                          {SCOPE_LABEL[rec.scope]}
                        </span>
                        {rec.needs_review && (
                          <span className="cursor-help text-xs text-amber-500" title={rec.needs_review_reason}>
                            ⚠️
                          </span>
                        )}
                        {rec.is_locked && (
                          <span className="cursor-help text-[11px]" title="Locked for audit">
                            🔒
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-4 max-w-xs">
                      <p className="text-xs font-bold text-slate-800 truncate">{rec.category}</p>
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">{rec.location}</p>
                      {rec.review_note && (
                        <p className="text-[10px] text-indigo-600 bg-indigo-50 border border-indigo-100/50 px-2 py-0.5 rounded-md mt-1 font-semibold inline-block truncate max-w-full">
                          💬 {rec.review_note}
                        </p>
                      )}
                    </td>
                    <td className="hidden md:table-cell px-5 py-4 text-right font-mono text-xs text-slate-700 font-semibold whitespace-nowrap">
                      {rec.activity_quantity.toLocaleString()} <span className="text-[10px] text-slate-400 font-medium font-sans">{rec.activity_unit}</span>
                    </td>
                    <td className="px-5 py-4 text-right font-mono text-xs text-slate-900 font-bold whitespace-nowrap">
                      {rec.co2e_tonnes != null ? rec.co2e_tonnes.toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 }) : '—'}
                    </td>
                    <td className="hidden sm:table-cell px-5 py-4 whitespace-nowrap">
                      <p className="text-xs text-slate-600 font-semibold">{rec.period_start}</p>
                      {rec.period_end !== rec.period_start && (
                        <p className="text-[10px] text-slate-400 mt-0.5">→ {rec.period_end}</p>
                      )}
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <span className={`text-[10px] px-2.5 py-1 rounded-full font-bold uppercase tracking-wider ${STATUS_BADGE[rec.status] || 'bg-slate-100 text-slate-500'}`}>
                        {rec.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <div className="flex items-center justify-center gap-1.5">
                        {!rec.is_locked && rec.status !== 'APPROVED' && (
                          <>
                            <button
                              id={`edit-${rec.id}`}
                              onClick={() => handleEditOpen(rec)}
                              className="flex items-center gap-1 text-[11px] font-bold text-indigo-600 bg-indigo-500/5 hover:bg-indigo-500 hover:text-white border border-indigo-500/10 hover:border-indigo-600 px-2.5 py-1.5 rounded-lg transition-all duration-200 cursor-pointer"
                              title="Edit Record"
                            >
                              ✎ Edit
                            </button>
                            <button
                              id={`approve-${rec.id}`}
                              onClick={() => approve.mutate(rec.id)}
                              className="flex items-center gap-1 text-[11px] font-bold text-emerald-600 bg-emerald-500/5 hover:bg-emerald-500 hover:text-white border border-emerald-500/10 hover:border-emerald-600 px-2.5 py-1.5 rounded-lg transition-all duration-200 cursor-pointer"
                              title="Approve Record"
                            >
                              ✓ Approve
                            </button>
                            <button
                              id={`flag-${rec.id}`}
                              onClick={() => setFlaggingRecordId(rec.id)}
                              className="flex items-center gap-1 text-[11px] font-bold text-amber-600 bg-amber-500/5 hover:bg-amber-500 hover:text-white border border-amber-500/10 hover:border-amber-600 px-2.5 py-1.5 rounded-lg transition-all duration-200 cursor-pointer"
                              title="Flag Record"
                            >
                              ⚑ Flag
                            </button>
                            <button
                              id={`reject-${rec.id}`}
                              onClick={() => reject.mutate(rec.id)}
                              className="flex items-center justify-center text-[11px] font-bold text-rose-600 bg-rose-500/5 hover:bg-rose-500 hover:text-white border border-rose-500/10 hover:border-rose-600 w-8 h-8 rounded-lg transition-all duration-200 cursor-pointer"
                              title="Reject Record"
                            >
                              ✗
                            </button>
                          </>
                        )}
                        {rec.status === 'APPROVED' && (
                          <div className="flex items-center gap-1 text-slate-400 text-xs font-semibold">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                            Verified
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination Toolbar */}
        {data && data.count > 50 && (
          <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
            <p className="text-xs font-semibold text-slate-500">
              Showing <span className="text-slate-800">{(page - 1) * 50 + 1}</span>–<span className="text-slate-800">{Math.min(page * 50, data.count)}</span> of <span className="text-slate-800">{data.count}</span> records
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="text-xs font-bold px-3.5 py-2 border border-slate-200 rounded-xl hover:bg-white bg-slate-50 disabled:opacity-40 disabled:pointer-events-none cursor-pointer transition-colors"
              >
                ← Prev
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page * 50 >= data.count}
                className="text-xs font-bold px-3.5 py-2 border border-slate-200 rounded-xl hover:bg-white bg-slate-50 disabled:opacity-40 disabled:pointer-events-none cursor-pointer transition-colors"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Flag dialog modal */}
      {flaggingRecordId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm"
            onClick={() => setFlaggingRecordId(null)}
          />
          {/* Modal Card */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-2xl w-full max-w-md p-6 relative z-10 animate-scale-up">
            <h3 className="text-base font-extrabold text-slate-950 tracking-tight">Flag Record for Review</h3>
            <p className="text-xs text-slate-400 mt-1">Specify an anomaly description or action item for this emissions row.</p>

            <div className="mt-4">
              <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Custom Annotation Note</label>
              <textarea
                className="w-full bg-slate-50 border border-slate-200 focus:bg-white focus:border-emerald-500 rounded-xl p-3 text-xs focus:outline-none focus:ring-4 focus:ring-emerald-500/10 min-h-[90px] font-medium"
                placeholder="e.g. Activity factor is 12% higher than seasonal expectations."
                value={flagNote}
                onChange={(e) => setFlagNote(e.target.value)}
              />
            </div>

            <div className="mt-5 flex items-center justify-end gap-2.5">
              <button
                onClick={() => setFlaggingRecordId(null)}
                className="text-xs font-semibold text-slate-500 hover:text-slate-700 bg-slate-50 border border-slate-200 px-4 py-2.5 rounded-xl cursor-pointer transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => flag.mutate({ id: flaggingRecordId, note: flagNote || 'Needs review' })}
                disabled={flag.isPending}
                className="text-xs font-semibold text-white bg-amber-500 hover:bg-amber-600 px-4 py-2.5 rounded-xl cursor-pointer transition-colors disabled:opacity-50"
              >
                {flag.isPending ? 'Flagging...' : 'Flag Record'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit dialog modal */}
      {editingRecord !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm"
            onClick={() => setEditingRecord(null)}
          />
          {/* Modal Card */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-2xl w-full max-w-md p-6 relative z-10 animate-scale-up">
            <h3 className="text-base font-extrabold text-slate-950 tracking-tight">Edit Emission Activity Record</h3>
            <p className="text-xs text-slate-400 mt-1">
              Correct quantities, change activity units, and annotate notes. Calculations will be re-run instantly.
            </p>

            {editError && (
              <div className="mt-3 text-xs text-rose-600 bg-rose-50 border border-rose-100 p-3 rounded-xl font-medium">
                ⚠️ {editError}
              </div>
            )}

            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                  Activity Quantity
                </label>
                <input
                  type="text"
                  className="w-full bg-slate-50 border border-slate-200 focus:bg-white focus:border-emerald-500 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:ring-4 focus:ring-emerald-500/10 font-mono font-semibold"
                  value={editQuantity}
                  onChange={(e) => setEditQuantity(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                  Activity Unit
                </label>
                <select
                  className="w-full bg-slate-50 border border-slate-200 focus:bg-white focus:border-emerald-500 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:ring-4 focus:ring-emerald-500/10 font-semibold"
                  value={editUnit}
                  onChange={(e) => setEditUnit(e.target.value)}
                >
                  {getUnitOptions(editingRecord.source_type, editingRecord.category).map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                  Analyst Review Note
                </label>
                <textarea
                  className="w-full bg-slate-50 border border-slate-200 focus:bg-white focus:border-emerald-500 rounded-xl p-3 text-xs focus:outline-none focus:ring-4 focus:ring-emerald-500/10 min-h-[80px] font-medium"
                  placeholder="e.g. Corrected the utility invoice input value."
                  value={editNote}
                  onChange={(e) => setEditNote(e.target.value)}
                />
              </div>
            </div>

            <div className="mt-5 flex items-center justify-end gap-2.5">
              <button
                onClick={() => setEditingRecord(null)}
                className="text-xs font-semibold text-slate-500 hover:text-slate-700 bg-slate-50 border border-slate-200 px-4 py-2.5 rounded-xl cursor-pointer transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  editRecord.mutate({
                    id: editingRecord.id,
                    payload: {
                      activity_quantity: parseFloat(editQuantity),
                      activity_unit: editUnit,
                      review_note: editNote,
                    },
                  })
                }
                disabled={editRecord.isPending || !editQuantity || isNaN(Number(editQuantity))}
                className="text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2.5 rounded-xl cursor-pointer transition-colors disabled:opacity-50"
              >
                {editRecord.isPending ? 'Saving...' : 'Save & Re-calculate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
