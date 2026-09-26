import react from '@vitejs/plugin-react';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';
import { defineConfig } from 'vite';
import mkcert from 'vite-plugin-mkcert';

const __dirname = dirname(fileURLToPath(import.meta.url));

// https://vitejs.dev/config/
export default defineConfig({
  // Im Docker-Container servieren wir von Root
  base: '/',
  plugins: [react(), mkcert()],
  envDir: resolve(__dirname, '..'),
  server: {
    host: '127.0.0.1',
    port: 3000,
    https: true as any,
    proxy: {
      // Die Task-Pane läuft zwingend über HTTPS (Office-Add-in-Vorgabe), das
      // Backend lokal nur über HTTP - ein direkter Browser-Fetch auf die
      // HTTP-URL würde als Mixed Content geblockt (TypeError: Failed to
      // fetch, ohne weitere Erklärung). Dieser Proxy läuft serverseitig in
      // Vite, nicht im Browser, und ist davon nicht betroffen.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        taskpane: resolve(__dirname, 'index.html'),
        commands: resolve(__dirname, 'commands.html'),
        authStart: resolve(__dirname, 'auth-start.html'),
        authCallback: resolve(__dirname, 'auth-callback.html'),
      },
    },
  },
});
