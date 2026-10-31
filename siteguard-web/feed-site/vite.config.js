import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: { dedupe: ['react', 'react-dom', 'react-router-dom'] },
  server: { port: 3003, strictPort: true, host: 'localhost', fs: { allow: ['..'] } },
});
