import React from 'react'

import {
  ForgotPasswordScreen,
  LoginScreen,
  RegisterScreen,
  ResetPasswordScreen,
  VerifyEmailScreen,
} from './screens'

export interface AuthRouteEntry {
  path: string
  element: React.ReactElement
}

export const authRouteCatalog: AuthRouteEntry[] = [
  { path: '/login', element: <LoginScreen /> },
  { path: '/register', element: <RegisterScreen /> },
  { path: '/verify', element: <VerifyEmailScreen /> },
  { path: '/forgot-password', element: <ForgotPasswordScreen /> },
  { path: '/reset-password', element: <ResetPasswordScreen /> },
]
