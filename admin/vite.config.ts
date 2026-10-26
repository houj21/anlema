import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    port: 5180,
    host: '127.0.0.1',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8899', changeOrigin: true },
    },
  },
})
