<script lang="ts">
	import type { Token } from 'marked';
	import { getContext } from 'svelte';

	import { unescapeHtml } from '$lib/utils';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { settings } from '$lib/stores';
	import { createIndexedDetailsStateIds } from '$lib/utils/marked/details-state';

	import CodeBlock from '$lib/components/chat/Messages/CodeBlock.svelte';
	import MarkdownInlineTokens from '$lib/components/chat/Messages/Markdown/MarkdownInlineTokens.svelte';
	import MarkdownTokens from '$lib/components/chat/Messages/Markdown/MarkdownTokens.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import AlertRenderer, { alertComponent } from './AlertRenderer.svelte';
	import MarkdownDetailsScope from './MarkdownDetailsScope.svelte';
	import MarkdownDetailsBlock from './MarkdownDetailsBlock.svelte';
	import MarkdownTable from './MarkdownTable.svelte';

	import HtmlToken from './HTMLToken.svelte';
	import {
		markdownDetailsScopeContextKey,
		markdownRenderContextKey,
		type MarkdownDetailsScopeState,
		type MarkdownRenderContextState
	} from './context';

	type MarkdownToken = Token & Record<string, any>;
	const EMPTY_DETAILS_STATE_IDS = new Map<number, string>();

	interface MarkdownTokensProps {
		id: string;
		tokens?: MarkdownToken[];
		top?: boolean;
		rootDetailsStateId?: string | null;
	}

	let { id, tokens = [], top = true, rootDetailsStateId = null }: MarkdownTokensProps = $props();

	const markdownRenderContext = getContext<MarkdownRenderContextState | null>(
		markdownRenderContextKey
	);
	const markdownDetailsScope = getContext<MarkdownDetailsScopeState | null>(
		markdownDetailsScopeContextKey
	);

	if (!markdownRenderContext) {
		throw new Error('MarkdownTokens requires markdown render context');
	}

	let renderDone = $derived(markdownRenderContext.done);

	let renderParagraphTag = $derived(markdownRenderContext.paragraphTag);

	let renderTopPadding = $derived(markdownRenderContext.topPadding);
	let renderOnTaskClick = $derived(markdownRenderContext.onTaskClick);
	let resolvedDetailsScopeId = $derived(markdownDetailsScope?.id ?? id);

	let detailsStateIds = $derived(
		tokens.some((token) => token.type === 'details')
			? createIndexedDetailsStateIds(tokens, (token) => token as Token, resolvedDetailsScopeId)
			: EMPTY_DETAILS_STATE_IDS
	);

	const headerComponent = (depth: number) => {
		return 'h' + depth;
	};
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
				done={renderDone}
				lang={token?.lang ?? ''}
				code={token?.text ?? ''}
				stickyButtonsClassName={renderTopPadding ? 'top-10' : 'top-0'}
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
				<MarkdownTokens id={`${id}-${tokenIdx}`} tokens={token.tokens} />
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
									renderOnTaskClick({
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
									renderOnTaskClick({
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
								/>
							</div>
						{:else}
							<MarkdownTokens
								id={`${id}-${tokenIdx}-${itemIdx}`}
								tokens={item.tokens}
								top={token.loose}
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
			`${resolvedDetailsScopeId}::details::${tokenIdx}`}

		<MarkdownDetailsBlock
			{openStateId}
			title={token.summary}
			attributes={token.attributes}
			hasContent={(token.tokens?.length ?? 0) > 0}
		>
			{#snippet content()}
				<MarkdownDetailsScope scopeId={openStateId}>
					{#snippet children()}
						<div class="mb-1.5">
							<MarkdownTokens id={`${id}-${tokenIdx}-d`} tokens={token.tokens} />
						</div>
					{/snippet}
				</MarkdownDetailsScope>
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
		{#if renderParagraphTag == 'span'}
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
