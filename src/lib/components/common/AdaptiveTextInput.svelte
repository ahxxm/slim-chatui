<script lang="ts">
	import PlainTextInput from './PlainTextInput.svelte';

	type MarkdownEditorValue = {
		md?: string | null;
		json?: unknown;
	};

	interface AdaptiveTextInputProps {
		id?: string;
		richText?: boolean;
		value?: unknown;
		html?: string;
		editable?: boolean;
		placeholder?: string;
		onChange?: (content: { html: string; json: string; md: string }) => void;
		onkeydown?: (event: KeyboardEvent) => void;
		onkeyup?: (event: KeyboardEvent) => void;
		onfocus?: (event: FocusEvent) => void;
		onpaste?: (event: ClipboardEvent) => void;
		oncompositionstart?: (event: CompositionEvent) => void;
		oncompositionend?: (event: CompositionEvent) => void;
		json?: boolean;
		messageInput?: boolean;
		shiftEnter?: boolean;
		largeTextAsFile?: boolean;
		insertPromptAsRichText?: boolean;
		showFormattingToolbar?: boolean;
		[key: string]: unknown;
	}

	const hasMarkdownValue = (value: unknown): value is MarkdownEditorValue =>
		typeof value === 'object' && value !== null && 'md' in value;

	let {
		id = '',
		richText = true,
		value = '',
		html = '',
		editable = true,
		placeholder = '',
		onChange = (_content: { html: string; json: string; md: string }) => {},
		onkeydown = (_event: KeyboardEvent) => {},
		onkeyup = (_event: KeyboardEvent) => {},
		onfocus = (_event: FocusEvent) => {},
		onpaste = (_event: ClipboardEvent) => {},
		oncompositionstart = (_event: CompositionEvent) => {},
		oncompositionend = (_event: CompositionEvent) => {},
		...restProps
	}: AdaptiveTextInputProps = $props();

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

		if (hasMarkdownValue(value)) {
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

	const applyEditorContent = (content: unknown) => {
		inputElement?.setContent?.(content);
	};

	export function setEditorContent(content: { json?: unknown; md?: string } | null | undefined) {
		if (richText && RichTextInputComponent) {
			applyEditorContent(content?.json ?? null);
			return;
		}

		applyEditorContent(content);
	}
</script>

{#if richText && RichTextInputComponent}
	<RichTextInputComponent
		bind:this={inputElement}
		{id}
		{richText}
		{value}
		{html}
		{editable}
		{placeholder}
		{onChange}
		{onkeydown}
		{onkeyup}
		{onfocus}
		{onpaste}
		{oncompositionstart}
		{oncompositionend}
		{...restProps}
	/>
{:else}
	<PlainTextInput
		bind:this={inputElement}
		{id}
		value={plainTextValue}
		{editable}
		{placeholder}
		{onChange}
		{onkeydown}
		{onkeyup}
		{onfocus}
		{onpaste}
		{oncompositionstart}
		{oncompositionend}
	/>
{/if}
