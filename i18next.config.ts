import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { defineConfig } from 'i18next-cli';
import type { Plugin } from 'i18next-cli';
import { getLanguages } from './src/lib/i18n/index.ts';

const languages = await getLanguages();
const locales = languages.map((l: { code: string }) => l.code);

// i18next-cli's SWC pre-scan can't parse .svelte files and exits non-zero.
// This plugin runs in onEnd (after SWC), globs .svelte files itself, and
// regex-extracts $i18n.t() keys directly into the key map.
//
// Three regexes for three quote styles:
//   $i18n.t('simple key')           → key has no single quotes
//   $i18n.t("key with 'apostrophe") → key has no double quotes
//   $i18n.t(`key with "both"`)      → key has no backticks
const CALLS_BY_QUOTE = [
	/\$i18n\s*\.t\(\s*'([^']*)'/g,
	/\$i18n\s*\.t\(\s*"([^"]*)"/g,
	/\$i18n\s*\.t\(\s*`([^`]*)`/g
];

function extractKeysFromSvelte(code: string): string[] {
	return CALLS_BY_QUOTE.flatMap((re) =>
		[...code.matchAll(re)].map((m) => m[1].replace(/\\n/g, '\n'))
	);
}

const sveltePlugin: Plugin = {
	name: 'svelte-extract',
	onEnd(allKeys) {
		const NS = 'translation';
		for (const file of globSync('src/**/*.svelte')) {
			for (const key of extractKeysFromSvelte(readFileSync(file, 'utf-8'))) {
				const mapKey = `${NS}:${key}`;
				if (!allKeys.has(mapKey)) {
					allKeys.set(mapKey, { key, ns: NS, defaultValue: '' });
				}
			}
		}
	}
};

export default defineConfig({
	locales,
	extract: {
		input: ['src/**/*.{js,ts}'],
		output: 'src/lib/i18n/locales/{{language}}/{{namespace}}.json',
		defaultNS: 'translation',
		defaultValue: '',
		keySeparator: false,
		nsSeparator: false,
		removeUnusedKeys: true,
		sort: true,
		indentation: 2
	},
	plugins: [sveltePlugin]
});
