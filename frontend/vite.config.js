import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: ['@emotion/babel-plugin'],
      },
    }),
  ],

  // ===== BUILD OPTIMIZATIONS (P-MED-4) =====
  build: {
    // Source maps for production debugging (optional - disable for smaller builds)
    sourcemap: false,

    // Optimize chunk size warnings
    chunkSizeWarningLimit: 600,

    // Advanced rollup options for code splitting
    rollupOptions: {
      output: {
        // Manual chunk splitting strategy (P-MED-4)
        // Splits large vendor libraries into separate chunks for better caching
        manualChunks: {
          // React core - Changes rarely, cache forever
          'react-vendor': ['react', 'react-dom'],

          // UI framework - Chakra UI + Emotion + Framer Motion
          // ~400KB minified -> separate chunk for better caching
          'ui-framework': [
            '@chakra-ui/react',
            '@chakra-ui/tabs',
            '@emotion/react',
            '@emotion/styled',
            'framer-motion'
          ],

          // Chart libraries - Chart.js + Recharts
          // ~470KB minified -> lazy load when needed
          'charts': ['chart.js', 'recharts'],

          // Rich text editors - Load only when opening newsletter/ticket editors
          // ~270KB minified -> significant savings
          'editors': ['react-email-editor', 'react-quill'],

          // Icons library
          'icons': ['react-icons'],

          // HTTP client
          'utils': ['axios']
        },

        // Optimize chunk naming for better cache busting
        chunkFileNames: (chunkInfo) => {
          const facadeModuleId = chunkInfo.facadeModuleId
            ? chunkInfo.facadeModuleId.split('/').pop()
            : 'chunk';
          return `assets/${facadeModuleId}-[hash].js`;
        },

        // Asset naming with hash for cache busting
        assetFileNames: 'assets/[name]-[hash].[ext]',
        entryFileNames: 'assets/[name]-[hash].js',
      },
    },

    // Minification with esbuild for production (P-MED-4)
    // Using esbuild instead of terser - faster build, similar compression
    minify: 'esbuild',

    // Drop console.logs and debugger statements in production
    esbuild: {
      drop: ['console', 'debugger'],
      // Только для production builds
      ...(process.env.NODE_ENV === 'production' ? {
        legalComments: 'none', // Remove comments
      } : {}),
    },

    // Enable CSS code splitting for smaller initial load
    cssCodeSplit: true,
  },

  // Optimize dependency pre-bundling
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      '@chakra-ui/react',
      'chart.js',
      'axios'
    ],
    exclude: []
  },

  css: {
    preprocessorOptions: {
      css: {
        charset: false,
      },
    },
  },
});