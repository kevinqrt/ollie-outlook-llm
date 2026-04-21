import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import mkcert from 'vite-plugin-mkcert';

const __dirname = dirname(fileURLToPath(import.meta.url));

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), mkcert()],
  // Robust absolute path to the root directory
  envDir: resolve(__dirname, '..'),
  server: {
    host: 'localhost',
    port: 3000,
    https: true,
  },
});
