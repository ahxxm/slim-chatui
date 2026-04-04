const FENCE_OPENING_PATTERN = /^\s{0,3}(`{3,}|~{3,}).*$/;
const HTML_TAG_PATTERN = /<\/?[a-zA-Z][^>]*>/g;
const MARKDOWN_IMAGE_PATTERN = /!\[([^\]]*)\]\([^)]+\)/g;
const MARKDOWN_INLINE_LINK_PATTERN = /\[([^\]]+)\]\([^)]+\)/g;
const MARKDOWN_REFERENCE_LINK_PATTERN = /\[([^\]]+)\]\[[^\]]*\]/g;
const INLINE_CODE_PATTERN = /`([^`\n]+)`/g;
const STRONG_ASTERISK_PATTERN = /\*\*([^*\n]+)\*\*/g;
const STRONG_UNDERSCORE_PATTERN = /__([^_\n]+)__/g;
const STRIKETHROUGH_PATTERN = /~~([^~\n]+)~~/g;
const EMPHASIS_ASTERISK_PATTERN = /(^|[^\w*])\*([^*\n]+)\*(?=[^\w*]|$)/g;
const EMPHASIS_UNDERSCORE_PATTERN = /(^|[^\w_])_([^_\n]+)_(?=[^\w_]|$)/g;
const TABLE_SEPARATOR_PATTERN = /^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$/;

const stripFencedCodeBlocks = (markdown: string): string => {
	const visibleLines: string[] = [];
	const lines = markdown.split(/\r?\n/);
	let activeFenceCharacter: '`' | '~' | null = null;
	let activeFenceLength = 0;

	for (const line of lines) {
		const trimmedLine = line.trimStart();

		if (activeFenceCharacter) {
			const closingFencePattern = activeFenceCharacter === '`' ? /^`{3,}\s*$/ : /^~{3,}\s*$/;

			if (closingFencePattern.test(trimmedLine) && trimmedLine.trim().length >= activeFenceLength) {
				activeFenceCharacter = null;
				activeFenceLength = 0;
			}

			continue;
		}

		const openingFenceMatch = trimmedLine.match(FENCE_OPENING_PATTERN);
		if (openingFenceMatch) {
			activeFenceCharacter = openingFenceMatch[1][0] as '`' | '~';
			activeFenceLength = openingFenceMatch[1].length;
			continue;
		}

		visibleLines.push(line);
	}

	return visibleLines.join('\n');
};

const stripLineLevelMarkdown = (line: string): string => {
	let nextLine = line
		.replace(/^\s{0,3}#{1,6}\s+/, '')
		.replace(/^\s{0,3}>\s?/, '')
		.replace(/^\s*[-+*]\s+\[[ xX]\]\s+/, '')
		.replace(/^\s*[-+*]\s+/, '')
		.replace(/^\s*\d+\.\s+/, '');

	if (TABLE_SEPARATOR_PATTERN.test(nextLine)) {
		return ' ';
	}

	return nextLine;
};

export const toPreviewText = (content: unknown, limit = 320): string => {
	if (typeof content !== 'string') {
		return '';
	}

	return stripFencedCodeBlocks(content)
		.replace(/&gt;/g, '>')
		.replace(/&lt;/g, '<')
		.replace(/&amp;/g, '&')
		.replace(HTML_TAG_PATTERN, ' ')
		.replace(MARKDOWN_IMAGE_PATTERN, '$1')
		.replace(MARKDOWN_INLINE_LINK_PATTERN, '$1')
		.replace(MARKDOWN_REFERENCE_LINK_PATTERN, '$1')
		.replace(INLINE_CODE_PATTERN, '$1')
		.replace(STRONG_ASTERISK_PATTERN, '$1')
		.replace(STRONG_UNDERSCORE_PATTERN, '$1')
		.replace(STRIKETHROUGH_PATTERN, '$1')
		.replace(EMPHASIS_ASTERISK_PATTERN, '$1$2')
		.replace(EMPHASIS_UNDERSCORE_PATTERN, '$1$2')
		.split(/\r?\n/)
		.map(stripLineLevelMarkdown)
		.join(' ')
		.replace(/\s+/g, ' ')
		.trim()
		.slice(0, limit);
};
