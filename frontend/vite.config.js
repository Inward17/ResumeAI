import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // GitHub Pages serves the app from /<repo>/; CI sets VITE_BASE_PATH
  base: process.env.VITE_BASE_PATH || '/',
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
        // Vite 8 (Rolldown) takes only the function form
        manualChunks(id) {
          if (/node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) return 'react';
          if (/node_modules[\\/](firebase|@firebase)[\\/]/.test(id)) return 'firebase';
          return undefined;
        },
      },
    },
  },
});
