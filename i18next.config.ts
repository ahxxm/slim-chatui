import { defineConfig } from 'i18next-cli';
import type { Plugin } from 'i18next-cli';
import { getLanguages } from './src/lib/i18n/index.ts';

const languages = await getLanguages();
const locales = languages.map((l: { code: string }) => l.code);

// i18next-cli's SWC parser can't read .svelte files directly.
// This plugin regex-extracts $i18n.t() calls and emits plain t() calls for SWC.
// Handles multiline ($i18n\n.t) and both quote styles:
//   $i18n.t('simple key')         → key has no single quotes
//   $i18n.t("key with 'apostrophe") → key has no double quotes
//   $i18n.t(`key with "both"`)    → key has no backticks
const CALLS_BY_QUOTE = [
	/\$i18n\s*\.t\(\s*'([^']*)'/g,
	/\$i18n\s*\.t\(\s*"([^"]*)"/g,
	/\$i18n\s*\.t\(\s*`([^`]*)`/g
];

const sveltePlugin: Plugin = {
	name: 'svelte-extract',
	onLoad(code: string, path: string) {
		if (!path.endsWith('.svelte')) return code;

		const keys = CALLS_BY_QUOTE.flatMap((re) => [...code.matchAll(re)].map((m) => m[1]));
		// Emit t('key') calls that SWC can parse — escape any single quotes in the key
		return keys.map((k) => `t('${k.replace(/'/g, "\\'")}');`).join('\n') || '// no translations';
	}
};

export default defineConfig({
	locales,
	extract: {
		input: ['src/**/*.{js,ts,svelte}'],
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
