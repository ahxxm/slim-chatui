<script lang="ts">
	type MarkdownEditorValue = {
		md?: string | null;
		json?: unknown;
	};

	type EditorContent = {
		html: string;
		json: string;
		md: string;
	};

	type SettableEditorContent = string | MarkdownEditorValue | null | undefined;

	interface AdaptiveTextInputProps {
		id?: string;
		richText?: boolean;
		value?: unknown;
		html?: string;
		editable?: boolean;
		placeholder?: string;
		onChange?: (content: EditorContent) => void;
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
	}

	const hasMarkdownValue = (value: unknown): value is MarkdownEditorValue =>
		typeof value === 'object' && value !== null && 'md' in value;

	const getWordBounds = (text: string, cursor: number) => {
		let start = cursor;
		let end = cursor;

		while (start > 0 && !/\s/.test(text[start - 1])) start--;
		while (end < text.length && !/\s/.test(text[end])) end++;

		return { start, end };
	};

	let {
		id = '',
		richText = true,
		value = '',
		html = '',
		editable = true,
		placeholder = '',
		onChange = (_content: EditorContent) => {},
		onkeydown = (_event: KeyboardEvent) => {},
		onkeyup = (_event: KeyboardEvent) => {},
		onfocus = (_event: FocusEvent) => {},
		onpaste = (_event: ClipboardEvent) => {},
		oncompositionstart = (_event: CompositionEvent) => {},
		oncompositionend = (_event: CompositionEvent) => {},
		json = false,
		messageInput = false,
		shiftEnter = false,
		largeTextAsFile = false,
		insertPromptAsRichText = false,
		showFormattingToolbar = true
	}: AdaptiveTextInputProps = $props();

	let richTextInputElement = $state<any>(null);
	let textareaElement = $state<HTMLTextAreaElement>();
	let RichTextInputComponent = $state<any>(null);
	let loadingRichTextInput = $state(false);
	let textValue = $state('');

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
		if (hasMarkdownValue(value)) return String(value.md ?? '');
		if (typeof html === 'string') return html;
		return '';
	});

	const showPlainTextFallback = $derived(!richText || !RichTextInputComponent);
	const usingRichTextInput = $derived(
		Boolean(richText && RichTextInputComponent && richTextInputElement)
	);

	const resizeTextarea = () => {
		if (!textareaElement) return;
		textareaElement.style.height = '0px';
		textareaElement.style.height = `${textareaElement.scrollHeight}px`;
	};

	const emitPlainTextChange = (nextText = textValue) => {
		onChange({
			html: nextText,
			json: nextText,
			md: nextText
		});
	};

	const setTextareaCursor = (cursor: number) => {
		if (!textareaElement) return;
		textareaElement.setSelectionRange(cursor, cursor);
	};

	const commitPlainTextValue = (nextText: string, cursor = nextText.length) => {
		textValue = nextText;

		if (textareaElement) {
			if (textareaElement.value !== nextText) {
				textareaElement.value = nextText;
			}
			resizeTextarea();
			setTextareaCursor(cursor);
		}

		emitPlainTextChange(nextText);
	};

	$effect(() => {
		if (!showPlainTextFallback || plainTextValue === textValue) return;
		textValue = plainTextValue;
	});

	$effect(() => {
		if (!showPlainTextFallback || !textareaElement) return;
		if (textareaElement.value !== textValue) {
			textareaElement.value = textValue;
		}
		resizeTextarea();
	});

	export function getWordAtDocPos() {
		if (usingRichTextInput) {
			return richTextInputElement?.getWordAtDocPos?.() ?? '';
		}

		if (!textareaElement) return '';
		const text = textareaElement.value;
		const cursor = textareaElement.selectionStart ?? 0;
		const { start, end } = getWordBounds(text, cursor);
		return text.slice(start, end);
	}

	export async function replaceCommandWithText(text: string) {
		if (usingRichTextInput) {
			await richTextInputElement?.replaceCommandWithText?.(text);
			return;
		}

		if (!textareaElement) return;
		const currentText = textareaElement.value;
		const cursor = textareaElement.selectionStart ?? currentText.length;
		const { start, end } = getWordBounds(currentText, cursor);
		const nextText = `${currentText.slice(0, start)}${text}${currentText.slice(end)}`;
		commitPlainTextValue(nextText, start + text.length);
		focus();
	}

	export function setText(text = '') {
		if (usingRichTextInput) {
			richTextInputElement?.setText?.(text);
			return;
		}

		commitPlainTextValue(text);
		focus();
	}

	export function insertContent(content: string) {
		if (usingRichTextInput) {
			richTextInputElement?.insertContent?.(content);
			return;
		}

		if (!textareaElement) return;
		const currentText = textareaElement.value;
		const selectionStart = textareaElement.selectionStart ?? currentText.length;
		const selectionEnd = textareaElement.selectionEnd ?? selectionStart;
		const nextText = `${currentText.slice(0, selectionStart)}${content}${currentText.slice(selectionEnd)}`;
		commitPlainTextValue(nextText, selectionStart + content.length);
		focus();
	}

	export function focus() {
		if (usingRichTextInput) {
			richTextInputElement?.focus?.();
			return;
		}

		if (!textareaElement) return;
		textareaElement.focus();
		textareaElement.scrollTop = textareaElement.scrollHeight;
	}

	export function setEditorContent(content: SettableEditorContent) {
		if (usingRichTextInput) {
			richTextInputElement?.setContent?.(
				typeof content === 'string' ? content : (content?.json ?? null)
			);
			return;
		}

		if (typeof content === 'string') {
			setText(content);
			return;
		}

		if (hasMarkdownValue(content)) {
			setText(String(content.md ?? ''));
			return;
		}

		setText('');
	}
</script>

{#if richText && RichTextInputComponent}
	<RichTextInputComponent
		bind:this={richTextInputElement}
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
		{json}
		{messageInput}
		{shiftEnter}
		{largeTextAsFile}
		{insertPromptAsRichText}
		{showFormattingToolbar}
	/>
{:else}
	<textarea
		bind:this={textareaElement}
		{id}
		rows="1"
		value={textValue}
		{placeholder}
		readonly={!editable}
		class="w-full min-h-[1.75rem] resize-none overflow-hidden bg-transparent text-sm outline-hidden"
		oninput={(event) => {
			textValue = event.currentTarget.value;
			resizeTextarea();
			emitPlainTextChange();
		}}
		onfocus={editable ? onfocus : undefined}
		onkeydown={editable ? onkeydown : undefined}
		onkeyup={editable ? onkeyup : undefined}
		onpaste={editable ? onpaste : undefined}
		oncompositionstart={editable ? oncompositionstart : undefined}
		oncompositionend={editable ? oncompositionend : undefined}
	></textarea>
{/if}
