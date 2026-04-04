<script lang="ts" module>
	import type { ComponentType } from 'svelte';
	import { marked, type Token } from 'marked';

	import ArrowRightCircle from '$lib/components/icons/ArrowRightCircle.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import Info from '$lib/components/icons/Info.svelte';
	import LightBulb from '$lib/components/icons/LightBulb.svelte';
	import Star from '$lib/components/icons/Star.svelte';

	type AlertType = 'NOTE' | 'TIP' | 'IMPORTANT' | 'WARNING' | 'CAUTION';
	type AlertToken = Token & { text?: string | null };

	interface AlertTheme {
		border: string;
		text: string;
		icon: ComponentType;
	}

	export interface AlertData {
		type: AlertType;
		text: string;
		tokens: Token[];
	}

	const alertStyles: Record<AlertType, AlertTheme> = {
		NOTE: {
			border: 'border-sky-500',
			text: 'text-sky-500',
			icon: Info
		},
		TIP: {
			border: 'border-emerald-500',
			text: 'text-emerald-500',
			icon: LightBulb
		},
		IMPORTANT: {
			border: 'border-purple-500',
			text: 'text-purple-500',
			icon: Star
		},
		WARNING: {
			border: 'border-yellow-500',
			text: 'text-yellow-500',
			icon: ArrowRightCircle
		},
		CAUTION: {
			border: 'border-rose-500',
			text: 'text-rose-500',
			icon: Bolt
		}
	};

	export function alertComponent(token: AlertToken): AlertData | false {
		const regExpStr = `^(?:\\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\\])\\s*?\n*`;
		const regExp = new RegExp(regExpStr);
		const rawText = token.text ?? '';
		const matches = rawText.match(regExp);

		if (matches && matches.length) {
			const alertType = matches[1] as AlertType;
			const newText = rawText.replace(regExp, '');
			const newTokens = marked.lexer(newText);
			return {
				type: alertType,
				text: newText,
				tokens: newTokens
			};
		}
		return false;
	}
</script>

<script lang="ts">
	import MarkdownTokens from './MarkdownTokens.svelte';

	interface AlertRendererProps {
		alert: AlertData;
		id?: string;
		tokenIdx?: number;
	}

	let { alert, id = '', tokenIdx = 0 }: AlertRendererProps = $props();
	let AlertIcon = $derived(alertStyles[alert.type].icon);
</script>

<!--

Renders the following Markdown as alerts:

> [!NOTE]
> Example note

> [!TIP]
> Example tip

> [!IMPORTANT]
> Example important

> [!CAUTION]
> Example caution

> [!WARNING]
> Example warning

-->
<div class={`border-l-4 pl-2.5 ${alertStyles[alert.type].border} my-0.5`}>
	<div class="{alertStyles[alert.type].text} items-center flex gap-1 py-1.5">
		<AlertIcon className="inline-block size-4" />
		<span class=" font-medium">{alert.type}</span>
	</div>
	<div class="pb-2">
		<MarkdownTokens id={`${id}-${tokenIdx}`} tokens={alert.tokens} />
	</div>
</div>
