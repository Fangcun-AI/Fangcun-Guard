import { z } from 'zod'

// Email field
const emailField = z
  .string()
  .min(1, 'Email is required')
  .email('Invalid email address')

// Password field: min 8 chars, contains uppercase, lowercase, and number
const passwordField = z
  .string()
  .min(8, 'Password must be at least 8 characters')
  .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
  .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
  .regex(/[0-9]/, 'Password must contain at least one number')

// ----- Login -----
export const loginSchema = z.object({
  email: emailField,
  password: z.string().min(1, 'Password is required'),
})
export type LoginFormData = z.infer<typeof loginSchema>

// ----- Register -----
export const registerSchema = z
  .object({
    email: emailField,
    password: passwordField,
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })
export type RegisterFormData = z.infer<typeof registerSchema>

// ----- Verification code (6 digits) -----
export const verificationCodeSchema = z.object({
  verificationCode: z
    .string()
    .min(6, 'Verification code must be 6 digits')
    .max(6, 'Verification code must be 6 digits')
    .regex(/^\d{6}$/, 'Verification code must be 6 digits'),
})
export type VerificationCodeFormData = z.infer<typeof verificationCodeSchema>

// ----- Email verification (email + code) -----
export const emailVerificationSchema = z.object({
  email: emailField,
  verificationCode: z
    .string()
    .min(6, 'Verification code must be 6 digits')
    .max(6, 'Verification code must be 6 digits')
    .regex(/^\d{6}$/, 'Verification code must be 6 digits'),
})
export type EmailVerificationFormData = z.infer<typeof emailVerificationSchema>

// ----- Forgot password -----
export const forgotPasswordSchema = z.object({
  email: emailField,
})
export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>

// ----- Reset password -----
export const resetPasswordSchema = z
  .object({
    password: passwordField,
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })
export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>
