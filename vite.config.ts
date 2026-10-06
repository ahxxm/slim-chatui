import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { playwright } from '@vitest/browser-playwright';
import { defineConfig } from 'vitest/config';
import { defaultClientConditions } from 'vite';

// Browser mode (Firefox headless via Playwright) is opt-in because it needs
// system libraries on dev machines that CI provides: VITEST_BROWSER=1
const browserTests = !!process.env.VITEST_BROWSER;

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			// Consult https://kit.svelte.dev/docs/integrations#preprocessors
			// for more information about preprocessors
			preprocess: vitePreprocess(),
			onwarn: (warning, handler) => {
				const { code } = warning;

				if (code === 'css-unused-selector') return;

				handler(warning);
			},
			adapter: adapter({ pages: 'build', assets: 'build', fallback: 'index.html' }),
			// SvelteKit 3 polls for new versions by default (one hour). Preserve the
			// pre-3 behaviour of no polling: nothing reads `updated.current`.
			version: { pollInterval: 0 }
		}),
		svelteTesting()
	],

	// svelteTesting() assigns resolve.conditions = [], which stops
	// vite-plugin-svelte from filling in the client defaults; without the
	// 'browser' condition the browser server resolves svelte to its server
	// build and mount() fails.
	resolve: browserTests ? { conditions: [...defaultClientConditions, 'svelte'] } : undefined,
	// Pre-bundle deps the components import, so the browser server doesn't
	// discover them mid-run: on-demand optimization reloads the page and
	// cancels whatever test is executing (vitest warns about exactly this).
	optimizeDeps: browserTests ? { include: ['katex', 'katex/contrib/mhchem'] } : undefined,
	test: {
		globalSetup: ['src/lib/test/globalSetup.ts'],
		fileParallelism: false,
		browser: {
			enabled: browserTests,
			provider: playwright(),
			headless: true,
			instances: [{ browser: 'firefox' }]
		}
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
