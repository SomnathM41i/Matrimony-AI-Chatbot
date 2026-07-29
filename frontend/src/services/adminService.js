import api from './apiClient'

export const getAdminStats = () => api.get('/admin/stats').then(r => r.data)

export const getUsers = (page = 1, search = '', perPage = 20) =>
  api.get('/admin/users', { params: { page, search, per_page: perPage } }).then(r => r.data)

export const updateUser = (id, body) =>
  api.patch(`/admin/users/${id}`, body).then(r => r.data)

export const deleteUser = (id) =>
  api.delete(`/admin/users/${id}`).then(r => r.data)

export const getProfiles = (page = 1, filters = {}, perPage = 20) =>
  api.get('/admin/profiles', { params: { page, per_page: perPage, ...filters } }).then(r => r.data)

export const getProfile = (matriId) =>
  api.get(`/admin/profiles/${matriId}`).then(r => r.data)

export const updateProfileStatus = (matriId, status) =>
  api.patch(`/admin/profiles/${matriId}/status`, { status }).then(r => r.data)

export const getConversations = (page = 1, search = '', perPage = 20) =>
  api.get('/admin/conversations', { params: { page, search, per_page: perPage } }).then(r => r.data)

export const getConversationDetail = (id) =>
  api.get(`/admin/conversations/${id}`).then(r => r.data)

export const getAdminHealth = () => api.get('/admin/health').then(r => r.data)
