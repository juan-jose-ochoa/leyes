import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
  site: 'https://leyesmx.com',
  output: 'static',
  trailingSlash: 'always',
  integrations: [
    react(),
    tailwind(),
  ],
  build: {
    assets: 'assets'
  },
  vite: {
    ssr: {
      noExternal: ['clsx', 'lucide-react']
    }
  }
});
