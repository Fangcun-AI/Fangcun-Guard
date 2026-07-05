import axios from 'axios'

export interface LoginRequest { email: string; password: string; language?: string }
export interface RegisterRequest { email: string; password: string; language?: string }
export interface VerifyEmailRequest { email: string; verification_code: string }
export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  api_key?: string
  tenant_id?: string
  is_super_admin?: boolean
  requires_password_change?: boolean
  password_message?: string
}
export interface UserInfo {
  id: string
  email: string
  api_key: string
  model_api_key?: string
  is_active: boolean
  is_verified: boolean
  is_super_admin: boolean
  rate_limit: number
  language: string
  log_direct_model_access: boolean
}

class AuthService {
  private readonly baseURL = import.meta.env.VITE_API_URL || ''
  private readonly storageKey = 'auth_token'

  private authHeaders() {
    const token = this.getToken()
    if (!token) throw new Error('No authentication token found')
    return { Authorization: `Bearer ${token}` }
  }

  async login(data: LoginRequest): Promise<LoginResponse> {
    return (await axios.post(`${this.baseURL}/api/v1/users/login`, data)).data
  }
  async register(data: RegisterRequest): Promise<{ message: string }> {
    return (await axios.post(`${this.baseURL}/api/v1/users/register`, data)).data
  }
  async verifyEmail(data: VerifyEmailRequest): Promise<{ message: string }> {
    return (await axios.post(`${this.baseURL}/api/v1/users/verify-email`, data)).data
  }
  async getCurrentUser(): Promise<UserInfo> {
    return (await axios.get(`${this.baseURL}/api/v1/users/me`, { headers: this.authHeaders() })).data
  }
  async regenerateModelApiKey(): Promise<{ model_api_key: string }> {
    return (await axios.post(`${this.baseURL}/api/v1/users/regenerate-model-api-key`, {}, { headers: this.authHeaders() })).data
  }
  async regenerateApiKey(): Promise<{ api_key: string }> {
    return (await axios.post(`${this.baseURL}/api/v1/users/regenerate-api-key`, {}, { headers: this.authHeaders() })).data
  }
  async updateLanguage(language: string): Promise<{ status: string; message: string; language: string }> {
    return (await axios.put(`${this.baseURL}/api/v1/users/language`, { language }, { headers: this.authHeaders() })).data
  }
  async changePassword(currentPassword: string, newPassword: string): Promise<{ status: string; message: string }> {
    const payload = { current_password: currentPassword, new_password: newPassword }
    return (await axios.post(`${this.baseURL}/api/v1/users/change-password`, payload, { headers: this.authHeaders() })).data
  }
  async updateLogDirectModelAccess(logDMA: boolean): Promise<{ status: string; message: string; log_direct_model_access: boolean }> {
    const payload = { log_direct_model_access: logDMA }
    return (await axios.put(`${this.baseURL}/api/v1/users/log-direct-model-access`, payload, { headers: this.authHeaders() })).data
  }
  async logout(): Promise<void> {
    const token = this.getToken()
    try {
      if (token) await axios.post(`${this.baseURL}/api/v1/auth/logout`, {}, { headers: this.authHeaders() })
    } catch (error) {
      console.error('Logout API call failed:', error)
    } finally {
      this.clearToken()
    }
  }
  setToken(token: string) { localStorage.setItem(this.storageKey, token) }
  getToken() { return localStorage.getItem(this.storageKey) }
  clearToken() { localStorage.removeItem(this.storageKey) }
  isAuthenticated() {
    const token = this.getToken()
    if (!token) return false
    try {
      return JSON.parse(atob(token.split('.')[1])).exp > Date.now() / 1000
    } catch {
      return false
    }
  }
}

export const authService = new AuthService()
