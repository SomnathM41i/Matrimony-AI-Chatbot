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

export const getCommercialSummary = () => api.get('/admin/commercial/summary').then(r => r.data)
export const getCommercialPlans = () => api.get('/admin/commercial/plans').then(r => r.data)
export const createCommercialPlan = (body) => api.post('/admin/commercial/plans', body).then(r => r.data)
export const getAIProviders = () => api.get('/admin/commercial/providers').then(r => r.data)
export const createAIProvider = (body) => api.post('/admin/commercial/providers', body).then(r => r.data)
export const updateAIProvider = (id, body) => api.patch(`/admin/commercial/providers/${id}`, body).then(r => r.data)
export const getAIModels = () => api.get('/admin/commercial/models').then(r => r.data)
export const createAIModel = (body) => api.post('/admin/commercial/models', body).then(r => r.data)
export const updateAIModel = (id, body) => api.patch(`/admin/commercial/models/${id}`, body).then(r => r.data)
export const testAIModel = (id) => api.post(`/admin/commercial/models/${id}/test`).then(r => r.data)
export const getAIRoutes = () => api.get('/admin/commercial/routes').then(r => r.data)
export const publishAIRoute = (taskKey, modelIds) => api.put(`/admin/commercial/routes/${taskKey}`, { task_key: taskKey, model_ids: modelIds, enabled: true }).then(r => r.data)
export const testAIRoute = (taskKey) => api.post(`/admin/commercial/routes/${taskKey}/test`).then(r => r.data)
export const getSubscriptions = () => api.get('/admin/commercial/subscriptions').then(r => r.data)
export const assignSubscription = (userId, planId) => api.post(`/admin/commercial/users/${userId}/subscription`, { plan_id: planId }).then(r => r.data)
export const updateSubscription = (id, body) => api.patch(`/admin/commercial/subscriptions/${id}`, body).then(r => r.data)
export const getPaymentOrders = () => api.get('/admin/commercial/orders').then(r => r.data)
export const getPaymentGateways = () => api.get('/admin/commercial/gateways').then(r => r.data)
export const createPaymentGateway = (body) => api.post('/admin/commercial/gateways', body).then(r => r.data)
export const updatePaymentGateway = (id, body) => api.patch(`/admin/commercial/gateways/${id}`, body).then(r => r.data)
export const confirmPaymentOrder = (orderId, providerPaymentId) => api.post(`/admin/commercial/orders/${orderId}/confirm`, { provider_payment_id: providerPaymentId }).then(r => r.data)
export const getAIUsageEvents = () => api.get('/admin/commercial/usage').then(r => r.data)
export const getCommercialAudit = () => api.get('/admin/commercial/audit').then(r => r.data)
