import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: 'src/api/openapi.json',
  output: 'src/api/generated',
  plugins: ['@hey-api/client-fetch'],
});
