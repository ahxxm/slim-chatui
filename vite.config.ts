import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit(), svelteTesting()],
	test: {
		globalSetup: ['src/lib/test/globalSetup.ts'],
		fileParallelism: false
	},
	define: {
		APP_VERSION: JSON.stringify(process.env.npm_package_version),
		APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
	},
	build: {
		sourcemap: false,
		reportCompressedSize: false,
		rolldownOptions: {
			treeshake: {
				manualPureFunctions:
					process.env.ENV === 'dev' ? [] : ['console.log', 'console.debug', 'console.error']
			}
		}
	}
});
