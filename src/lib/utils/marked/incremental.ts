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
		return withTransition(
			resetIncrementalTokenState(state, nextSource, nextLinks),
			options,
			'reset'
		);
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
		return withTransition(
			resetIncrementalTokenState(state, nextSource, nextLinks),
			options,
			'reset'
		);
	}

	if (state.mode === 'block' && state.mutableSegment?.tokens[0]?.type === 'def') {
		return withTransition(
			resetIncrementalTokenState(state, nextSource, nextLinks),
			options,
			'reset'
		);
	}

	const delta = nextSource.slice(state.lastSource.length);

	if (!delta) {
		return withTransition(state, options, 'noop');
	}

	if (state.mode === 'inline' && shouldResetInlineStateForUnsafeBoundary(state)) {
		return withTransition(
			resetIncrementalTokenState(state, nextSource, nextLinks),
			options,
			'reset'
		);
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
		return withTransition(
			resetIncrementalTokenState(state, nextSource, nextLinks),
			options,
			'reset'
		);
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
	if (state.mode === 'inline') {
		return applyInlineTailTokens(state, source, tailTokens, links);
	}

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
	const text = `${'text' in currentToken ? (currentToken.text ?? '') : ''}${delta}`;
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

const hasDefinitionToken = (tokens: Token[]): boolean =>
	tokens.some((token) => token.type === 'def');

const shouldResetInlineStateForUnsafeBoundary = (state: IncrementalTokenState): boolean => {
	const previousToken = state.frozenSegments.at(-1)?.tokens.at(-1);
	const nextToken = state.mutableSegment?.tokens[0];

	if (!previousToken || !nextToken) {
		return false;
	}

	return isUnsafeInlineBoundary(previousToken, nextToken);
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
		.map((token) => createSegment(token, nextSegmentId++));
	const mutableTokens = tokens.slice(mutableTokenStartIndex);
	const mutableSegment = mutableTokens.length
		? createSegmentGroup(`segment-${nextSegmentId++}`, mutableTokens)
		: null;

	return {
		...state,
		frozenSegments,
		mutableTailRaw: joinTokenRaw(mutableTokens),
		mutableSegment,
		links,
		lastSource: source,
		nextSegmentId
	};
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
		return {
			...state,
			mutableTailRaw: '',
			mutableSegment: null,
			links,
			lastSource: source,
			nextSegmentId
		};
	}

	const mutableTokenStartIndex = getInlineMutableTokenStartIndex(tailTokens);

	for (const token of tailTokens.slice(0, mutableTokenStartIndex)) {
		nextFrozenSegments.push(createSegment(token, nextSegmentId++));
	}

	const mutableTokens = tailTokens.slice(mutableTokenStartIndex);
	const mutableSegmentId = state.mutableSegment?.id ?? `segment-${nextSegmentId++}`;

	return {
		...state,
		frozenSegments: nextFrozenSegments,
		mutableTailRaw: joinTokenRaw(mutableTokens),
		mutableSegment: createSegmentGroup(mutableSegmentId, mutableTokens),
		links,
		lastSource: source,
		nextSegmentId
	};
};

const getInlineMutableTokenStartIndex = (tokens: Token[]): number => {
	if (tokens.length === 0) {
		return 0;
	}

	const hasOpenBracketedInlineConstructByEndIndex: boolean[] = [];
	let openBracketedInlineConstructs: OpenBracketedInlineConstruct[] = [];

	for (const token of tokens) {
		openBracketedInlineConstructs = updateOpenBracketedInlineConstructs(
			openBracketedInlineConstructs,
			getInlineBoundaryTokenRaw(token)
		);
		hasOpenBracketedInlineConstructByEndIndex.push(openBracketedInlineConstructs.length > 0);
	}

	let startIndex = Math.max(0, tokens.length - 1);

	while (
		startIndex > 0 &&
		isUnsafeInlineBoundary(
			tokens[startIndex - 1],
			tokens[startIndex],
			hasOpenBracketedInlineConstructByEndIndex[startIndex - 1] ?? false
		)
	) {
		startIndex -= 1;
	}

	return startIndex;
};

const isUnsafeInlineBoundary = (
	previousToken: Token,
	nextToken: Token,
	hasOpenBracketedInlineConstructInPrefix = false
): boolean => {
	if (hasOpenBracketedInlineConstructInPrefix) {
		return true;
	}

	if (previousToken.type === 'br' || nextToken.type === 'br') {
		return true;
	}

	if (previousToken.type === 'text') {
		const previousRaw = getTokenRaw(previousToken);

		if (nextToken.type !== 'text' && textTokenContainsPotentialInlineOpener(previousRaw)) {
			return true;
		}

		if (nextToken.type === 'link' && /(?:!?\[[^\]\r\n]*\]\(|<)$/.test(previousRaw)) {
			return true;
		}

		if (
			(nextToken.type === 'em' || nextToken.type === 'strong' || nextToken.type === 'del') &&
			textTokenContainsPotentialInlineOpener(previousRaw)
		) {
			return true;
		}
	}

	if (previousToken.type === 'link' && nextToken.type === 'text') {
		const previousRaw = getTokenRaw(previousToken);
		const previousText = 'text' in previousToken ? (previousToken.text ?? '') : '';
		const previousHref = 'href' in previousToken ? (previousToken.href ?? '') : '';

		if (
			previousRaw === previousText &&
			previousRaw === previousHref &&
			/^[A-Za-z0-9._~:/?#[\]@!$&'()*+,;=%-]/.test(getTokenRaw(nextToken))
		) {
			return true;
		}
	}

	if (
		(previousToken.type === 'em' ||
			previousToken.type === 'strong' ||
			previousToken.type === 'del') &&
		nextToken.type === 'text'
	) {
		const expectedDelimiter = getInlineDelimiterTriggerPrefix(previousToken.raw ?? '');
		if (expectedDelimiter && getTokenRaw(nextToken).startsWith(expectedDelimiter)) {
			return true;
		}
	}

	return false;
};

type OpenBracketedInlineConstruct =
	| { state: 'label'; bracketDepth: number }
	| { state: 'after-label' }
	| { state: 'destination'; parenthesisDepth: number }
	| { state: 'reference'; bracketDepth: number };

const textTokenContainsPotentialInlineOpener = (raw: string): boolean =>
	/[*_~`$<\\\n]/.test(raw) ||
	/!\[[^\]\r\n]*$/.test(raw) ||
	/\[[^\]\r\n]*$/.test(raw) ||
	/\]\([^\)\r\n]*$/.test(raw);

const updateOpenBracketedInlineConstructs = (
	openConstructs: OpenBracketedInlineConstruct[],
	raw: string
): OpenBracketedInlineConstruct[] => {
	if (!raw) {
		return openConstructs;
	}

	const nextOpenConstructs = openConstructs.map((openConstruct) => ({ ...openConstruct }));
	let index = 0;

	while (index < raw.length) {
		if (raw[index] === '\\') {
			index += 2;
			continue;
		}

		const activeConstruct = nextOpenConstructs.at(-1);

		if (activeConstruct?.state === 'destination') {
			if (raw[index] === '(') {
				activeConstruct.parenthesisDepth += 1;
			} else if (raw[index] === ')') {
				activeConstruct.parenthesisDepth -= 1;
				if (activeConstruct.parenthesisDepth === 0) {
					nextOpenConstructs.pop();
				}
			}

			index += 1;
			continue;
		}

		if (activeConstruct?.state === 'reference') {
			if (raw[index] === '[') {
				activeConstruct.bracketDepth += 1;
			} else if (raw[index] === ']') {
				activeConstruct.bracketDepth -= 1;
				if (activeConstruct.bracketDepth === 0) {
					nextOpenConstructs.pop();
				}
			}

			index += 1;
			continue;
		}

		if (activeConstruct?.state === 'after-label') {
			if (raw[index] === '(') {
				nextOpenConstructs[nextOpenConstructs.length - 1] = {
					state: 'destination',
					parenthesisDepth: 1
				};
				index += 1;
				continue;
			}

			if (raw[index] === '[') {
				nextOpenConstructs[nextOpenConstructs.length - 1] = {
					state: 'reference',
					bracketDepth: 1
				};
				index += 1;
				continue;
			}

			nextOpenConstructs.pop();
			continue;
		}

		if (activeConstruct?.state === 'label') {
			if (raw[index] === '[') {
				activeConstruct.bracketDepth += 1;
			} else if (raw[index] === ']') {
				activeConstruct.bracketDepth -= 1;
				if (activeConstruct.bracketDepth === 0) {
					nextOpenConstructs[nextOpenConstructs.length - 1] = {
						state: 'after-label'
					};
				}
			}

			index += 1;
			continue;
		}

		if (raw[index] === '!' && raw[index + 1] === '[') {
			nextOpenConstructs.push({ state: 'label', bracketDepth: 1 });
			index += 2;
			continue;
		}

		if (raw[index] === '[') {
			nextOpenConstructs.push({ state: 'label', bracketDepth: 1 });
			index += 1;
			continue;
		}

		index += 1;
	}

	return nextOpenConstructs;
};

const getInlineDelimiterTriggerPrefix = (raw: string): string => {
	if (raw.startsWith('**') && raw.endsWith('**')) {
		return '*';
	}

	if (raw.startsWith('__') && raw.endsWith('__')) {
		return '_';
	}

	if (raw.startsWith('~~') && raw.endsWith('~~')) {
		return '~';
	}

	if (raw.startsWith('*') && raw.endsWith('*')) {
		return '*';
	}

	if (raw.startsWith('_') && raw.endsWith('_')) {
		return '_';
	}

	return '';
};

const joinTokenRaw = (tokens: Token[]): string =>
	tokens.map((token) => getTokenRaw(token)).join('');

const getInlineBoundaryTokenRaw = (token: Token): string => {
	if (token.type === 'link' || token.type === 'image' || token.type === 'citation') {
		return '';
	}

	return getTokenRaw(token);
};

const getTokenRaw = (token: Token): string => token.raw ?? '';

const createSegment = (token: Token, id: number): IncrementalTokenSegment => ({
	id: `segment-${id}`,
	tokens: [token]
});

const createSegmentGroup = (id: string, tokens: Token[]): IncrementalTokenSegment => ({
	id,
	tokens
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
