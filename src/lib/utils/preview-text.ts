import { decode } from 'html-entities';
import type { Token } from 'marked';

import { chatMarked } from './marked/chat-marked';

const HTML_TAG_PATTERN = /<\/?[a-zA-Z][^>]*>/g;

type PreviewToken = Token & Record<string, any>;

const normalizePreviewText = (value: unknown): string => {
	if (typeof value !== 'string' || value === '') {
		return '';
	}

	return decode(value).replace(HTML_TAG_PATTERN, ' ').replace(/\s+/g, ' ').trim();
};

const appendPreviewText = (parts: string[], value: unknown) => {
	const nextPart = normalizePreviewText(value);

	if (nextPart) {
		parts.push(nextPart);
	}
};

const appendTokensPreviewText = (parts: string[], tokens: PreviewToken[] | undefined) => {
	for (const token of tokens ?? []) {
		appendTokenPreviewText(parts, token);
	}
};

const appendTablePreviewText = (parts: string[], token: PreviewToken) => {
	for (const cell of token.header ?? []) {
		if (Array.isArray(cell.tokens) && cell.tokens.length > 0) {
			appendTokensPreviewText(parts, cell.tokens as PreviewToken[]);
		} else {
			appendPreviewText(parts, cell.text);
		}
	}

	for (const row of token.rows ?? []) {
		for (const cell of row ?? []) {
			if (Array.isArray(cell.tokens) && cell.tokens.length > 0) {
				appendTokensPreviewText(parts, cell.tokens as PreviewToken[]);
			} else {
				appendPreviewText(parts, cell.text);
			}
		}
	}
};

const appendTokenPreviewText = (parts: string[], token: PreviewToken) => {
	switch (token.type) {
		case 'code':
		case 'hr':
		case 'space':
			return;
		case 'br':
			parts.push(' ');
			return;
		case 'details':
			appendPreviewText(parts, token.summary);
			appendTokensPreviewText(parts, token.tokens as PreviewToken[] | undefined);
			return;
		case 'list':
			for (const item of token.items ?? []) {
				appendTokensPreviewText(parts, item.tokens as PreviewToken[] | undefined);
			}
			return;
		case 'table':
			appendTablePreviewText(parts, token);
			return;
		case 'html':
			appendPreviewText(parts, token.text ?? token.raw);
			return;
		case 'footnote':
			appendPreviewText(parts, token.escapedText ?? token.text ?? token.raw);
			return;
	}

	if (Array.isArray(token.tokens) && token.tokens.length > 0) {
		appendTokensPreviewText(parts, token.tokens as PreviewToken[]);
		return;
	}

	appendPreviewText(parts, token.text ?? token.raw);
};

export const toPreviewText = (content: unknown, limit = 320): string => {
	if (typeof content !== 'string') {
		return '';
	}

	const parts: string[] = [];

	try {
		appendTokensPreviewText(parts, chatMarked.lexer(content) as PreviewToken[]);
	} catch {
		appendPreviewText(parts, content);
	}

	return parts.join(' ').replace(/\s+/g, ' ').trim().slice(0, limit);
};
