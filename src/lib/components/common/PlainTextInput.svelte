<script lang="ts">
	import { tick } from 'svelte';

	let {
		id = '',
		value = '',
		editable = true,
		placeholder = '',
		onChange = (_content: { html: string; json: string; md: string }) => {},
		onkeydown = (_event: KeyboardEvent) => {},
		onpaste = (_event: ClipboardEvent) => {},
		oncompositionstart = (_event: CompositionEvent) => {},
		oncompositionend = (_event: CompositionEvent) => {}
	} = $props();

	let textareaElement = $state<HTMLTextAreaElement>();
	let textValue = $state('');

	const emitChange = () => {
		onChange({
			html: textValue,
			json: textValue,
			md: textValue
		});
	};

	const resizeToContent = () => {
		if (!textareaElement) return;
		textareaElement.style.height = '0px';
		textareaElement.style.height = `${textareaElement.scrollHeight}px`;
	};

	const setSelection = (start: number, end = start) => {
		if (!textareaElement) return;
		textareaElement.setSelectionRange(start, end);
	};

	const replaceRange = (nextText: string, start: number, end = start, nextCursor = start) => {
		textValue = nextText;
		if (textareaElement) {
			textareaElement.value = nextText;
			setSelection(nextCursor);
		}
		resizeToContent();
		emitChange();
	};

	$effect(() => {
		const nextValue = typeof value === 'string' ? value : '';
		if (nextValue === textValue) return;
		textValue = nextValue;
		if (textareaElement) {
			textareaElement.value = nextValue;
			resizeToContent();
		}
	});

	export function getWordAtDocPos() {
		if (!textareaElement) return '';
		const text = textareaElement.value;
		const cursor = textareaElement.selectionStart ?? 0;

		let wordStart = cursor;
		let wordEnd = cursor;

		while (wordStart > 0 && !/\s/.test(text[wordStart - 1])) wordStart--;
		while (wordEnd < text.length && !/\s/.test(text[wordEnd])) wordEnd++;

		return text.slice(wordStart, wordEnd);
	}

	export async function replaceCommandWithText(text: string) {
		if (!textareaElement) return;

		const currentText = textareaElement.value;
		const cursor = textareaElement.selectionStart ?? currentText.length;

		let wordStart = cursor;
		let wordEnd = cursor;

		while (wordStart > 0 && !/\s/.test(currentText[wordStart - 1])) wordStart--;
		while (wordEnd < currentText.length && !/\s/.test(currentText[wordEnd])) wordEnd++;

		const nextText = `${currentText.slice(0, wordStart)}${text}${currentText.slice(wordEnd)}`;
		replaceRange(nextText, wordStart, wordEnd, wordStart + text.length);

		await tick();
		focus();
	}

	export function setText(text = '') {
		const normalizedText = text.replaceAll('\n\n', '\n');
		replaceRange(normalizedText, normalizedText.length);
		focus();
	}

	export function insertContent(content: string) {
		if (!textareaElement) return;

		const currentText = textareaElement.value;
		const selectionStart = textareaElement.selectionStart ?? currentText.length;
		const selectionEnd = textareaElement.selectionEnd ?? selectionStart;
		const nextText = `${currentText.slice(0, selectionStart)}${content}${currentText.slice(selectionEnd)}`;

		replaceRange(nextText, selectionStart, selectionEnd, selectionStart + content.length);
		focus();
	}

	export function focus() {
		if (!textareaElement) return;
		textareaElement.focus();
		textareaElement.scrollTop = textareaElement.scrollHeight;
	}

	export function setContent(content: unknown) {
		if (typeof content === 'string') {
			setText(content);
			return;
		}

		if (content && typeof content === 'object' && 'md' in content) {
			setText(String(content.md ?? ''));
			return;
		}

		setText('');
	}
</script>

<textarea
	bind:this={textareaElement}
	{id}
	rows="1"
	value={textValue}
	placeholder={placeholder}
	readonly={!editable}
	class="w-full min-h-[1.75rem] resize-none overflow-hidden bg-transparent text-sm outline-hidden"
	oninput={(event) => {
		textValue = event.currentTarget.value;
		resizeToContent();
		emitChange();
	}}
	onkeydown={editable ? onkeydown : undefined}
	onpaste={editable ? onpaste : undefined}
	oncompositionstart={editable ? oncompositionstart : undefined}
	oncompositionend={editable ? oncompositionend : undefined}
></textarea>
