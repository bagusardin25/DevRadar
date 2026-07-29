import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  // Pin every React entrypoint into a single optimize pass. Left to discover
  // them on its own, the dep optimizer emitted two CommonJS React modules —
  // `react.js` (used by react-dom + the JSX runtime) and a second chunk (used
  // by react-dom/client + lucide-react). Two modules means two dispatchers, so
  // createRoot installed hooks on one instance while components read them from
  // the other: every render died with "Invalid hook call".
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-dom/client',
      'react/jsx-runtime',
      'react/jsx-dev-runtime',
    ],
  },
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
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
