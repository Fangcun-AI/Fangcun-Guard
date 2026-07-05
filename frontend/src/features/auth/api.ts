import api, { responseBody as body } from '@/core/api/client'
import { authService } from '@/services/auth'

type AuthMessage = { message: string }

export const authFeatureApi = {
  register: (email: string, password: string, language: string): Promise<AuthMessage> =>
    authService.register({ email, password, language }),
  verifyEmail: (email: string, verificationCode: string): Promise<AuthMessage> =>
    authService.verifyEmail({ email, verification_code: verificationCode }),
  resendVerificationCode: (email: string, language: string): Promise<AuthMessage> =>
    body(api.post('/api/v1/users/resend-verification-code', { email, language })),
  requestPasswordReset: (email: string, language: string): Promise<AuthMessage> =>
    body(api.post('/api/v1/auth/forgot-password', { email, language })),
  verifyResetToken: (token: string): Promise<AuthMessage> =>
    body(api.post('/api/v1/auth/verify-reset-token', null, { params: { token } })),
  resetPassword: (token: string, newPassword: string): Promise<AuthMessage> =>
    body(api.post('/api/v1/auth/reset-password', { token, new_password: newPassword })),
}
