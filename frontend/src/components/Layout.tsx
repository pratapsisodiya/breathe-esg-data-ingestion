import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { getUser, logout } from '../api/client'

const nav = [
  {
    to: '/',
    label: 'Dashboard',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    to: '/ingest',
    label: 'Ingest Data',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
      </svg>
    ),
  },
  {
    to: '/review',
    label: 'Review Records',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    to: '/audit',
    label: 'Audit Log',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
      </svg>
    ),
  },
]

export default function Layout() {
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const user = getUser()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex flex-col md:flex-row h-screen overflow-hidden bg-slate-50/50">
      {/* Mobile Drawer Backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-30 md:hidden transition-opacity duration-300"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar / Mobile Drawer */}
      <aside className={`fixed inset-y-0 left-0 w-64 bg-slate-950 text-slate-100 flex flex-col flex-shrink-0 border-r border-slate-900 shadow-xl z-40 transform transition-transform duration-300 ease-in-out md:relative md:translate-x-0 ${
        isMobileOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        {/* Logo Section */}
        <div className="px-6 py-6 border-b border-slate-900 flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                <span className="text-emerald-400 text-lg">🌿</span>
              </div>
              <span className="font-bold text-base text-white tracking-tight">BreatheESG</span>
            </div>
            {/* Close button for mobile */}
            <button
              onClick={() => setIsMobileOpen(false)}
              className="w-8 h-8 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-400 hover:text-white md:hidden cursor-pointer"
              aria-label="Close menu"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-soft"></span>
            <p className="text-slate-400 text-[11px] font-medium tracking-wide uppercase truncate w-44">{user?.tenant}</p>
          </div>
        </div>

        {/* Navigation Section */}
        <nav className="flex-1 px-4 py-6 space-y-1.5">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setIsMobileOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl text-[13px] font-semibold tracking-wide transition-all duration-200 ${
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-400 border-l-2 border-emerald-400'
                    : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
                }`
              }
            >
              <span className="transition-transform duration-200 group-hover:scale-110">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User Info Section */}
        <div className="p-4 border-t border-slate-900 bg-slate-950/50 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center font-bold text-xs text-slate-300 uppercase">
              {user?.email?.charAt(0) || 'A'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-200 truncate">{user?.email}</p>
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider mt-0.5">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 border border-slate-800 hover:border-red-950/30 hover:bg-red-950/20 text-slate-400 hover:text-red-400 text-xs font-medium rounded-xl transition-all duration-200 cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 01-3-3h4a3 3 0 013 3v1" />
            </svg>
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile Top Header + Content Wrapper */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header Bar for Mobile only */}
        <header className="h-16 bg-slate-950 text-slate-100 border-b border-slate-900 px-5 flex items-center justify-between md:hidden flex-shrink-0 z-20 shadow-md">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <span className="text-emerald-400 text-lg">🌿</span>
            </div>
            <span className="font-bold text-sm text-white tracking-tight">BreatheESG</span>
          </div>
          <button
            onClick={() => setIsMobileOpen(true)}
            className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-300 hover:text-white transition-colors cursor-pointer"
            aria-label="Toggle menu"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 overflow-auto bg-slate-50/50">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
