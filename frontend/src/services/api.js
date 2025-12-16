import axios from 'axios'
import { getToken } from '../store/auth'

const api = axios.create({
  baseURL: 'http://localhost:5002'
})

api.interceptors.request.use(config => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = token
  }
  return config
})

export default api