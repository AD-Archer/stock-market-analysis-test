import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Check if we're running in Docker or locally
const backendUrl = process.env.VITE_DOCKER_ENV === 'true'
  ? 'http://backend:8000'  // use service name in Docker
  : 'http://localhost:8000' // use localhost for local dev

console.log('Using backend URL:', backendUrl)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        rewrite: (path) => path
      }
    },
    cors: {
      // Allow requests from these domains
      origin: ['https://stocks.adarcher.app', 'https://stocks.archer.software', 'http://localhost:5173']
    },
    allowedHosts: ['stocks.archer.software', 'stocks.adarcher.app', 'localhost']
  },
  define: {
    'process.env': process.env
  }
})
