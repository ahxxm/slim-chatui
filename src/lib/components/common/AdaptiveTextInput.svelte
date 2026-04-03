<script lang="ts">
	import PlainTextInput from './PlainTextInput.svelte';

	let {
		richText = true,
		value = '',
		html = '',
		...restProps
	} = $props();

	let inputElement = $state<any>(null);
	let RichTextInputComponent = $state<any>(null);
	let loadingRichTextInput = $state(false);

	const loadRichTextInput = async () => {
		if (RichTextInputComponent || loadingRichTextInput) return;

		loadingRichTextInput = true;

		try {
			const { default: RichTextInput } = await import('./RichTextInput.svelte');
			RichTextInputComponent = RichTextInput;
		} finally {
			loadingRichTextInput = false;
		}
	};

	$effect(() => {
		if (richText && !RichTextInputComponent) {
			void loadRichTextInput();
		}
	});

	const plainTextValue = $derived.by(() => {
		if (typeof value === 'string') return value;

		if (value && typeof value === 'object' && 'md' in value) {
			return String(value.md ?? '');
		}

		if (typeof html === 'string') {
			return html;
		}

		return '';
	});

	export function getWordAtDocPos() {
		return inputElement?.getWordAtDocPos?.() ?? '';
	}

	export async function replaceCommandWithText(text: string) {
		await inputElement?.replaceCommandWithText?.(text);
	}

	export function setText(text = '') {
		inputElement?.setText?.(text);
	}

	export function insertContent(content: string) {
		inputElement?.insertContent?.(content);
	}

	export function focus() {
		inputElement?.focus?.();
	}

	export function setContent(content: unknown) {
		inputElement?.setContent?.(content);
	}

	export function setEditorContent(content: { json?: unknown; md?: string } | null | undefined) {
		if (richText && RichTextInputComponent) {
			inputElement?.setContent?.(content?.json ?? null);
			return;
		}

		inputElement?.setContent?.(content);
	}
</script>

{#if richText && RichTextInputComponent}
	<RichTextInputComponent bind:this={inputElement} {richText} {value} {html} {...restProps} />
{:else}
	<PlainTextInput bind:this={inputElement} value={plainTextValue} {...restProps} />
{/if}
