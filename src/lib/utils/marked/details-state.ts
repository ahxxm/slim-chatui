import type { Token } from 'marked';

export interface DetailsIdentityToken extends Token {
	type: 'details';
	summary?: string;
	text?: string;
	attributes?: Record<string, string>;
}

const IDENTITY_ATTRIBUTE_KEYS = ['id', 'name', 'action', 'query', 'pattern', 'url'] as const;
const IDENTITY_TEXT_ATTRIBUTE_KEYS = ['arguments', 'files'] as const;
const PREVIEW_LIMIT = 120;

const normalizePreviewText = (value: string | null | undefined): string => {
	if (!value) {
		return '';
	}

	return value.replace(/\s+/g, ' ').trim().slice(0, PREVIEW_LIMIT);
};

const getStableDetailsTextPreview = (token: DetailsIdentityToken): string => {
	const lines = (token.text ?? '')
		.split(/\r?\n/)
		.map((line) => normalizePreviewText(line))
		.filter(Boolean);

	return lines[0] ?? '';
};

export const getDetailsIdentityBase = (token: Token | undefined): string | null => {
	if (!token || token.type !== 'details') {
		return null;
	}

	const detailsToken = token as DetailsIdentityToken;
	const attributes = detailsToken.attributes ?? {};
	const identityParts = [`type:${attributes.type ?? 'details'}`];

	for (const key of IDENTITY_ATTRIBUTE_KEYS) {
		const value = normalizePreviewText(attributes[key]);

		if (value) {
			identityParts.push(`${key}:${value}`);
		}
	}

	for (const key of IDENTITY_TEXT_ATTRIBUTE_KEYS) {
		const value = normalizePreviewText(attributes[key]);

		if (value) {
			identityParts.push(`${key}:${value}`);
		}
	}

	const textPreview = getStableDetailsTextPreview(detailsToken);

	if (textPreview) {
		identityParts.push(`text:${textPreview}`);
	}

	const summaryPreview = normalizePreviewText(detailsToken.summary);

	if (summaryPreview && identityParts.length === 1 && !textPreview) {
		identityParts.push(`summary:${summaryPreview}`);
	}

	return identityParts.join('|');
};

export const createIndexedDetailsStateIds = <T>(
	items: T[],
	getToken: (item: T) => Token | undefined,
	scopeId: string
): Map<number, string> => {
	const detailsStateIds = new Map<number, string>();
	const occurrenceCounts = new Map<string, number>();

	items.forEach((item, index) => {
		const identityBase = getDetailsIdentityBase(getToken(item));

		if (!identityBase) {
			return;
		}

		const occurrenceIndex = occurrenceCounts.get(identityBase) ?? 0;
		occurrenceCounts.set(identityBase, occurrenceIndex + 1);
		detailsStateIds.set(index, `${scopeId}::${identityBase}::${occurrenceIndex}`);
	});

	return detailsStateIds;
};
