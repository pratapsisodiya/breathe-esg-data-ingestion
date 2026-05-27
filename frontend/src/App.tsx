import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { getUser } from './api/client'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Ingest from './pages/Ingest'
import Review from './pages/Review'
import AuditLog from './pages/AuditLog'

function RequireAuth({ children }: { children: React.ReactNode }) {
  return getUser() ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="ingest" element={<Ingest />} />
          <Route path="review" element={<Review />} />
          <Route path="audit" element={<AuditLog />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
