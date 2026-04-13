import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Use environment variables passed during build, then read variables from .env, finally fallback to /platform/
  const base = process.env.VITE_BASE || env.VITE_BASE || '/platform/'

  return {
    plugins: [react()],
    base,
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      host: '0.0.0.0', // Allow access from any IP
      port: parseInt(env.VITE_DEV_PORT || '3000'),
      proxy: {
        // API proxy to backend service
        '/api': {
          target: env.VITE_API_TARGET || 'http://localhost:5000',
          changeOrigin: true,
          secure: false
        },
        // Guardrails detection proxy to backend service
        '/v1': {
          target: env.VITE_DETECTION_TARGET || 'http://localhost:5001',
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})