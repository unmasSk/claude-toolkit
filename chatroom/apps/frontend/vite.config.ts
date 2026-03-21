import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 4201,
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
