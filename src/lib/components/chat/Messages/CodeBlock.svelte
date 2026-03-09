<script lang="ts" context="module">
	import type HljsType from 'highlight.js';

	let hljsPromise: Promise<typeof HljsType> | null = null;
	function getHljs(): Promise<typeof HljsType> {
		if (!hljsPromise) {
			hljsPromise = Promise.all([
				import('$lib/highlight'),
				import('highlight.js/styles/github-dark.min.css')
			]).then(([m]) => m.default);
		}
		return hljsPromise;
	}
</script>

<script lang="ts">
	import { onMount, getContext } from 'svelte';

	import { copyToClipboard } from '$lib/utils';

	import ChevronUpDown from '$lib/components/icons/ChevronUpDown.svelte';

	const i18n = getContext('i18n');

	let {
		id = '',
		edit = true,
		onSave = (e) => {},
		save = false,
		collapsed = false,
		lang = '',
		code = '',
		className = '',
		editorClassName = '',
		stickyButtonsClassName = 'top-0'
	} = $props();

	let _code = $state(code);
	$effect(() => {
		_code = code;
	});

	let hljs: typeof HljsType | null = $state(null);
	onMount(async () => {
		hljs = await getHljs();
	});

	let copied = $state(false);
	let saved = $state(false);

	const collapseCodeBlock = () => {
		collapsed = !collapsed;
	};

	const saveCode = () => {
		saved = true;

		code = _code;
		onSave(code);

		setTimeout(() => {
			saved = false;
		}, 1000);
	};

	const copyCode = async () => {
		copied = true;
		await copyToClipboard(_code);

		setTimeout(() => {
			copied = false;
		}, 1000);
	};
</script>

<div>
	<div
		class="relative {className} flex flex-col rounded-2xl border border-gray-100/30 dark:border-gray-850/30 my-0.5"
		dir="ltr"
	>
		<div
			class="absolute left-0 right-0 py-1.5 pr-3 text-text-300 pl-4.5 text-xs font-medium dark:text-white"
		>
			{lang}
		</div>

		<div
			class="sticky {stickyButtonsClassName} left-0 right-0 py-1.5 pr-3 flex items-center justify-end w-full z-10 text-xs text-black dark:text-white"
		>
			<div class="flex items-center gap-0.5">
				<button
					class="flex gap-1 items-center bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
					onclick={collapseCodeBlock}
				>
					<div class=" -translate-y-[0.5px]">
						<ChevronUpDown className="size-3" />
					</div>

					<div>
						{collapsed ? $i18n.t('Expand') : $i18n.t('Collapse')}
					</div>
				</button>

				{#if save}
					<button
						class="save-code-button bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
						onclick={saveCode}
					>
						{saved ? $i18n.t('Saved') : $i18n.t('Save')}
					</button>
				{/if}

				<button
					class="copy-code-button bg-none border-none transition rounded-md px-1.5 py-0.5 bg-white dark:bg-black"
					onclick={copyCode}>{copied ? $i18n.t('Copied') : $i18n.t('Copy')}</button
				>
			</div>
		</div>

		<div
			class="language-{lang} rounded-t-2xl -mt-8 {editorClassName
				? editorClassName
				: 'rounded-b-2xl'} overflow-hidden"
		>
			<div class=" pt-6.5 bg-white dark:bg-black"></div>

			{#if !collapsed}
				{#if edit}
					{#await import('$lib/components/common/CodeEditor.svelte') then { default: CodeEditor }}
						<CodeEditor
							value={code}
							{id}
							{lang}
							onSave={() => {
								saveCode();
							}}
							onChange={(value) => {
								_code = value;
							}}
						/>
					{/await}
				{:else}
					<pre
						class=" hljs p-4 px-5 overflow-x-auto"
						style="border-top-left-radius: 0px; border-top-right-radius: 0px;"><code
							class="language-{lang} rounded-t-none whitespace-pre text-sm"
							>{@html hljs
								? hljs.highlightAuto(code, hljs.getLanguage(lang)?.aliases).value || code
								: code}</code
						></pre>
				{/if}
			{:else}
				<div
					class="bg-white dark:bg-black dark:text-white rounded-b-2xl! pt-0.5 pb-2 px-4 flex flex-col gap-2 text-xs"
				>
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
