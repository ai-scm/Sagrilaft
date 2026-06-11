import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // @shared apunta a frontend/shared/ (dos niveles arriba desde apps/portal-interno/)
      '@shared': path.resolve(__dirname, '../../shared'),
    },
  },
  server: {
    port: 5174,
    fs: {
      allow: ['../..'],
    },
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
