import axios from 'axios'

const healthApi = axios.create({
  baseURL: '',
  timeout: 10000,
})

export const getHealth = async () => {
  const { data } = await healthApi.get('/health')
  return data
}
