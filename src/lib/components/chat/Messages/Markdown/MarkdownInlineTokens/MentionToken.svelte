<script lang="ts">
	import type { Token } from 'marked';

	import { getContext, untrack } from 'svelte';

	import { goto } from '$app/navigation';
	import { models } from '$lib/stores';

	const i18n = getContext('i18n');

	let { token }: { token: Token } = $props();

	let triggerChar = $state('');
	let label = $state('');

	let idType = $state(null);
	let id = $state('');

	$effect(() => {
		token;
		untrack(() => init());
	});

	const init = () => {
		const _id = token?.id;
		triggerChar = token?.triggerChar ?? '@';

		const parts = _id?.split(':');
		if (parts) {
			idType = parts[0];
			id = parts.slice(1).join(':');
		} else {
			idType = null;
			id = _id;
		}

		label = token?.label ?? id;

		if (triggerChar === '@' && idType === 'M') {
			const model = $models.find((m) => m.id === id);
			if (model) {
				label = model.name;
			} else {
				label = $i18n.t('Unknown');
			}
		}
	};
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<span
	class="mention cursor-pointer"
	on:click={async () => {
		if (triggerChar === '@' && idType === 'M') {
			await goto(`/?model=${id}`);
		}
	}}
>
	{triggerChar}{label}
</span>
