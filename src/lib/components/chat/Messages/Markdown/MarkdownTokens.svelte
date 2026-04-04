<script lang="ts">
	import type { Links, Token } from 'marked';
	import { getContext, setContext } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';

	import { unescapeHtml } from '$lib/utils';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { settings } from '$lib/stores';
	import { EMPTY_LINKS } from '$lib/utils/marked/incremental';
	import { createIndexedDetailsStateIds } from '$lib/utils/marked/details-state';

	import CodeBlock from '$lib/components/chat/Messages/CodeBlock.svelte';
	import MarkdownInlineTokens from '$lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte';
	import MarkdownTokens from '$lib/components/chat/Messages/Markdown/MarkdownTokens.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import AlertRenderer, { alertComponent } from './AlertRenderer.svelte';
	import MarkdownDetailsBlock from './MarkdownDetailsBlock.svelte';
	import MarkdownTable from './MarkdownTable.svelte';

	import HtmlToken from './HTMLToken.svelte';
	import { markdownRenderContextKey, type MarkdownRenderContextState } from './context';

	type MarkdownToken = Token & Record<string, any>;
	const EMPTY_DETAILS_STATE_IDS = new Map<number, string>();

	interface MarkdownTokensProps {
		id: string;
		tokens?: MarkdownToken[];
		top?: boolean;
		sourceIds?: string[] | undefined;
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
		sourceIds = undefined,
		done = undefined,
		save = undefined,
		paragraphTag = undefined,
		editCodeBlock = undefined,
		topPadding = undefined,
		links = undefined,
		incremental = undefined,
		onSave = undefined,
		onTaskClick = undefined,
		onSourceClick = undefined,
		openStates = undefined,
		detailsScopeId = undefined,
		rootDetailsStateId = null
	}: MarkdownTokensProps = $props();

	const markdownRenderContext =
		getContext<MarkdownRenderContextState | null>(markdownRenderContextKey) ?? null;
	const fallbackOpenStates = new SvelteMap<string, boolean>();
	const localRenderContext = $state<MarkdownRenderContextState>({
		done: true,
		save: false,
		paragraphTag: 'p',
		editCodeBlock: true,
		topPadding: false,
		sourceIds: [],
		onSave: () => {},
		onTaskClick: () => {},
		onSourceClick: () => {},
		links: EMPTY_LINKS,
		openStates: fallbackOpenStates,
		incremental: false
	});

	setContext(markdownRenderContextKey, localRenderContext);

	let effectiveSourceIds = $derived(sourceIds ?? markdownRenderContext?.sourceIds ?? []);
	let effectiveDone = $derived(done ?? markdownRenderContext?.done ?? true);
	let effectiveSave = $derived(save ?? markdownRenderContext?.save ?? false);
	let effectiveParagraphTag = $derived(paragraphTag ?? markdownRenderContext?.paragraphTag ?? 'p');
	let effectiveEditCodeBlock = $derived(
		editCodeBlock ?? markdownRenderContext?.editCodeBlock ?? true
	);
	let effectiveTopPadding = $derived(topPadding ?? markdownRenderContext?.topPadding ?? false);
	let effectiveLinks = $derived(links ?? markdownRenderContext?.links ?? EMPTY_LINKS);
	let effectiveIncremental = $derived(incremental ?? markdownRenderContext?.incremental ?? false);
	let effectiveOnSave = $derived(onSave ?? markdownRenderContext?.onSave ?? (() => {}));
	let effectiveOnTaskClick = $derived(
		onTaskClick ?? markdownRenderContext?.onTaskClick ?? (() => {})
	);
	let effectiveOnSourceClick = $derived(
		onSourceClick ?? markdownRenderContext?.onSourceClick ?? (() => {})
	);
	let effectiveOpenStates = $derived(
		openStates ?? markdownRenderContext?.openStates ?? fallbackOpenStates
	);
	let effectiveDetailsScopeId = $derived(detailsScopeId ?? id);

	let detailsStateIds = $derived(
		tokens.some((token) => token.type === 'details')
			? createIndexedDetailsStateIds(tokens, (token) => token as Token, effectiveDetailsScopeId)
			: EMPTY_DETAILS_STATE_IDS
	);

	const headerComponent = (depth: number) => {
		return 'h' + depth;
	};

	$effect(() => {
		const nextRenderContext: MarkdownRenderContextState = {
			done: effectiveDone,
			save: effectiveSave,
			paragraphTag: effectiveParagraphTag,
			editCodeBlock: effectiveEditCodeBlock,
			topPadding: effectiveTopPadding,
			sourceIds: effectiveSourceIds,
			onSave: effectiveOnSave,
			onTaskClick: effectiveOnTaskClick,
			onSourceClick: effectiveOnSourceClick,
			links: effectiveLinks,
			openStates: effectiveOpenStates,
			incremental: effectiveIncremental
		};

		Object.assign(localRenderContext, nextRenderContext);
	});
</script>

{#each tokens as token, tokenIdx (tokenIdx)}
	{#if token.type === 'hr'}
		<hr class=" border-gray-100/30 dark:border-gray-850/30" />
	{:else if token.type === 'heading'}
		<svelte:element this={headerComponent(token.depth)} dir="auto">
			<MarkdownInlineTokens
				id={`${id}-${tokenIdx}-h`}
				source={token.text ?? ''}
				tokens={token.tokens}
			/>
		</svelte:element>
	{:else if token.type === 'code'}
		{#if token.raw.includes('```')}
			<CodeBlock
				id={`${id}-${tokenIdx}`}
				collapsed={$settings?.collapseCodeBlocks ?? false}
				done={effectiveDone}
				lang={token?.lang ?? ''}
				code={token?.text ?? ''}
				save={effectiveSave}
				edit={effectiveEditCodeBlock}
				stickyButtonsClassName={effectiveTopPadding ? 'top-10' : 'top-0'}
				onSave={(value: unknown) => {
					effectiveOnSave({
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
		<MarkdownTable id={`${id}-${tokenIdx}`} {token} />
	{:else if token.type === 'blockquote'}
		{@const alert = alertComponent(token)}
		{#if alert}
			<AlertRenderer {alert} />
		{:else}
			<blockquote dir="auto">
				<MarkdownTokens
					id={`${id}-${tokenIdx}`}
					tokens={token.tokens}
					detailsScopeId={effectiveDetailsScopeId}
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
									effectiveOnTaskClick({
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
							detailsScopeId={effectiveDetailsScopeId}
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
									effectiveOnTaskClick({
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
									detailsScopeId={effectiveDetailsScopeId}
									rootDetailsStateId={null}
								/>
							</div>
						{:else}
							<MarkdownTokens
								id={`${id}-${tokenIdx}-${itemIdx}`}
								tokens={item.tokens}
								top={token.loose}
								detailsScopeId={effectiveDetailsScopeId}
								rootDetailsStateId={null}
							/>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	{:else if token.type === 'details'}
		{@const openStateId =
			rootDetailsStateId ??
			detailsStateIds.get(tokenIdx) ??
			`${effectiveDetailsScopeId}::details::${tokenIdx}`}

		<MarkdownDetailsBlock
			id={`${id}-${tokenIdx}`}
			{openStateId}
			title={token.summary}
			attributes={token.attributes}
			hasContent={(token.tokens?.length ?? 0) > 0}
		>
			{#snippet content()}
				<div class="mb-1.5">
					<MarkdownTokens
						id={`${id}-${tokenIdx}-d`}
						tokens={token.tokens}
						detailsScopeId={openStateId}
						rootDetailsStateId={null}
					/>
				</div>
			{/snippet}
		</MarkdownDetailsBlock>
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
		{#if effectiveParagraphTag == 'span'}
			<span dir="auto">
				<MarkdownInlineTokens
					id={`${id}-${tokenIdx}-p`}
					source={token.text ?? ''}
					tokens={token.tokens ?? []}
				/>
			</span>
		{:else}
			<p dir="auto">
				<MarkdownInlineTokens
					id={`${id}-${tokenIdx}-p`}
					source={token.text ?? ''}
					tokens={token.tokens ?? []}
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
