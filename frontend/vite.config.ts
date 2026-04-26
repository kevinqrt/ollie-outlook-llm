import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import mkcert from 'vite-plugin-mkcert';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), mkcert()],
  envDir: resolve(__dirname, '..'),
  server: {
    host: '127.0.0.1',
    port: 3000,
    // biome-ignore lint/suspicious/noExplicitAny: Vite 6+ has stricter https types that conflict with mkcert's true value
    https: true as any,
  },
  build: {
    rollupOptions: {
      input: {
        taskpane: resolve(__dirname, 'index.html'),
        commands: resolve(__dirname, 'commands.html'),
      },
    },
  },
});
