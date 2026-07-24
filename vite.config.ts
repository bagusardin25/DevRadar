import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      // Dev: browser calls /api/* and /health/* on Vite; proxied to FastAPI.
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000';
            console.warn(`[vite proxy] Backend server unreachable at ${target}: ${err.message}`);
            if ('writeHead' in res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({
                error: 'Backend proxy error',
                message: `Could not connect to backend server at ${target}. Make sure backend is running.`,
              }));
            }
          });
        },
      },
      '/health': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000';
            console.warn(`[vite proxy] Backend server unreachable at ${target}: ${err.message}`);
            if ('writeHead' in res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({
                error: 'Backend proxy error',
                message: `Could not connect to backend server at ${target}.`,
              }));
            }
          });
        },
      },
    },
  },
});
