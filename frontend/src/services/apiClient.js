import axios from 'axios'
import { navigateTo } from './navigate'
import { useAuthStore } from '../app/store'

const baseURL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

let refreshRequest = null

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const originalRequest = err.config
    const isAuthRequest = originalRequest?.url?.includes('/auth/login')
      || originalRequest?.url?.includes('/auth/register')
      || originalRequest?.url?.includes('/auth/refresh')

    if (err.response?.status === 401 && originalRequest && !originalRequest._retried && !isAuthRequest) {
      originalRequest._retried = true
      try {
        if (!refreshRequest) {
          refreshRequest = axios.post(`${baseURL}/auth/refresh`, null, {
            withCredentials: true,
            headers: { 'Content-Type': 'application/json' },
          }).finally(() => {
            refreshRequest = null
          })
        }
        await refreshRequest
        return api(originalRequest)
      } catch {
        useAuthStore.getState().logout()
        navigateTo('/login')
      }
    } else if (err.response?.status === 401 && !isAuthRequest) {
      useAuthStore.getState().logout()
      navigateTo('/login')
    }
    return Promise.reject(err)
  }
)

export default api
