import type { Links, Token, TokensList } from 'marked';

import { chatMarked } from './chat-marked';
import {
	getInlineMutableTokenStartIndex,
	getTokenRaw,
	isUnsafeInlineBoundary
} from './inline-boundary';

export type IncrementalTokenMode = 'block' | 'inline';

export interface IncrementalTokenSegment {
	id: string;
	tokens: Token[];
}

export interface IncrementalTokenState {
	mode: IncrementalTokenMode;
	frozenSegments: IncrementalTokenSegment[];
	mutableTailRaw: string;
	mutableSegment: IncrementalTokenSegment | null;
	links: Links;
	lastSource: string;
	nextSegmentId: number;
}

export type IncrementalTokenTransitionKind =
	| 'noop'
	| 'clear'
	| 'reset'
	| 'direct-append'
	| 'tail-lex';

interface IncrementalTokenUpdateOptions {
	seedLinks?: Links;
	onTransition?: (transition: IncrementalTokenTransitionKind) => void;
}

export const EMPTY_LINKS = Object.freeze(Object.create(null)) as Links;

export const createIncrementalTokenState = (
	mode: IncrementalTokenMode,
	options: IncrementalTokenUpdateOptions = {}
): IncrementalTokenState => ({
	mode,
	frozenSegments: [],
	mutableTailRaw: '',
	mutableSegment: null,
	links: options.seedLinks ?? EMPTY_LINKS,
	lastSource: '',
	nextSegmentId: 0
});

export const getRenderSegments = (state: IncrementalTokenState): IncrementalTokenSegment[] =>
	state.mutableSegment ? [...state.frozenSegments, state.mutableSegment] : state.frozenSegments;

export const updateIncrementalTokenState = (
	state: IncrementalTokenState,
	source: string,
	options: IncrementalTokenUpdateOptions = {}
): IncrementalTokenState => {
	const nextSource = source ?? '';
	const nextLinks = options.seedLinks ?? EMPTY_LINKS;
	const reset = () =>
		withTransition(resetIncrementalTokenState(state, nextSource, nextLinks), options, 'reset');

	if (state.mode === 'inline' && state.links !== nextLinks) {
		return reset();
	}

	if (state.lastSource === nextSource) {
		return withTransition(state, options, 'noop');
	}

	if (!nextSource) {
		return withTransition(
			clearIncrementalTokenState(
				state,
				nextSource,
				state.mode === 'inline' ? nextLinks : EMPTY_LINKS
			),
			options,
			'clear'
		);
	}

	if (!nextSource.startsWith(state.lastSource)) {
		return reset();
	}

	if (state.mode === 'block' && state.mutableSegment?.tokens[0]?.type === 'def') {
		return reset();
	}

	const delta = nextSource.slice(state.lastSource.length);

	if (!delta) {
		return withTransition(state, options, 'noop');
	}

	if (state.mode === 'inline' && shouldResetInlineStateForUnsafeBoundary(state)) {
		return reset();
	}

	if (state.mode === 'block' && canDirectAppendBlockToken(state, delta)) {
		return withTransition(
			extendMutableBlockToken(state, nextSource, delta),
			options,
			'direct-append'
		);
	}

	const nextMutableTailRaw = `${state.mutableTailRaw}${delta}`;
	const tailTokens =
		state.mode === 'block'
			? lexBlockTokens(nextMutableTailRaw, state.links)
			: lexInlineTokens(nextMutableTailRaw, nextLinks);

	if (state.mode === 'block' && hasDefinitionToken(tailTokens)) {
		return reset();
	}

	return withTransition(
		applyTailTokens(
			state,
			nextSource,
			tailTokens,
			state.mode === 'inline' ? nextLinks : state.links
		),
		options,
		'tail-lex'
	);
};

const withTransition = <State>(
	nextState: State,
	options: IncrementalTokenUpdateOptions,
	transition: IncrementalTokenTransitionKind
): State => {
	options.onTransition?.(transition);
	return nextState;
};

const withSegmentState = (
	state: IncrementalTokenState,
	source: string,
	links: Links,
	{
		frozenSegments = state.frozenSegments,
		mutableSegment = state.mutableSegment,
		nextSegmentId = state.nextSegmentId
	}: {
		frozenSegments?: IncrementalTokenSegment[];
		mutableSegment?: IncrementalTokenSegment | null;
		nextSegmentId?: number;
	}
): IncrementalTokenState => ({
	...state,
	frozenSegments,
	mutableTailRaw: mutableSegment ? joinTokenRaw(mutableSegment.tokens) : '',
	mutableSegment,
	links,
	lastSource: source,
	nextSegmentId
});

const resetIncrementalTokenState = (
	state: IncrementalTokenState,
	source: string,
	seedLinks: Links
): IncrementalTokenState => {
	if (!source) {
		return clearIncrementalTokenState(
			state,
			source,
			state.mode === 'inline' ? seedLinks : EMPTY_LINKS
		);
	}

	if (state.mode === 'block') {
		const tokens = lexBlockTokens(source);
		return buildResetState(state, source, tokens, tokens.links);
	}

	const tokens = lexInlineTokens(source, seedLinks);
	return buildResetState(state, source, tokens, seedLinks);
};

const buildResetState = (
	state: IncrementalTokenState,
	source: string,
	tokens: Token[],
	links: Links
): IncrementalTokenState => {
	if (state.mode === 'inline') {
		return buildResetInlineState(state, source, tokens, links);
	}

	let nextSegmentId = state.nextSegmentId;
	const nextSegments = tokens.map((token) => makeSegment(`segment-${nextSegmentId++}`, [token]));

	return withSegmentState(state, source, links, {
		frozenSegments: nextSegments.slice(0, -1),
		mutableSegment: nextSegments.at(-1) ?? null,
		nextSegmentId
	});
};

const clearIncrementalTokenState = (
	state: IncrementalTokenState,
	source: string,
	links: Links
): IncrementalTokenState =>
	withSegmentState(state, source, links, {
		frozenSegments: [],
		mutableSegment: null
	});

const applyTailTokens = (
	state: IncrementalTokenState,
	source: string,
	tailTokens: Token[],
	links: Links
): IncrementalTokenState => {
	if (state.mode === 'inline') {
		return applyInlineTailTokens(state, source, tailTokens, links);
	}

	let nextSegmentId = state.nextSegmentId;
	const nextFrozenSegments = state.frozenSegments.slice();

	if (tailTokens.length === 0) {
		return withSegmentState(state, source, links, {
			mutableSegment: null,
			nextSegmentId
		});
	}

	if (!state.mutableSegment) {
		const nextSegments = tailTokens.map((token) =>
			makeSegment(`segment-${nextSegmentId++}`, [token])
		);

		return withSegmentState(state, source, links, {
			frozenSegments: nextSegments.slice(0, -1),
			mutableSegment: nextSegments.at(-1) ?? null,
			nextSegmentId
		});
	}

	if (tailTokens.length === 1) {
		return withSegmentState(state, source, links, {
			mutableSegment: makeSegment(state.mutableSegment.id, [tailTokens[0]]),
			nextSegmentId
		});
	}

	nextFrozenSegments.push(makeSegment(state.mutableSegment.id, [tailTokens[0]]));

	for (const token of tailTokens.slice(1, -1)) {
		nextFrozenSegments.push(makeSegment(`segment-${nextSegmentId++}`, [token]));
	}

	const mutableSegment = makeSegment(`segment-${nextSegmentId++}`, [tailTokens.at(-1) as Token]);

	return withSegmentState(state, source, links, {
		frozenSegments: nextFrozenSegments,
		mutableSegment,
		nextSegmentId
	});
};

const canDirectAppendBlockToken = (state: IncrementalTokenState, delta: string): boolean => {
	if (!state.mutableSegment || /[\r\n]/.test(delta)) {
		return false;
	}

	const token = state.mutableSegment.tokens[0];

	return token?.type === 'paragraph' || token?.type === 'heading';
};

const extendMutableBlockToken = (
	state: IncrementalTokenState,
	source: string,
	delta: string
): IncrementalTokenState => {
	const currentMutableSegment = state.mutableSegment;
	const currentToken = currentMutableSegment?.tokens[0];

	if (!currentToken) {
		return state;
	}

	const raw = `${currentToken.raw ?? ''}${delta}`;
	const text = `${'text' in currentToken ? (currentToken.text ?? '') : ''}${delta}`;
	const nextToken = {
		...currentToken,
		raw,
		text
	} as Token;

	return {
		...state,
		mutableTailRaw: raw,
		mutableSegment: makeSegment(currentMutableSegment.id, [nextToken]),
		lastSource: source
	};
};

const hasDefinitionToken = (tokens: Token[]): boolean =>
	tokens.some((token) => token.type === 'def');

const shouldResetInlineStateForUnsafeBoundary = (state: IncrementalTokenState): boolean => {
	const previousToken = state.frozenSegments.at(-1)?.tokens.at(-1);
	const nextToken = state.mutableSegment?.tokens[0];

	return Boolean(previousToken && nextToken && isUnsafeInlineBoundary(previousToken, nextToken));
};

const buildResetInlineState = (
	state: IncrementalTokenState,
	source: string,
	tokens: Token[],
	links: Links
): IncrementalTokenState => {
	let nextSegmentId = state.nextSegmentId;
	const mutableTokenStartIndex = getInlineMutableTokenStartIndex(tokens);
	const frozenSegments = tokens
		.slice(0, mutableTokenStartIndex)
		.map((token) => makeSegment(`segment-${nextSegmentId++}`, [token]));
	const mutableTokens = tokens.slice(mutableTokenStartIndex);
	const mutableSegment = mutableTokens.length
		? makeSegment(`segment-${nextSegmentId++}`, mutableTokens)
		: null;

	return withSegmentState(state, source, links, {
		frozenSegments,
		mutableSegment,
		nextSegmentId
	});
};

const applyInlineTailTokens = (
	state: IncrementalTokenState,
	source: string,
	tailTokens: Token[],
	links: Links
): IncrementalTokenState => {
	let nextSegmentId = state.nextSegmentId;
	const nextFrozenSegments = state.frozenSegments.slice();

	if (tailTokens.length === 0) {
		return withSegmentState(state, source, links, {
			mutableSegment: null,
			nextSegmentId
		});
	}

	const mutableTokenStartIndex = getInlineMutableTokenStartIndex(tailTokens);

	for (const token of tailTokens.slice(0, mutableTokenStartIndex)) {
		nextFrozenSegments.push(makeSegment(`segment-${nextSegmentId++}`, [token]));
	}

	const mutableTokens = tailTokens.slice(mutableTokenStartIndex);
	const mutableSegmentId = state.mutableSegment?.id ?? `segment-${nextSegmentId++}`;

	return withSegmentState(state, source, links, {
		frozenSegments: nextFrozenSegments,
		mutableSegment: makeSegment(mutableSegmentId, mutableTokens),
		nextSegmentId
	});
};

const joinTokenRaw = (tokens: Token[]): string =>
	tokens.map((token) => getTokenRaw(token)).join('');

const makeSegment = (id: string, tokens: Token[]): IncrementalTokenSegment => ({ id, tokens });

const lexBlockTokens = (source: string, seedLinks?: Links): TokensList =>
	createLexer(seedLinks).lex(source);

const lexInlineTokens = (source: string, seedLinks?: Links): Token[] =>
	createLexer(seedLinks).inlineTokens(source);

const createLexer = (seedLinks?: Links) => {
	const lexer = new chatMarked.Lexer(chatMarked.defaults);
	lexer.tokens.links = Object.assign(Object.create(null) as Links, seedLinks);
	return lexer;
};
