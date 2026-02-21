import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],
    server: {
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true
            },
            '/system': {
                target: 'http://localhost:8000',
                changeOrigin: true
            },
            '/health': {
                target: 'http://localhost:8000',
                changeOrigin: true
            },
            '/ping': {
                target: 'http://localhost:8000',
                changeOrigin: true
            }
        }
    }
})
