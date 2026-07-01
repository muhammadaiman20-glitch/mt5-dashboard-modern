import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/mt5-dashboard-modern/',
  plugins: [react()],
})
