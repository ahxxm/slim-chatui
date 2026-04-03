import type { Links, Token, TokensList } from 'marked';

import { chatMarked } from './chat-marked';

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

interface IncrementalTokenUpdateOptions {
	seedLinks?: Links;
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

export const getRenderSegments = (state: IncrementalTokenState): IncrementalTokenSegment[] => {
	if (!state.mutableSegment) {
		return state.frozenSegments;
	}

	return [...state.frozenSegments, state.mutableSegment];
};

export const updateIncrementalTokenState = (
	state: IncrementalTokenState,
	source: string,
	options: IncrementalTokenUpdateOptions = {}
): IncrementalTokenState => {
	const nextSource = source ?? '';
	const nextLinks = options.seedLinks ?? EMPTY_LINKS;

	if (state.mode === 'inline' && state.links !== nextLinks) {
		return resetIncrementalTokenState(state, nextSource, nextLinks);
	}

	if (state.lastSource === nextSource) {
		return state;
	}

	if (!nextSource) {
		return clearIncrementalTokenState(state, nextSource, state.mode === 'inline' ? nextLinks : EMPTY_LINKS);
	}

	if (!nextSource.startsWith(state.lastSource)) {
		return resetIncrementalTokenState(state, nextSource, nextLinks);
	}

	if (state.mode === 'block' && state.mutableSegment?.tokens[0]?.type === 'def') {
		return resetIncrementalTokenState(state, nextSource, nextLinks);
	}

	const delta = nextSource.slice(state.lastSource.length);

	if (!delta) {
		return state;
	}

	if (state.mode === 'inline' && shouldResetInlineStateForRetroactiveBoundaryChange(state)) {
		return resetIncrementalTokenState(state, nextSource, nextLinks);
	}

	if (state.mode === 'block' && canDirectAppendBlockToken(state, delta)) {
		return extendMutableBlockToken(state, nextSource, delta);
	}

	const nextMutableTailRaw = `${state.mutableTailRaw}${delta}`;
	const tailTokens =
		state.mode === 'block'
			? lexBlockTokens(nextMutableTailRaw, state.links)
			: lexInlineTokens(nextMutableTailRaw, nextLinks);

	if (state.mode === 'block' && hasDefinitionToken(tailTokens)) {
		return resetIncrementalTokenState(state, nextSource, nextLinks);
	}

	return applyTailTokens(
		state,
		nextSource,
		tailTokens,
		state.mode === 'inline' ? nextLinks : state.links
	);
};

const resetIncrementalTokenState = (
	state: IncrementalTokenState,
	source: string,
	seedLinks: Links
): IncrementalTokenState => {
	if (!source) {
		return clearIncrementalTokenState(state, source, state.mode === 'inline' ? seedLinks : EMPTY_LINKS);
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
	let nextSegmentId = state.nextSegmentId;
	const nextSegments = tokens.map((token) => createSegment(token, nextSegmentId++));

	return {
		...state,
		frozenSegments: nextSegments.slice(0, -1),
		mutableTailRaw: nextSegments.at(-1)?.tokens[0]?.raw ?? '',
		mutableSegment: nextSegments.at(-1) ?? null,
		links,
		lastSource: source,
		nextSegmentId
	};
};

const clearIncrementalTokenState = (
	state: IncrementalTokenState,
	source: string,
	links: Links
): IncrementalTokenState => ({
	...state,
	frozenSegments: [],
	mutableTailRaw: '',
	mutableSegment: null,
	links,
	lastSource: source
});

const applyTailTokens = (
	state: IncrementalTokenState,
	source: string,
	tailTokens: Token[],
	links: Links
): IncrementalTokenState => {
	let nextSegmentId = state.nextSegmentId;
	const nextFrozenSegments = state.frozenSegments.slice();

	if (tailTokens.length === 0) {
		return {
			...state,
			mutableTailRaw: '',
			mutableSegment: null,
			links,
			lastSource: source,
			nextSegmentId
		};
	}

	if (!state.mutableSegment) {
		const nextSegments = tailTokens.map((token) => createSegment(token, nextSegmentId++));

		return {
			...state,
			frozenSegments: nextSegments.slice(0, -1),
			mutableTailRaw: nextSegments.at(-1)?.tokens[0]?.raw ?? '',
			mutableSegment: nextSegments.at(-1) ?? null,
			links,
			lastSource: source,
			nextSegmentId
		};
	}

	if (tailTokens.length === 1) {
		const mutableSegment = createSegmentWithId(state.mutableSegment.id, tailTokens[0]);

		return {
			...state,
			mutableTailRaw: mutableSegment.tokens[0]?.raw ?? '',
			mutableSegment,
			links,
			lastSource: source,
			nextSegmentId
		};
	}

	nextFrozenSegments.push(createSegmentWithId(state.mutableSegment.id, tailTokens[0]));

	for (const token of tailTokens.slice(1, -1)) {
		nextFrozenSegments.push(createSegment(token, nextSegmentId++));
	}

	const mutableSegment = createSegment(tailTokens.at(-1) as Token, nextSegmentId++);

	return {
		...state,
		frozenSegments: nextFrozenSegments,
		mutableTailRaw: mutableSegment.tokens[0]?.raw ?? '',
		mutableSegment,
		links,
		lastSource: source,
		nextSegmentId
	};
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
	const text = `${'text' in currentToken ? currentToken.text ?? '' : ''}${delta}`;
	const nextToken = {
		...currentToken,
		raw,
		text
	} as Token;

	return {
		...state,
		mutableTailRaw: raw,
		mutableSegment: createSegmentWithId(currentMutableSegment.id, nextToken),
		lastSource: source
	};
};

const hasDefinitionToken = (tokens: Token[]): boolean => tokens.some((token) => token.type === 'def');

const shouldResetInlineStateForRetroactiveBoundaryChange = (
	state: IncrementalTokenState
): boolean => {
	const frozenTextToken = state.frozenSegments.at(-1)?.tokens[0] as
		| (Token & { text?: string; raw?: string })
		| undefined;
	const mutableLinkToken = state.mutableSegment?.tokens[0] as
		| (Token & { text?: string; raw?: string; href?: string })
		| undefined;

	if (frozenTextToken?.type !== 'text' || mutableLinkToken?.type !== 'link') {
		return false;
	}

	const raw = mutableLinkToken.raw ?? '';
	const text = mutableLinkToken.text ?? '';
	const href = mutableLinkToken.href ?? '';

	if (raw !== text || raw !== href) {
		return false;
	}

	const frozenText = frozenTextToken.text ?? frozenTextToken.raw ?? '';

	return /(?:!?\[[^\]\r\n]*\]\(|<)$/.test(frozenText);
};

const createSegment = (token: Token, id: number): IncrementalTokenSegment => ({
	id: `segment-${id}`,
	tokens: [token]
});

const createSegmentWithId = (id: string, token: Token): IncrementalTokenSegment => ({
	id,
	tokens: [token]
});

const lexBlockTokens = (source: string, seedLinks?: Links): TokensList => {
	const lexer = createLexer(seedLinks);
	return lexer.lex(source);
};

const lexInlineTokens = (source: string, seedLinks?: Links): Token[] => {
	const lexer = createLexer(seedLinks);
	return lexer.inlineTokens(source);
};

const createLexer = (seedLinks?: Links) => {
	const lexer = new chatMarked.Lexer(chatMarked.defaults);
	lexer.tokens.links = cloneLinks(seedLinks);
	return lexer;
};

const cloneLinks = (links?: Links): Links => {
	const nextLinks = Object.create(null) as Links;

	if (links) {
		Object.assign(nextLinks, links);
	}

	return nextLinks;
};
