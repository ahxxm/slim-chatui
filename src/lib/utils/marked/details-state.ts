import type { Token } from 'marked';

export type DetailsIdentityToken = Token & {
	type: 'details';
	attributes?: Record<string, string>;
};

const IDENTITY_ATTRIBUTE_KEYS = [
	'id',
	'name',
	'action',
	'query',
	'pattern',
	'url'
] as const;
const PREVIEW_LIMIT = 120;

const normalizePreviewText = (value: string | null | undefined): string => {
	if (!value) {
		return '';
	}

	return value.replace(/\s+/g, ' ').trim().slice(0, PREVIEW_LIMIT);
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
