import type { Token } from 'marked';

interface LinkLikeToken extends Token {
	text?: string | null;
	tokens?: Token[];
}

export const shouldRenderNestedLinkTokens = (token: LinkLikeToken): boolean => {
	const childTokens = token.tokens ?? [];

	if (childTokens.length === 0) {
		return false;
	}

	return !(
		childTokens.length === 1 &&
		childTokens[0].type === 'text' &&
		(childTokens[0] as LinkLikeToken).text === (token.text ?? '')
	);
};
