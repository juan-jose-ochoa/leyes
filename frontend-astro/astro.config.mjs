import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwind from '@astrojs/tailwind';
import pagefind from 'astro-pagefind';

// https://astro.build/config
export default defineConfig({
  output: 'static',
  integrations: [
    react(),
    tailwind(),
    pagefind(),
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
