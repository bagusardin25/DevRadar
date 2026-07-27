import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  root: resolve(__dirname, 'src/sidepanel'),
  base: './',
  build: {
    outDir: resolve(__dirname, 'dist/sidepanel'),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, 'src/sidepanel/index.html'),
    },
  },
});
