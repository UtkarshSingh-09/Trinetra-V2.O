import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  define: {
    global: 'globalThis',
  },
  server: {
    port: 5173,
    strictPort: true, // Forces Vite to use 5173. Will error if another instance is running!
    open: true,
    proxy: {
      '/api': {
        target: 'http://10.1.184.239:8000',
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: 'http://10.1.184.239:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
