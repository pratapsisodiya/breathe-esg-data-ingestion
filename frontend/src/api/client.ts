import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://breatheesg-backend-c64a.onrender.com'

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Inject auth token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) config.headers.Authorization = `Token ${token}`
  return config
})

// Redirect to login on 401
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export async function login(email: string, password: string) {
  const res = await api.post('/api/auth/login/', { username: email, password })
  localStorage.setItem('auth_token', res.data.token)
  localStorage.setItem('user', JSON.stringify(res.data.user))
  return res.data
}

export function logout() {
  api.post('/api/auth/logout/').catch(() => {})
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user')
  window.location.href = '/login'
}

export function getUser() {
  const u = localStorage.getItem('user')
  return u ? JSON.parse(u) : null
}
