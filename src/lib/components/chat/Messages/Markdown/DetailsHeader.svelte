<script lang="ts">
	import { getContext } from 'svelte';

	import dayjs from '$lib/dayjs';

	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');

	interface DetailsHeaderProps {
		title?: string | null;
		attributes?: Record<string, string | undefined> | null;
	}

	let { title = null, attributes = null }: DetailsHeaderProps = $props();

	const summaryText = $derived.by(() => {
		if (attributes?.type === 'reasoning') {
			const seconds = parseFloat(attributes?.duration ?? '0');

			if (attributes?.done === 'true' && seconds > 0) {
				if (seconds < 60) {
					return $i18n.t('Thought for {{DURATION}} seconds', {
						DURATION: seconds
					});
				}

				return $i18n.t('Thought for {{DURATION}}', {
					DURATION: dayjs.duration(seconds, 'seconds').humanize()
				});
			}

			if (attributes?.done === 'true') {
				return $i18n.t('Thought shortly');
			}

			return $i18n.t('Thinking...');
		}

		if (attributes?.type === 'web_search') {
			if (attributes?.done === 'true') {
				if (attributes?.action === 'open_page') {
					return `${$i18n.t('Opened')} "${attributes?.url || ''}"`;
				}

				if (attributes?.action === 'find_in_page') {
					return `${$i18n.t('Looked for')} "${attributes?.pattern || ''}" on ${attributes?.url || ''}`;
				}

				return `${$i18n.t('Searched')} "${attributes?.query || ''}"`;
			}

			return $i18n.t('Searching...');
		}

		return title ?? '';
	});
</script>

<div
	class="w-full font-medium flex items-center justify-between gap-2 {attributes?.done &&
	attributes?.done !== 'true'
		? 'shimmer'
		: ''}"
>
	{#if attributes?.done && attributes?.done !== 'true'}
		<div>
			<Spinner className="size-4" />
		</div>
	{/if}

	<div class="min-w-0">
		{summaryText}
	</div>
</div>
