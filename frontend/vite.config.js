import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  // Port 3000 matches the backend's default CORS_ORIGINS
  server: { port: 3000 },
  preview: { port: 3000 },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        // Long-lived vendor chunks; pages are lazy-loaded in App.jsx
        manualChunks: {
          react: ['react', 'react-dom', 'react-dom/client', 'react-router-dom'],
          firebase: ['firebase/app', 'firebase/auth'],
        },
      },
    },
  },
});
