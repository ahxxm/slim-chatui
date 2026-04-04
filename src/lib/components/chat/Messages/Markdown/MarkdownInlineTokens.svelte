<script lang="ts">
	import type { Token } from 'marked';
	import DOMPurify from 'dompurify';
	import { getContext } from 'svelte';
	import { goto } from '$app/navigation';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { unescapeHtml } from '$lib/utils';
	import {
		createIncrementalTokenState,
		getRenderSegments,
		updateIncrementalTokenState,
		type IncrementalTokenSegment
	} from '$lib/utils/marked/incremental';
	import { shouldRenderNestedLinkTokens } from '$lib/utils/marked/render';

	import Image from '$lib/components/common/Image.svelte';
	import KatexRenderer from './KatexRenderer.svelte';
	import HtmlToken from './HTMLToken.svelte';
	import MarkdownInlineTokens from './MarkdownInlineTokens.svelte';
	import TextToken from './MarkdownInlineTokens/TextToken.svelte';
	import CodespanToken from './MarkdownInlineTokens/CodespanToken.svelte';
	import SourceToken from './SourceToken.svelte';
	import { markdownRenderContextKey, type MarkdownRenderContextState } from './context';

	type InlineToken = Token & Record<string, any>;

	interface MarkdownInlineTokensProps {
		id: string;
		tokens?: InlineToken[];
		source?: string | null;
	}

	let { id, tokens = [], source = null }: MarkdownInlineTokensProps = $props();

	const markdownRenderContext = getContext<MarkdownRenderContextState | null>(
		markdownRenderContextKey
	);

	if (!markdownRenderContext) {
		throw new Error('MarkdownInlineTokens requires markdown render context');
	}

	let renderDone = $derived(markdownRenderContext.done);
	let renderSourceIds = $derived(markdownRenderContext.sourceIds);
	let renderOnSourceClick = $derived(markdownRenderContext.onSourceClick);
	let renderLinks = $derived(markdownRenderContext.links);

	function createStaticSegments(nextTokens: InlineToken[]): IncrementalTokenSegment[] {
		return nextTokens.map((token, tokenIdx) => ({
			id: `static-${tokenIdx}`,
			tokens: [token]
		}));
	}

	let inlineState = createIncrementalTokenState('inline');
	let currentInlineId = '';
	let renderSegments = $state<IncrementalTokenSegment[]>([]);

	$effect(() => {
		const nextId = id;
		const nextTokens = tokens ?? [];
		const nextLinks = renderLinks;
		const useIncremental = source !== null;

		if (!useIncremental) {
			currentInlineId = nextId;
			inlineState = createIncrementalTokenState('inline', { seedLinks: nextLinks });
			renderSegments = createStaticSegments(nextTokens);
			return;
		}

		if (nextId !== currentInlineId) {
			currentInlineId = nextId;
			inlineState = createIncrementalTokenState('inline', { seedLinks: nextLinks });
		}

		inlineState = updateIncrementalTokenState(inlineState, source ?? '', {
			seedLinks: nextLinks
		});
		renderSegments = getRenderSegments(inlineState);
	});

	/**
	 * Handle link clicks - intercept same-origin app URLs for in-app navigation
	 */
	const handleLinkClick = (e: MouseEvent, href: string) => {
		try {
			const url = new URL(href, window.location.origin);
			// Check if same origin and an in-app route
			if (url.origin === window.location.origin && url.pathname.startsWith('/c/')) {
				e.preventDefault();
				goto(url.pathname + url.search + url.hash);
			}
		} catch {
			// Invalid URL, let browser handle it
		}
	};
</script>

{#each renderSegments as segment (segment.id)}
	{#each segment.tokens as token, tokenIdx}
		{#if token.type === 'escape'}
			{unescapeHtml(token.text)}
		{:else if token.type === 'html'}
			<HtmlToken token={token as InlineToken} />
		{:else if token.type === 'link'}
			{@const plainLinkTextToken =
				token.tokens?.length === 1 && token.tokens[0].type === 'text' ? token.tokens[0] : null}
			{#if shouldRenderNestedLinkTokens(token)}
				<a
					href={token.href}
					target="_blank"
					rel="nofollow"
					title={token.title}
					onclick={(e) => handleLinkClick(e, token.href)}
				>
					<MarkdownInlineTokens
						id={`${id}-${segment.id}-${tokenIdx}-a`}
						source={token.text ?? ''}
						tokens={token.tokens}
					/>
				</a>
			{:else if plainLinkTextToken}
				<a
					href={token.href}
					target="_blank"
					rel="nofollow"
					title={token.title}
					onclick={(e) => handleLinkClick(e, token.href)}
				>
					<TextToken token={plainLinkTextToken} done={renderDone} />
				</a>
			{:else}
				<a
					href={token.href}
					target="_blank"
					rel="nofollow"
					title={token.title}
					onclick={(e) => handleLinkClick(e, token.href)}>{token.text}</a
				>
			{/if}
		{:else if token.type === 'image'}
			<Image src={token.href} alt={token.text} />
		{:else if token.type === 'strong'}
			<strong>
				<MarkdownInlineTokens
					id={`${id}-${segment.id}-${tokenIdx}-strong`}
					source={token.text ?? ''}
					tokens={token.tokens}
				/>
			</strong>
		{:else if token.type === 'em'}
			<em>
				<MarkdownInlineTokens
					id={`${id}-${segment.id}-${tokenIdx}-em`}
					source={token.text ?? ''}
					tokens={token.tokens}
				/>
			</em>
		{:else if token.type === 'codespan'}
			<CodespanToken token={token as InlineToken} done={renderDone} />
		{:else if token.type === 'br'}
			<br />
		{:else if token.type === 'del'}
			<del>
				<MarkdownInlineTokens
					id={`${id}-${segment.id}-${tokenIdx}-del`}
					source={token.text ?? ''}
					tokens={token.tokens}
				/>
			</del>
		{:else if token.type === 'inlineKatex'}
			{#if token.text}
				<KatexRenderer content={token.text} displayMode={false} />
			{/if}
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
		{:else if token.type === 'footnote'}
			{@html DOMPurify.sanitize(
				`<sup class="footnote-ref footnote-ref-text">${token.escapedText}</sup>`
			) || ''}
		{:else if token.type === 'citation'}
			{#if renderSourceIds.length > 0}
				<SourceToken
					token={token as InlineToken}
					sourceIds={renderSourceIds}
					onClick={renderOnSourceClick}
				/>
			{:else}
				<TextToken token={token as InlineToken} done={renderDone} />
			{/if}
		{:else if token.type === 'text'}
			<TextToken token={token as InlineToken} done={renderDone} />
		{/if}
	{/each}
{/each}
