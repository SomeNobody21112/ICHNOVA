import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The local analysis server (python server/app.py) runs the blind receiver on uploads.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8765' },
  },
  build: { chunkSizeWarningLimit: 900 },
})
