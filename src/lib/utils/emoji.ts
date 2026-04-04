import emojiShortCodesJson from '$lib/emoji-shortcodes.json';

export type EmojiShortCodeMap = Record<string, string | string[]>;

export const emojiShortCodes: EmojiShortCodeMap = emojiShortCodesJson;

export const shortCodeToCodePoint = Object.entries(emojiShortCodes).reduce<Record<string, string>>(
	(shortCodeMap, [codePoint, shortCodeValue]) => {
		if (typeof shortCodeValue === 'string') {
			shortCodeMap[shortCodeValue] = codePoint;
			return shortCodeMap;
		}

		for (const shortCode of shortCodeValue) {
			shortCodeMap[shortCode] = codePoint;
		}

		return shortCodeMap;
	},
	{}
);

export const codePointToEmoji = (hex: string): string =>
	String.fromCodePoint(...hex.split('-').map((codePoint) => parseInt(codePoint, 16)));

export const getEmojiForShortCode = (shortCode: string): string | null => {
	const codePoint = shortCodeToCodePoint[shortCode];
	return codePoint ? codePointToEmoji(codePoint) : null;
};
