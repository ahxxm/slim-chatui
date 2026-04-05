<script lang="ts" module>
	import type HljsType from 'highlight.js';

	let hljsPromise: Promise<typeof HljsType> | null = null;
	function getHljs(): Promise<typeof HljsType> {
		if (!hljsPromise) {
			hljsPromise = Promise.all([
				import('$lib/highlight'),
				import('highlight.js/styles/github.min.css')
			]).then(([m]) => m.default);
		}
		return hljsPromise;
	}
</script>

<script lang="ts">
	import { getContext } from 'svelte';

	import { copyToClipboard } from '$lib/utils';

	import ChevronUpDown from '$lib/components/icons/ChevronUpDown.svelte';

	const i18n = getContext('i18n');

	interface CodeBlockProps {
		id?: string;
		collapsed?: boolean;
		done?: boolean;
		lang?: string;
		code?: string;
		className?: string;
		editorClassName?: string;
		stickyButtonsClassName?: string;
	}

	let {
		id = '',
		collapsed = false,
		done = true,
		lang = '',
		code = '',
		className = '',
		editorClassName = '',
		stickyButtonsClassName = 'top-0'
	}: CodeBlockProps = $props();

	let hljs: typeof HljsType | null = $state(null);

	$effect(() => {
		if (collapsed || hljs) return;

		let cancelled = false;
		getHljs().then((instance) => {
			if (!cancelled) {
				hljs = instance;
			}
		});

		return () => {
			cancelled = true;
		};
	});

	let copied = $state(false);

	const collapseCodeBlock = () => {
		collapsed = !collapsed;
	};

	const copyCode = async () => {
		copied = true;
		await copyToClipboard(code);

		setTimeout(() => {
			copied = false;
		}, 1000);
	};
</script>

<div>
	<div
		class="relative {className} flex flex-col rounded-2xl border border-gray-200 dark:border-gray-800 my-0.5"
		dir="ltr"
	>
		<div class="absolute left-0 right-0 py-1.5 pr-3 text-gray-500 pl-4.5 text-xs font-medium">
			{lang}
		</div>

		<div
			class="sticky {stickyButtonsClassName} left-0 right-0 py-1.5 pr-3 flex items-center justify-end w-full z-10 text-xs text-gray-600"
		>
			<div class="flex items-center gap-0.5">
				<button
					class="flex gap-1 items-center bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white/80"
					onclick={collapseCodeBlock}
				>
					<div class=" -translate-y-[0.5px]">
						<ChevronUpDown className="size-3" />
					</div>

					<div>
						{collapsed ? $i18n.t('Expand') : $i18n.t('Collapse')}
					</div>
				</button>

				<button
					class="copy-code-button bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white/80"
					onclick={copyCode}>{copied ? $i18n.t('Copied') : $i18n.t('Copy')}</button
				>
			</div>
		</div>

		<div
			class="language-{lang} rounded-t-2xl -mt-8 {editorClassName
				? editorClassName
				: 'rounded-b-2xl'} overflow-hidden"
		>
			<div class=" pt-6.5 bg-white"></div>

			{#if !collapsed}
				<pre
					class=" hljs p-4 px-5 overflow-x-auto"
					style="border-top-left-radius: 0px; border-top-right-radius: 0px;">
					{#if done && hljs}
						<code class="language-{lang} rounded-t-none whitespace-pre text-sm"
							>{@html hljs.highlightAuto(code, hljs.getLanguage(lang)?.aliases).value || code}</code
						>
					{:else}
						<code class="language-{lang} rounded-t-none whitespace-pre text-sm">{code}</code>
					{/if}
				</pre>
			{:else}
				<div class="bg-white rounded-b-2xl! pt-0.5 pb-2 px-4 flex flex-col gap-2 text-xs">
					<span class="text-gray-500 italic">
						{$i18n.t('{{COUNT}} hidden lines', {
							COUNT: code.split('\n').length
						})}
					</span>
				</div>
			{/if}
		</div>
	</div>
</div>
