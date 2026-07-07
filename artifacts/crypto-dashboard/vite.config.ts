import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, loadEnv } from 'vite';

function resolvePort(rawPort: string | undefined): number {
  if (!rawPort) return 5173;

  const port = Number(rawPort);
  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`Invalid PORT value: "${rawPort}"`);
  }
  return port;
}

function resolveBasePath(rawBasePath: string | undefined): string {
  const value = rawBasePath?.trim() || '/';
  if (value === '/') return '/';
  return `/${value.replace(/^\/+|\/+$/g, '')}/`;
}

const projectRoot = path.resolve(import.meta.dirname);

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, '');
  const port = resolvePort(env.PORT || process.env.PORT);
  const basePath = resolveBasePath(env.BASE_PATH || process.env.BASE_PATH);

  return {
    base: basePath,
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, 'src'),
        '@assets': path.resolve(
          import.meta.dirname,
          '..',
          '..',
          'attached_assets',
        ),
      },
      dedupe: ['react', 'react-dom'],
    },
    root: projectRoot,
    build: {
      outDir: path.resolve(import.meta.dirname, 'dist/public'),
      emptyOutDir: true,
    },
    server: {
      port,
      strictPort: true,
      host: '0.0.0.0',
      allowedHosts: true,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
      fs: {
        strict: true,
      },
    },
    preview: {
      port,
      host: '0.0.0.0',
      allowedHosts: true,
    },
  };
});
