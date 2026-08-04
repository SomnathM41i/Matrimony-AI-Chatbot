import api from './apiClient'

export const updateProfile = async (payload) => {
  const { data } = await api.patch('/profile', payload)
  return data
}

export const linkMatriId = async (matriId) => {
  const { data } = await api.post('/profile/matri/link', { matri_id: matriId })
  return data
}

export const getPreferences = async () => {
  const { data } = await api.get('/profile/preference')
  return data
}

export const startPreferenceFlow = async () => {
  const { data } = await api.post('/profile/preference/start')
  return data
}

export const nextPreferenceQuestion = async (answers) => {
  const { data } = await api.post('/profile/preference/next', { answers })
  return data
}

export const savePreferences = async (filters) => {
  const { data } = await api.post('/profile/preference/save', { filters })
  return data
}

export const clearPreferences = async () => {
  const { data } = await api.delete('/profile/preference')
  return data
}
