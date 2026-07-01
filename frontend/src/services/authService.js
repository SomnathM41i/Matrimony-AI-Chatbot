import api from './apiClient'

export const login = async (email, password) => {
  const { data } = await api.post('/auth/login', { email, password })
  return data
}

export const register = async (name, email, password) => {
  const { data } = await api.post('/auth/register', { name, email, password })
  return data
}

export const getMe = async () => {
  const { data } = await api.get('/auth/me')
  return data
}

export const refreshToken = async (refresh_token) => {
  const { data } = await api.post('/auth/refresh', { refresh_token })
  return data
}
