import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteStaticCopy } from 'vite-plugin-static-copy'; // Import the plugin

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Add the static copy plugin configuration
    viteStaticCopy({
      targets: [
        {
          // Copy from the onnxruntime-web package directly
          src: 'node_modules/onnxruntime-web/dist/*.wasm',
          dest: 'assets/vad-models' // Destination relative to the output 'dist' folder
        },
        {
          // Copy necessary JS/MJS modules from onnxruntime-web
          // Be specific about which files are needed if possible
          src: [
            'node_modules/onnxruntime-web/dist/*.mjs',
            'node_modules/onnxruntime-web/dist/*.js',
            // Add any other specific JS files needed by the runtime
          ],
          dest: 'assets/vad-models',
          // Exclude map files if not needed
          // filter: (fileName) => !fileName.endsWith('.map')
        },
        {
          // Copy the ONNX model from the vad-web package
          src: 'node_modules/@ricky0123/vad-web/dist/*.onnx',
          dest: 'assets/vad-models'
        }
        // Add other necessary files from @ricky0123/vad-web/dist if needed
        // e.g., src: 'node_modules/@ricky0123/vad-web/dist/some-worker.js' etc.
      ]
    })
  ],
  // Optional: If you still face issues, ensure wasm/mjs are known types
  // optimizeDeps: {
  //   include: ['onnxruntime-web']
  // },
  // build: {
  //   assetsInlineLimit: 0 // Prevent inlining small assets if causing issues
  // }
});