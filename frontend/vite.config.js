import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const target = process.env.API_PROXY || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': target } },
  preview: { port: 4173, proxy: { '/api': target } },
})
