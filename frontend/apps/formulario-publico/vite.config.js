import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // @shared apunta a frontend/shared/ (dos niveles arriba desde apps/formulario-publico/)
      '@shared': path.resolve(__dirname, '../../shared'),
    },
  },
  server: {
    port: 5173,
    fs: {
      allow: ['../..'],
    },
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**']
  },
  build: {
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) {
            return 'vendor-react';
          }
          if (id.includes('node_modules/country-state-city') || id.includes('node_modules/i18n-iso-countries')) {
            return 'vendor-geodata';
          }
        }
      }
    }
  }
})
