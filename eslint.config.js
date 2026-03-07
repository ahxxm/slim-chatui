import js from '@eslint/js';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import sveltePlugin from 'eslint-plugin-svelte';
import cypressPlugin from 'eslint-plugin-cypress';
import prettier from 'eslint-config-prettier';
import svelteParser from 'svelte-eslint-parser';
import globals from 'globals';

export default [
	{ ignores: ['.svelte-kit/**', 'build/**', 'static/**', 'backend/**'] },
	js.configs.recommended,
	{
		files: ['**/*.{js,ts}'],
		plugins: { '@typescript-eslint': tsPlugin },
		languageOptions: {
			parser: tsParser,
			parserOptions: { sourceType: 'module', ecmaVersion: 2020 },
			globals: { ...globals.browser, ...globals.es2017, ...globals.node }
		},
		rules: {
			...tsPlugin.configs.recommended.rules
		}
	},
	...sveltePlugin.configs['flat/recommended'],
	{
		files: ['**/*.svelte'],
		languageOptions: {
			parser: svelteParser,
			parserOptions: { parser: tsParser }
		}
	},
	cypressPlugin.configs.recommended,
	prettier
];
