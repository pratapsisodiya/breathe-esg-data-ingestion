import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/client'

export default function Login() {
  const [email, setEmail] = useState('analyst@acme.com')
  const [password, setPassword] = useState('analyst123')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(email, password)
      navigate('/')
    } catch {
      setError('Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-tr from-slate-50 via-emerald-50/20 to-slate-100 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background blobs for premium depth */}
      <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] bg-emerald-200/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] bg-teal-200/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-[420px] relative z-10">
        {/* Logo Section */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 shadow-inner mb-3">
            <span className="text-2xl">🌿</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">BreatheESG</h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium">Enterprise Emissions Data Platform</p>
        </div>

        {/* Login Card */}
        <div className="bg-white/80 backdrop-blur-md rounded-2xl border border-slate-100 shadow-xl shadow-slate-200/50 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-[12px] font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400">
                  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.206" />
                  </svg>
                </span>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-white border border-slate-200 focus:border-emerald-500 rounded-xl pl-11 pr-4 py-2.5 text-sm font-medium focus:outline-none focus:ring-4 focus:ring-emerald-500/10 transition-all duration-200"
                  placeholder="name@company.com"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-[12px] font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400">
                  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </span>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-white border border-slate-200 focus:border-emerald-500 rounded-xl pl-11 pr-4 py-2.5 text-sm font-medium focus:outline-none focus:ring-4 focus:ring-emerald-500/10 transition-all duration-200"
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-600 bg-red-50/50 border border-red-100 rounded-xl p-3 text-xs font-semibold">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                {error}
              </div>
            )}

            <button
              id="login-submit"
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 text-white py-2.5 rounded-xl text-sm font-semibold shadow-lg shadow-emerald-600/10 hover:shadow-emerald-600/25 hover:from-emerald-700 hover:to-teal-700 focus:outline-none focus:ring-4 focus:ring-emerald-500/20 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-100 flex flex-col gap-1 items-center">
            <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Demo Credentials</span>
            <p className="text-xs text-slate-500 font-medium">
              <span className="font-mono text-slate-600 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">analyst@acme.com</span>
              <span className="text-slate-300 mx-1.5">|</span>
              <span className="font-mono text-slate-600 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">analyst123</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
