<script lang="ts">
	import { decode } from 'html-entities';
	import type { Token } from 'marked';
	import { getContext } from 'svelte';

	import { settings } from '$lib/stores';
	import { copyToClipboard, saveAs } from '$lib/utils';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Download from '$lib/components/icons/Download.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';

	import MarkdownInlineTokens from './MarkdownInlineTokens.svelte';

	type MarkdownTableCell = {
		text?: string | null;
		tokens?: (Token & Record<string, any>)[];
	};

	type MarkdownTableToken = Token & Record<string, any>;

	interface MarkdownTableProps {
		id: string;
		token: MarkdownTableToken;
	}

	const i18n = getContext('i18n');

	let { id, token }: MarkdownTableProps = $props();

	const escapeCsvValue = (value: string): string => `"${decode(value).replace(/"/g, '""')}"`;

	const getCellText = (cell: MarkdownTableCell): string =>
		(cell.tokens ?? [])
			.map((childToken) => ('text' in childToken ? (childToken.text ?? '') : ''))
			.join('') ||
		cell.text ||
		'';

	const exportTableToCsv = () => {
		const header = (token.header ?? []).map((cell: MarkdownTableCell) =>
			escapeCsvValue(cell.text ?? '')
		);
		const rows = (token.rows ?? []).map((row: MarkdownTableCell[]) =>
			row.map((cell: MarkdownTableCell) => escapeCsvValue(getCellText(cell)))
		);
		const csvContent = [header, ...rows].map((row) => row.join(',')).join('\n');
		const blob = new Blob([`\uFEFF${csvContent}`], { type: 'text/csv;charset=UTF-8' });

		saveAs(blob, `table-${id}.csv`);
	};
</script>

<div class="relative mb-2 w-full group">
	<div class="scrollbar-hidden relative max-w-full overflow-x-auto">
		<table
			class="w-full max-w-full rounded-xl text-start text-sm text-gray-500 dark:text-gray-400"
			dir="auto"
		>
			<thead
				class="border-none bg-white text-xs uppercase text-gray-700 dark:bg-gray-900 dark:text-gray-400"
			>
				<tr>
					{#each token.header ?? [] as header, headerIdx}
						<th
							scope="col"
							class="cursor-pointer border-b border-gray-100! px-2.5! py-2! dark:border-gray-800!"
							style={token.align?.[headerIdx] ? `text-align: ${token.align[headerIdx]}` : ''}
						>
							<div class="gap-1.5 text-start">
								<div class="shrink-0 break-normal">
									<MarkdownInlineTokens
										id={`${id}-header-${headerIdx}`}
										source={header.text ?? ''}
										tokens={header.tokens}
									/>
								</div>
							</div>
						</th>
					{/each}
				</tr>
			</thead>

			<tbody>
				{#each token.rows ?? [] as row, rowIdx}
					<tr class="bg-white text-xs dark:bg-gray-900">
						{#each row as cell, cellIdx}
							<td
								class="w-max px-3! py-2! text-gray-900 dark:text-white {rowIdx ===
								(token.rows?.length ?? 0) - 1
									? ''
									: 'border-b border-gray-50! dark:border-gray-850!'}"
								style={token.align?.[cellIdx] ? `text-align: ${token.align[cellIdx]}` : ''}
							>
								<div class="break-normal">
									<MarkdownInlineTokens
										id={`${id}-row-${rowIdx}-${cellIdx}`}
										source={cell.text ?? ''}
										tokens={cell.tokens}
									/>
								</div>
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<div class="absolute top-1 right-1.5 z-20 invisible flex gap-0.5 group-hover:visible">
		<Tooltip content={$i18n.t('Copy')}>
			<button
				class="rounded-lg bg-transparent p-1 transition"
				onclick={(event) => {
					event.stopPropagation();
					copyToClipboard(token.raw.trim(), null, $settings?.copyFormatted ?? false);
				}}
			>
				<Clipboard className="size-3.5" strokeWidth="1.5" />
			</button>
		</Tooltip>

		<Tooltip content={$i18n.t('Export to CSV')}>
			<button
				class="rounded-lg bg-transparent p-1 transition"
				onclick={(event) => {
					event.stopPropagation();
					exportTableToCsv();
				}}
			>
				<Download className="size-3.5" strokeWidth="1.5" />
			</button>
		</Tooltip>
	</div>
</div>
