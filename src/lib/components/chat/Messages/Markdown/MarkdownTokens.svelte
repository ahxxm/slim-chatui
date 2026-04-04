<script lang="ts">
	import type { Links, Token } from 'marked';
	import { decode } from 'html-entities';
	import { getContext } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	const i18n = getContext('i18n');

	import { saveAs } from '$lib/utils';

	import { copyToClipboard, unescapeHtml } from '$lib/utils';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { settings } from '$lib/stores';
	import { EMPTY_LINKS } from '$lib/utils/marked/incremental';
	import { createIndexedDetailsStateIds } from '$lib/utils/marked/details-state';

	import CodeBlock from '$lib/components/chat/Messages/CodeBlock.svelte';
	import MarkdownInlineTokens from '$lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte';
	import MarkdownTokens from '$lib/components/chat/Messages/Markdown/MarkdownTokens.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import AlertRenderer, { alertComponent } from './AlertRenderer.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import ToolCallDisplay from '$lib/components/common/ToolCallDisplay.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Download from '$lib/components/icons/Download.svelte';

	import HtmlToken from './HTMLToken.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';

	type MarkdownToken = Token & Record<string, any>;
	type MarkdownTextFragment = { text?: string | null };
	type MarkdownTableCell = {
		text?: string | null;
		tokens?: MarkdownTextFragment[];
	};

	interface MarkdownTokensProps {
		id: string;
		tokens?: MarkdownToken[];
		top?: boolean;
		sourceIds?: string[];
		done?: boolean;
		save?: boolean;
		paragraphTag?: 'p' | 'span';
		editCodeBlock?: boolean;
		topPadding?: boolean;
		links?: Links;
		incremental?: boolean;
		onSave?: (value: unknown) => void;
		onTaskClick?: (value: unknown) => void;
		onSourceClick?: (value: unknown) => void;
		openStates?: SvelteMap<string, boolean>;
		detailsScopeId?: string;
		rootDetailsStateId?: string | null;
	}

	let {
		id,
		tokens = [],
		top = true,
		sourceIds = [],
		done = true,
		save = false,
		paragraphTag = 'p',
		editCodeBlock = true,
		topPadding = false,
		links = EMPTY_LINKS,
		incremental = false,
		onSave = () => {},
		onTaskClick = () => {},
		onSourceClick = () => {},
		openStates = new SvelteMap<string, boolean>(),
		detailsScopeId = id,
		rootDetailsStateId = null
	}: MarkdownTokensProps = $props();

	let detailsStateIds = $derived(
		createIndexedDetailsStateIds(tokens, (token) => token as Token, detailsScopeId)
	);

	const getOpenState = (stateId: string, defaultOpen: boolean) =>
		openStates.get(stateId) ?? defaultOpen;
	const setOpenState = (stateId: string, nextOpen: boolean) => {
		if (openStates.get(stateId) !== nextOpen) {
			openStates.set(stateId, nextOpen);
		}
	};

	const headerComponent = (depth: number) => {
		return 'h' + depth;
	};

	const exportTableToCSVHandler = (token: MarkdownToken, tokenIdx = 0) => {
		console.log('Exporting table to CSV');

		// Extract header row text, decode HTML entities, and escape for CSV.
		const header = (token.header ?? []).map(
			(headerCell: MarkdownTableCell) => `"${decode(headerCell.text ?? '').replace(/"/g, '""')}"`
		);

		// Create an array for rows that will hold the mapped cell text.
		const rows = (token.rows ?? []).map((row: MarkdownTableCell[]) =>
			row.map((cell: MarkdownTableCell) => {
				// Map tokens into a single text
				const cellContent = (cell.tokens ?? [])
					.map((childToken: MarkdownTextFragment) => childToken.text ?? '')
					.join('');
				// Decode HTML entities and escape double quotes, wrap in double quotes
				return `"${decode(cellContent).replace(/"/g, '""')}"`;
			})
		);

		// Combine header and rows
		const csvData = [header, ...rows];

		// Join the rows using commas (,) as the separator and rows using newline (\n).
		const csvContent = csvData.map((row) => row.join(',')).join('\n');

		// Log rows and CSV content to ensure everything is correct.
		console.log(csvData);
		console.log(csvContent);

		// To handle Unicode characters, you need to prefix the data with a BOM:
		const bom = '\uFEFF'; // BOM for UTF-8

		// Create a new Blob prefixed with the BOM to ensure proper Unicode encoding.
		const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=UTF-8' });

		// Use FileSaver.js's saveAs function to save the generated CSV file.
		saveAs(blob, `table-${id}-${tokenIdx}.csv`);
	};
</script>

<!-- {JSON.stringify(tokens)} -->
{#each tokens as token, tokenIdx (tokenIdx)}
	{#if token.type === 'hr'}
		<hr class=" border-gray-100/30 dark:border-gray-850/30" />
	{:else if token.type === 'heading'}
		<svelte:element this={headerComponent(token.depth)} dir="auto">
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-h`}
				source={token.text ?? ''}
				tokens={token.tokens}
				{done}
				{sourceIds}
				{onSourceClick}
				{links}
				{incremental}
			/>
		</svelte:element>
	{:else if token.type === 'code'}
		{#if token.raw.includes('```')}
			<CodeBlock
				id={`${id}-${tokenIdx}`}
				collapsed={$settings?.collapseCodeBlocks ?? false}
				{done}
				lang={token?.lang ?? ''}
				code={token?.text ?? ''}
				{save}
				edit={editCodeBlock}
				stickyButtonsClassName={topPadding ? 'top-10' : 'top-0'}
				onSave={(value: unknown) => {
					onSave({
						raw: token.raw,
						oldContent: token.text,
						newContent: value
					});
				}}
			/>
		{:else}
			{token.text}
		{/if}
	{:else if token.type === 'table'}
		<div class="relative w-full group mb-2">
			<div class="scrollbar-hidden relative overflow-x-auto max-w-full">
				<table
					class=" w-full text-sm text-start text-gray-500 dark:text-gray-400 max-w-full rounded-xl"
					dir="auto"
				>
					<thead
						class="text-xs text-gray-700 uppercase bg-white dark:bg-gray-900 dark:text-gray-400 border-none"
					>
						<tr class="">
							{#each token.header as header, headerIdx}
								<th
									scope="col"
									class="px-2.5! py-2! cursor-pointer border-b border-gray-100! dark:border-gray-800!"
									style={token.align[headerIdx] ? `text-align: ${token.align[headerIdx]}` : ''}
								>
									<div class="gap-1.5 text-start">
										<div class="shrink-0 break-normal">
											<MarkdownInlineTokens
												id={`${id}-${tokenIdx}-header-${headerIdx}`}
												source={header.text ?? ''}
												tokens={header.tokens}
												{done}
												{sourceIds}
												{onSourceClick}
												{links}
												{incremental}
											/>
										</div>
									</div>
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each token.rows as row, rowIdx}
							<tr class="bg-white dark:bg-gray-900 text-xs">
								{#each row ?? [] as cell, cellIdx}
									<td
										class="px-3! py-2! text-gray-900 dark:text-white w-max {token.rows.length -
											1 ===
										rowIdx
											? ''
											: 'border-b border-gray-50! dark:border-gray-850!'}"
										style={token.align[cellIdx] ? `text-align: ${token.align[cellIdx]}` : ''}
									>
										<div class="break-normal">
											<MarkdownInlineTokens
												id={`${id}-${tokenIdx}-row-${rowIdx}-${cellIdx}`}
												source={cell.text ?? ''}
												tokens={cell.tokens}
												{done}
												{sourceIds}
												{onSourceClick}
												{links}
												{incremental}
											/>
										</div>
									</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<div class=" absolute top-1 right-1.5 z-20 invisible group-hover:visible flex gap-0.5">
				<Tooltip content={$i18n.t('Copy')}>
					<button
						class="p-1 rounded-lg bg-transparent transition"
						onclick={(e) => {
							e.stopPropagation();
							copyToClipboard(token.raw.trim(), null, $settings?.copyFormatted ?? false);
						}}
					>
						<Clipboard className=" size-3.5" strokeWidth="1.5" />
					</button>
				</Tooltip>

				<Tooltip content={$i18n.t('Export to CSV')}>
					<button
						class="p-1 rounded-lg bg-transparent transition"
						onclick={(e) => {
							e.stopPropagation();
							exportTableToCSVHandler(token, tokenIdx);
						}}
					>
						<Download className=" size-3.5" strokeWidth="1.5" />
					</button>
				</Tooltip>
			</div>
		</div>
	{:else if token.type === 'blockquote'}
		{@const alert = alertComponent(token)}
		{#if alert}
			<AlertRenderer {alert} />
		{:else}
			<blockquote dir="auto">
				<MarkdownTokens
					id={`${id}-${tokenIdx}`}
					tokens={token.tokens}
					{done}
					{save}
					{paragraphTag}
					{editCodeBlock}
					{topPadding}
					{links}
					{incremental}
					{onSave}
					{onTaskClick}
					{sourceIds}
					{onSourceClick}
					{openStates}
					{detailsScopeId}
					rootDetailsStateId={null}
				/>
			</blockquote>
		{/if}
	{:else if token.type === 'list'}
		{#if token.ordered}
			<ol start={token.start || 1} dir="auto">
				{#each token.items as item, itemIdx}
					<li class="text-start">
						{#if item?.task}
							<input
								class=" translate-y-[1px] -translate-x-1"
								type="checkbox"
								checked={item.checked}
								onchange={(e) => {
									onTaskClick({
										id: id,
										token: token,
										tokenIdx: tokenIdx,
										item: item,
										itemIdx: itemIdx,
										checked: e.currentTarget.checked
									});
								}}
							/>
						{/if}

						<MarkdownTokens
							id={`${id}-${tokenIdx}-${itemIdx}`}
							tokens={item.tokens}
							top={token.loose}
							{done}
							{save}
							{paragraphTag}
							{editCodeBlock}
							{topPadding}
							{links}
							{incremental}
							{onSave}
							{onTaskClick}
							{sourceIds}
							{onSourceClick}
							{openStates}
							{detailsScopeId}
							rootDetailsStateId={null}
						/>
					</li>
				{/each}
			</ol>
		{:else}
			<ul dir="auto" class="">
				{#each token.items as item, itemIdx}
					<li class="text-start {item?.task ? 'flex -translate-x-6.5 gap-3 ' : ''}">
						{#if item?.task}
							<input
								class=""
								type="checkbox"
								checked={item.checked}
								onchange={(e) => {
									onTaskClick({
										id: id,
										token: token,
										tokenIdx: tokenIdx,
										item: item,
										itemIdx: itemIdx,
										checked: e.currentTarget.checked
									});
								}}
							/>

							<div>
								<MarkdownTokens
									id={`${id}-${tokenIdx}-${itemIdx}`}
									tokens={item.tokens}
									top={token.loose}
									{done}
									{save}
									{paragraphTag}
									{editCodeBlock}
									{topPadding}
									{links}
									{incremental}
									{onSave}
									{onTaskClick}
									{sourceIds}
									{onSourceClick}
									{openStates}
									{detailsScopeId}
									rootDetailsStateId={null}
								/>
							</div>
						{:else}
							<MarkdownTokens
								id={`${id}-${tokenIdx}-${itemIdx}`}
								tokens={item.tokens}
								top={token.loose}
								{done}
								{save}
								{paragraphTag}
								{editCodeBlock}
								{topPadding}
								{links}
								{incremental}
								{onSave}
								{onTaskClick}
								{sourceIds}
								{onSourceClick}
								{openStates}
								{detailsScopeId}
								rootDetailsStateId={null}
							/>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	{:else if token.type === 'details'}
		{@const hasContent = (token.tokens?.length ?? 0) > 0}
		{@const openStateId =
			rootDetailsStateId ??
			detailsStateIds.get(tokenIdx) ??
			`${detailsScopeId}::details::${tokenIdx}`}
		<!-- token.attributes.done is baked into the HTML by the backend during streaming;
			 when cancelled, message-level done is true but the HTML still says done="false",
			 so override it here to stop the Collapsible spinner -->
		{@const attrs =
			done && token?.attributes?.done !== 'true'
				? { ...token?.attributes, done: 'true' }
				: token?.attributes}

		{#if attrs?.type === 'tool_calls'}
			<!-- Tool calls have dedicated handling with ToolCallDisplay component -->
			<ToolCallDisplay
				id={`${id}-${tokenIdx}-tc`}
				attributes={attrs}
				open={getOpenState(openStateId, false)}
				className="w-full space-y-1"
				onChange={(nextOpen: boolean) => setOpenState(openStateId, nextOpen)}
			/>
		{:else if attrs?.type === 'web_search'}
			<Collapsible
				title={token.summary}
				open={getOpenState(openStateId, false)}
				disabled={true}
				attributes={attrs}
				className="w-full space-y-1"
				onChange={(nextOpen: boolean) => setOpenState(openStateId, nextOpen)}
			/>
		{:else if hasContent}
			<Collapsible
				title={token.summary}
				open={getOpenState(openStateId, $settings?.expandDetails ?? false)}
				attributes={attrs}
				className="w-full space-y-1"
				onChange={(nextOpen: boolean) => setOpenState(openStateId, nextOpen)}
			>
				<div class=" mb-1.5" slot="content">
					<MarkdownTokens
						id={`${id}-${tokenIdx}-d`}
						tokens={token.tokens}
						{done}
						{save}
						{paragraphTag}
						{editCodeBlock}
						{topPadding}
						{links}
						{incremental}
						{onSave}
						{onTaskClick}
						{sourceIds}
						{onSourceClick}
						{openStates}
						detailsScopeId={openStateId}
						rootDetailsStateId={null}
					/>
				</div>
			</Collapsible>
		{:else}
			<Collapsible
				title={token.summary}
				open={getOpenState(openStateId, false)}
				disabled={true}
				attributes={attrs}
				className="w-full space-y-1"
				onChange={(nextOpen: boolean) => setOpenState(openStateId, nextOpen)}
			/>
		{/if}
	{:else if token.type === 'html'}
		<HtmlToken {token} />
	{:else if token.type === 'iframe'}
		<iframe
			src="{WEBUI_BASE_URL}/api/v1/files/{token.fileId}/content"
			title={token.fileId}
			width="100%"
			frameborder="0"
			onload={(e) => {
				const frame = e.currentTarget as HTMLIFrameElement;
				try {
					const bodyHeight = frame.contentWindow?.document.body.scrollHeight;

					if (typeof bodyHeight === 'number') {
						frame.style.height = `${bodyHeight + 20}px`;
					}
				} catch {}
			}}
		></iframe>
	{:else if token.type === 'paragraph'}
		{#if paragraphTag == 'span'}
			<span dir="auto">
				<MarkdownInlineTokens
					id={`${id}-${tokenIdx}-p`}
					source={token.text ?? ''}
					tokens={token.tokens ?? []}
					{done}
					{sourceIds}
					{onSourceClick}
					{links}
					{incremental}
				/>
			</span>
		{:else}
			<p dir="auto">
				<MarkdownInlineTokens
					id={`${id}-${tokenIdx}-p`}
					source={token.text ?? ''}
					tokens={token.tokens ?? []}
					{done}
					{sourceIds}
					{onSourceClick}
					{links}
					{incremental}
				/>
			</p>
		{/if}
	{:else if token.type === 'text'}
		{#if top}
			<p>
				{#if token.tokens}
					<MarkdownInlineTokens
						id={`${id}-${tokenIdx}-t`}
						source={token.text ?? ''}
						tokens={token.tokens}
						{done}
						{sourceIds}
						{onSourceClick}
						{links}
						{incremental}
					/>
				{:else}
					{unescapeHtml(token.text)}
				{/if}
			</p>
		{:else if token.tokens}
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-p`}
				source={token.text ?? ''}
				tokens={token.tokens ?? []}
				{done}
				{sourceIds}
				{onSourceClick}
				{links}
				{incremental}
			/>
		{:else}
			{unescapeHtml(token.text)}
		{/if}
	{:else if token.type === 'inlineKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={token?.displayMode ?? false} />
		{/if}
	{:else if token.type === 'blockKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={token?.displayMode ?? false} />
		{/if}
	{:else if token.type === 'space'}
		<div class="my-2"></div>
	{:else}
		{console.log('Unknown token', token)}
	{/if}
{/each}
