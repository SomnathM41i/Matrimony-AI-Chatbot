import api from './apiClient'

export const getPlans = () => api.get('/commercial/plans').then((r) => r.data)
export const getSubscription = () => api.get('/commercial/me').then((r) => r.data)
export const getUsage = () => api.get('/commercial/usage').then((r) => r.data)
export const createPlanOrder = (planId) => api.post('/commercial/orders', { plan_id: planId }).then((r) => r.data)
export const getMyOrders = () => api.get('/commercial/orders').then((r) => r.data)
