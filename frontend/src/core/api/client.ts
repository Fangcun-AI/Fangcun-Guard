import axios from 'axios'
import { toast } from 'sonner'

const getBaseURL = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL
  }

  return ''
}

const api = axios.create({
  baseURL: getBaseURL(),
  timeout: 300000,
})

api.interceptors.request.use(
  (config) => {
    if (config.url && config.url.includes('/auth/')) {
      return config
    }

    const authToken = localStorage.getItem('auth_token')
    const apiToken = localStorage.getItem('api_token')
    const token = authToken || apiToken

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    const switchToken = localStorage.getItem('switch_session_token')
    if (switchToken) {
      config.headers['X-Switch-Session'] = switchToken
    }

    const isProxyManagementRequest = config.url && config.url.includes('/proxy/upstream-apis')
    const applicationId = localStorage.getItem('current_application_id')
    if (applicationId && !isProxyManagementRequest) {
      config.headers['X-Application-ID'] = applicationId
    }

    return config
  },
  (error) => Promise.reject(error),
)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url: string | undefined = error.config?.url

    if (status === 401 && url && url.includes('/admin/current-switch')) {
      return Promise.reject(error)
    }

    if (status === 429) {
      return Promise.reject(error)
    }

    if (status === 403 && url && url.includes('/custom-scanners')) {
      return Promise.reject(error)
    }

    let errorMessage = 'Request failed'
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      errorMessage = detail
    } else if (Array.isArray(detail) && detail.length > 0) {
      errorMessage = detail.map((item: any) => item.msg || JSON.stringify(item)).join('; ')
    } else if (error.message) {
      errorMessage = error.message
    }

    toast.error(errorMessage)
    return Promise.reject(error)
  },
)

export const responseBody = <T>(request: Promise<{ data: T }>): Promise<T> =>
  request.then(({ data }) => data)

export default api
