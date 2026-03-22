import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const TAURI_DEV_HOST = process.env.TAURI_DEV_HOST;

export default defineConfig({
  // Tauri: prevent Vite from obscuring Rust compile errors
  clearScreen: false,
  plugins: [react()],
  server: {
    port: 4201,
    strictPort: true,
    host: TAURI_DEV_HOST ?? 'localhost',
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
        timeout: 5000,
        proxyTimeout: 5000,
      },
      '/ws': {
        target: 'http://localhost:3001',
        ws: true,
        timeout: 30000,
        proxyTimeout: 5000,
      },
    },
  },
  resolve: {
    alias: {
      '@agent-chatroom/shared': new URL('../../packages/shared/src/index.ts', import.meta.url).pathname,
    },
  },
});
