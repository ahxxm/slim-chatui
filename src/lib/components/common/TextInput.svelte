<script lang="ts">
	import { getContext, onMount, tick } from 'svelte';

	const i18n = getContext('i18n');

	let {
		id = '',
		value = $bindable(''),
		placeholder = $i18n.t('Type here...'),
		editable = true,
		className = 'w-full resize-none bg-transparent outline-hidden placeholder:text-[#676767]',
		messageInput = false,
		oncompositionstart = (e: CompositionEvent) => {},
		oncompositionend = (e: CompositionEvent) => {},
		onkeydown = (e: KeyboardEvent) => {},
		onkeyup = (e: KeyboardEvent) => {},
		onpaste = (e: ClipboardEvent) => {},
		onfocus = (e: FocusEvent) => {}
	}: {
		id?: string;
		value?: string;
		placeholder?: string;
		editable?: boolean;
		className?: string;
		messageInput?: boolean;
		oncompositionstart?: (e: CompositionEvent) => void;
		oncompositionend?: (e: CompositionEvent) => void;
		onkeydown?: (e: KeyboardEvent) => void;
		onkeyup?: (e: KeyboardEvent) => void;
		onpaste?: (e: ClipboardEvent) => void;
		onfocus?: (e: FocusEvent) => void;
	} = $props();

	let element: HTMLTextAreaElement | null = $state(null);

	export const focus = () => {
		element?.focus();
	};

	export const setText = async (text?: string) => {
		value = text ?? '';
		await tick();
		focus();
		element?.setSelectionRange(value.length, value.length);
	};

	onMount(() => {
		if (messageInput) focus();
	});
</script>

<textarea
	bind:this={element}
	bind:value
	{id}
	{placeholder}
	dir="auto"
	rows="1"
	readonly={!editable}
	aria-label={placeholder}
	class="{className} {!editable ? 'cursor-not-allowed' : ''}"
	style="field-sizing:content;"
	{onkeydown}
	{onkeyup}
	{onpaste}
	{onfocus}
	{oncompositionstart}
	{oncompositionend}></textarea>
