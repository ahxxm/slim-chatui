import { v4 as uuidv4 } from 'uuid';
import { WEBUI_BASE_URL } from '$lib/constants';

import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import isToday from 'dayjs/plugin/isToday';
import isYesterday from 'dayjs/plugin/isYesterday';
import localizedFormat from 'dayjs/plugin/localizedFormat';

dayjs.extend(relativeTime);
dayjs.extend(isToday);
dayjs.extend(isYesterday);
dayjs.extend(localizedFormat);

//////////////////////////
// Helper functions
//////////////////////////

export const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const formatNumber = (num: number): string => {
	return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(
		num
	);
};

function escapeRegExp(string: string): string {
	return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Replace tokens outside code blocks only
export const replaceOutsideCode = (content: string, replacer: (str: string) => string) => {
	return content
		.split(/(```[\s\S]*?```|`[\s\S]*?`)/)
		.map((segment) => {
			return segment.startsWith('```') || segment.startsWith('`') ? segment : replacer(segment);
		})
		.join('');
};

export const replaceTokens = (content: string, char: string, user: string) => {
	const tokens = [
		{ regex: /{{char}}/gi, replacement: char },
		{ regex: /{{user}}/gi, replacement: user },
		{
			regex: /{{VIDEO_FILE_ID_([a-f0-9-]+)}}/gi,
			replacement: (_: string, fileId: string) =>
				`<video src="${WEBUI_BASE_URL}/api/v1/files/${fileId}/content" controls></video>`
		},
		{
			regex: /{{HTML_FILE_ID_([a-f0-9-]+)}}/gi,
			replacement: (_: string, fileId: string) => `<file type="html" id="${fileId}" />`
		}
	];

	// Apply replacements
	content = replaceOutsideCode(content, (segment) => {
		tokens.forEach(({ regex, replacement }) => {
			if (replacement !== undefined && replacement !== null) {
				segment = segment.replace(regex, replacement);
			}
		});

		return segment;
	});

	return content;
};

export const sanitizeResponseContent = (content: string) => {
	return content
		.replace(/<\|[a-z]*$/, '')
		.replace(/<\|[a-z]+\|$/, '')
		.replace(/<$/, '')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;')
		.replaceAll(/<\|[a-z]+\|>/g, ' ')
		.trim();
};

export const processResponseContent = (content: string) => {
	content = processChineseContent(content);
	return content.trim();
};

function isChineseChar(char: string): boolean {
	return /\p{Script=Han}/u.test(char);
}

// Tackle "Model output issue not following the standard Markdown/LaTeX format" in Chinese.
function processChineseContent(content: string): string {
	// This function is used to process the response content before the response content is rendered.
	const lines = content.split('\n');
	const processedLines = lines.map((line) => {
		if (/[\u4e00-\u9fa5]/.test(line)) {
			// Problems caused by Chinese parentheses
			/* Discription:
			 *   When `*` has Chinese delimiters on the inside, markdown parser ignore bold or italic style.
			 *   - e.g. `**中文名（English）**中文内容` will be parsed directly,
			 *          instead of `<strong>中文名（English）</strong>中文内容`.
			 * Solution:
			 *   Adding a `space` before and after the bold/italic part can solve the problem.
			 *   - e.g. `**中文名（English）**中文内容` -> ` **中文名（English）** 中文内容`
			 * Note:
			 *   Similar problem was found with English parentheses and other full delimiters,
			 *   but they are not handled here because they are less likely to appear in LLM output.
			 *   Change the behavior in future if needed.
			 */
			if (line.includes('*')) {
				// Handle **bold** and *italic*
				// 1. With Chinese parentheses
				if (/（|）/.test(line)) {
					line = processChineseDelimiters(line, '**', '（', '）');
					line = processChineseDelimiters(line, '*', '（', '）');
				}
				// 2. With Chinese quotations
				if (/“|”/.test(line)) {
					line = processChineseDelimiters(line, '**', '“', '”');
					line = processChineseDelimiters(line, '*', '“', '”');
				}
			}
		}
		return line;
	});
	content = processedLines.join('\n');

	return content;
}

// Helper function for `processChineseContent`
function processChineseDelimiters(
	line: string,
	symbol: string,
	leftSymbol: string,
	rightSymbol: string
): string {
	// NOTE: If needed, with a little modification, this function can be applied to more cases.
	const escapedSymbol = escapeRegExp(symbol);
	const regex = new RegExp(
		`(.?)(?<!${escapedSymbol})(${escapedSymbol})([^${escapedSymbol}]+)(${escapedSymbol})(?!${escapedSymbol})(.)`,
		'g'
	);
	return line.replace(regex, (match, l, left, content, right, r) => {
		const result =
			(content.startsWith(leftSymbol) && l && l.length > 0 && isChineseChar(l[l.length - 1])) ||
			(content.endsWith(rightSymbol) && r && r.length > 0 && isChineseChar(r[0]));

		if (result) {
			return `${l} ${left}${content}${right} ${r}`;
		} else {
			return match;
		}
	});
}

export function unescapeHtml(html: string) {
	const doc = new DOMParser().parseFromString(html, 'text/html');
	return doc.documentElement.textContent;
}

export const capitalizeFirstLetter = (string: string) => {
	return string.charAt(0).toUpperCase() + string.slice(1);
};

export const splitStream = (splitOn: string) => {
	let buffer = '';
	return new TransformStream({
		transform(chunk, controller) {
			buffer += chunk;
			const parts = buffer.split(splitOn);
			parts.slice(0, -1).forEach((part) => controller.enqueue(part));
			buffer = parts[parts.length - 1];
		},
		flush(controller) {
			if (buffer) controller.enqueue(buffer);
		}
	});
};

export const convertMessagesToHistory = (messages: any[]) => {
	const history: { messages: Record<string, any>; currentId: string | null } = {
		messages: {},
		currentId: null
	};

	let parentMessageId: string | null = null;
	let messageId: string | null = null;

	for (const message of messages) {
		messageId = uuidv4();

		if (parentMessageId !== null) {
			history.messages[parentMessageId].childrenIds = [
				...history.messages[parentMessageId].childrenIds,
				messageId
			];
		}

		history.messages[messageId] = {
			...message,
			id: messageId,
			parentId: parentMessageId,
			childrenIds: []
		};

		parentMessageId = messageId;
	}

	history.currentId = messageId;
	return history;
};

export const compressImage = async (imageUrl: string, maxWidth: number, maxHeight: number) => {
	return new Promise((resolve, reject) => {
		const img = new Image();
		img.onload = () => {
			const canvas = document.createElement('canvas');
			let width = img.width;
			let height = img.height;

			// Maintain aspect ratio while resizing

			if (maxWidth && maxHeight) {
				// Resize with both dimensions defined (preserves aspect ratio)

				if (width <= maxWidth && height <= maxHeight) {
					resolve(imageUrl);
					return;
				}

				if (width / height > maxWidth / maxHeight) {
					height = Math.round((maxWidth * height) / width);
					width = maxWidth;
				} else {
					width = Math.round((maxHeight * width) / height);
					height = maxHeight;
				}
			} else if (maxWidth) {
				// Only maxWidth defined

				if (width <= maxWidth) {
					resolve(imageUrl);
					return;
				}

				height = Math.round((maxWidth * height) / width);
				width = maxWidth;
			} else if (maxHeight) {
				// Only maxHeight defined

				if (height <= maxHeight) {
					resolve(imageUrl);
					return;
				}

				width = Math.round((maxHeight * width) / height);
				height = maxHeight;
			}

			canvas.width = width;
			canvas.height = height;

			const context = canvas.getContext('2d');
			if (!context) return reject(new Error('Canvas 2d context unavailable'));
			context.drawImage(img, 0, 0, width, height);

			// Get compressed image URL
			const mimeType = imageUrl.match(/^data:([^;]+);/)?.[1];
			const compressedUrl = canvas.toDataURL(mimeType);
			resolve(compressedUrl);
		};
		img.onerror = (error) => reject(error);
		img.src = imageUrl;
	});
};
export const formatDate = (inputDate: string | number | Date) => {
	const date = dayjs(inputDate);

	if (date.isToday()) {
		return `Today at {{LOCALIZED_TIME}}`;
	} else if (date.isYesterday()) {
		return `Yesterday at {{LOCALIZED_TIME}}`;
	} else {
		return `{{LOCALIZED_DATE}} at {{LOCALIZED_TIME}}`;
	}
};

export const copyToClipboard = async (
	text: string,
	html: string | null = null,
	formatted = false
) => {
	if (formatted) {
		let styledHtml = '';
		if (!html) {
			const [
				{ Marked },
				{ default: markedKatexExtension },
				{ default: markedExtension },
				{ default: hljs }
			] = await Promise.all([
				import('marked'),
				import('$lib/utils/marked/katex-extension'),
				import('$lib/utils/marked/extension'),
				import('highlight.js')
			]);

			const clipboardMarked = new Marked();
			clipboardMarked.use(markedKatexExtension({ throwOnError: false }));
			clipboardMarked.use(markedExtension({ throwOnError: false }));
			clipboardMarked.use({
				renderer: {
					code({ text, lang }) {
						const language = hljs.getLanguage(lang) ? lang : 'plaintext';
						return `<pre><code class="hljs language-${language}">${hljs.highlight(text, { language }).value}</code></pre>`;
					}
				}
			});

			const htmlContent = clipboardMarked.parse(text);

			// Add basic styling to make the content look better when pasted
			styledHtml = `
			<div>
				<style>
					pre {
						background-color: #f6f8fa;
						border-radius: 6px;
						padding: 16px;
						overflow: auto;
					}
					code {
						font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
						font-size: 14px;
					}
					.hljs-keyword { color: #d73a49; }
					.hljs-string { color: #032f62; }
					.hljs-comment { color: #6a737d; }
					.hljs-function { color: #6f42c1; }
					.hljs-number { color: #005cc5; }
					.hljs-operator { color: #d73a49; }
					.hljs-class { color: #6f42c1; }
					.hljs-title { color: #6f42c1; }
					.hljs-params { color: #24292e; }
					.hljs-built_in { color: #005cc5; }
					blockquote {
						border-left: 4px solid #dfe2e5;
						padding-left: 16px;
						color: #6a737d;
						margin-left: 0;
						margin-right: 0;
					}
					table {
						border-collapse: collapse;
						width: 100%;
						margin-bottom: 16px;
					}
					table, th, td {
						border: 1px solid #dfe2e5;
					}
					th, td {
						padding: 8px 12px;
					}
					th {
						background-color: #f6f8fa;
					}
				</style>
				${htmlContent}
			</div>
		`;
		} else {
			// If HTML is provided, use it directly
			styledHtml = html;
		}

		// Create a blob with HTML content
		const blob = new Blob([styledHtml], { type: 'text/html' });

		try {
			// Create a ClipboardItem with HTML content
			const data = new ClipboardItem({
				'text/html': blob,
				'text/plain': new Blob([text], { type: 'text/plain' })
			});

			// Write to clipboard
			await navigator.clipboard.write([data]);
			return true;
		} catch (err) {
			console.error('Error copying formatted content:', err);
			// Fallback to plain text
			return await copyToClipboard(text);
		}
	} else {
		let result = false;
		if (!navigator.clipboard) {
			const textArea = document.createElement('textarea');
			textArea.value = text;

			// Avoid scrolling to bottom
			textArea.style.top = '0';
			textArea.style.left = '0';
			textArea.style.position = 'fixed';

			document.body.appendChild(textArea);
			textArea.focus();
			textArea.select();

			try {
				const successful = document.execCommand('copy');
				const msg = successful ? 'successful' : 'unsuccessful';
				console.log('Fallback: Copying text command was ' + msg);
				result = true;
			} catch (err) {
				console.error('Fallback: Oops, unable to copy', err);
			}

			document.body.removeChild(textArea);
			return result;
		}

		result = await navigator.clipboard
			.writeText(text)
			.then(() => {
				console.log('Async: Copying to clipboard was successful!');
				return true;
			})
			.catch((error) => {
				console.error('Async: Could not copy text: ', error);
				return false;
			});

		return result;
	}
};

export const compareVersion = (latest: string, current: string) => {
	return current === '0.0.0'
		? false
		: current.localeCompare(latest, undefined, {
				numeric: true,
				sensitivity: 'case',
				caseFirst: 'upper'
			}) < 0;
};

export const removeFirstHashWord = (inputString: string) => {
	// Split the string into an array of words
	const words = inputString.split(' ');

	// Find the index of the first word that starts with #
	const index = words.findIndex((word) => word.startsWith('#'));

	// Remove the first word with #
	if (index !== -1) {
		words.splice(index, 1);
	}

	// Join the remaining words back into a string
	const resultString = words.join(' ');

	return resultString;
};

export const transformFileName = (fileName: string) => {
	// Convert to lowercase
	const lowerCaseFileName = fileName.toLowerCase();

	// Remove special characters using regular expression
	const sanitizedFileName = lowerCaseFileName.replace(/[^\w\s]/g, '');

	// Replace spaces with dashes
	const finalFileName = sanitizedFileName.replace(/\s+/g, '-');

	return finalFileName;
};

export const calculateSHA256 = async (file: File) => {
	// Create a FileReader to read the file asynchronously
	const reader = new FileReader();

	// Define a promise to handle the file reading
	const readFile = new Promise<ArrayBuffer>((resolve, reject) => {
		reader.onload = () => {
			if (reader.result instanceof ArrayBuffer) resolve(reader.result);
			else reject(new Error('Expected ArrayBuffer from FileReader'));
		};
		reader.onerror = reject;
	});

	// Read the file as an ArrayBuffer
	reader.readAsArrayBuffer(file);

	try {
		// Wait for the FileReader to finish reading the file
		const buffer = await readFile;

		// Convert the ArrayBuffer to a Uint8Array
		const uint8Array = new Uint8Array(buffer);

		// Calculate the SHA-256 hash using Web Crypto API
		const hashBuffer = await crypto.subtle.digest('SHA-256', uint8Array);

		// Convert the hash to a hexadecimal string
		const hashArray = Array.from(new Uint8Array(hashBuffer));
		const hashHex = hashArray.map((byte) => byte.toString(16).padStart(2, '0')).join('');

		return `${hashHex}`;
	} catch (error) {
		console.error('Error calculating SHA-256 hash:', error);
		throw error;
	}
};

export const getImportOrigin = (_chats: any[]) => {
	// Check what external service chat imports are from
	if ('mapping' in _chats[0]) {
		return 'openai';
	}
	return 'webui';
};

const convertOpenAIMessages = (convo: any) => {
	// Parse OpenAI chat messages and create chat dictionary for creating new chats
	const mapping = convo['mapping'];
	const messages = [];
	let currentId = '';
	let lastId = null;

	for (const message_id in mapping) {
		const message = mapping[message_id];
		currentId = message_id;
		try {
			if (
				messages.length == 0 &&
				(message['message'] == null ||
					(message['message']['content']['parts']?.[0] == '' &&
						message['message']['content']['text'] == null))
			) {
				// Skip chat messages with no content
				continue;
			} else {
				const new_chat = {
					id: message_id,
					parentId: lastId,
					childrenIds: message['children'] || [],
					role: message['message']?.['author']?.['role'] !== 'user' ? 'assistant' : 'user',
					content:
						message['message']?.['content']?.['parts']?.[0] ||
						message['message']?.['content']?.['text'] ||
						'',
					model: 'gpt-3.5-turbo',
					done: true,
					context: null
				};
				messages.push(new_chat);
				lastId = currentId;
			}
		} catch (error) {
			console.log('Error with', message, '\nError:', error);
		}
	}

	const history: Record<PropertyKey, (typeof messages)[number]> = {};
	messages.forEach((obj) => (history[obj.id] = obj));

	const chat = {
		history: {
			currentId: currentId,
			messages: history // Need to convert this to not a list and instead a json object
		},
		models: ['gpt-3.5-turbo'],
		messages: messages,
		options: {},
		timestamp: convo['create_time'],
		title: convo['title'] ?? 'New Chat'
	};
	return chat;
};

const validateChat = (chat: any) => {
	// Because ChatGPT sometimes has features we can't use like DALL-E or might have corrupted messages, need to validate
	const messages = chat.messages;

	// Check if messages array is empty
	if (messages.length === 0) {
		return false;
	}

	// Last message's children should be an empty array
	const lastMessage = messages[messages.length - 1];
	if (lastMessage.childrenIds.length !== 0) {
		return false;
	}

	// First message's parent should be null
	const firstMessage = messages[0];
	if (firstMessage.parentId !== null) {
		return false;
	}

	// Every message's content should be a string
	for (const message of messages) {
		if (typeof message.content !== 'string') {
			return false;
		}
	}

	return true;
};

export const convertOpenAIChats = (_chats: any[]) => {
	// Create a list of dictionaries with each conversation from import
	const chats = [];
	let failed = 0;
	for (const convo of _chats) {
		const chat = convertOpenAIMessages(convo);

		if (validateChat(chat)) {
			chats.push({
				id: convo['id'],
				user_id: '',
				title: convo['title'],
				chat: chat,
				timestamp: convo['create_time']
			});
		} else {
			failed++;
		}
	}
	console.log(failed, 'Conversations could not be imported');
	return chats;
};

export const isValidHttpUrl = (string: string) => {
	let url;

	try {
		url = new URL(string);
	} catch (_) {
		return false;
	}

	return url.protocol === 'http:' || url.protocol === 'https:';
};

export const isYoutubeUrl = (url: string) => {
	return (
		url.startsWith('https://www.youtube.com') ||
		url.startsWith('https://youtu.be') ||
		url.startsWith('https://youtube.com') ||
		url.startsWith('https://m.youtube.com')
	);
};

export const removeEmojis = (str: string) => {
	// Regular expression to match emojis
	const emojiRegex = /[\uD800-\uDBFF][\uDC00-\uDFFF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDE4F]/g;

	// Replace emojis with an empty string
	return str.replace(emojiRegex, '');
};

export const removeFormattings = (str: string) => {
	return (
		str
			// Block elements (remove completely)
			.replace(/(```[\s\S]*?```)/g, '') // Code blocks
			.replace(/^\|.*\|$/gm, '') // Tables
			// Inline elements (preserve content)
			.replace(/(?:\*\*|__)(.*?)(?:\*\*|__)/g, '$1') // Bold
			.replace(/(?:[*_])(.*?)(?:[*_])/g, '$1') // Italic
			.replace(/~~(.*?)~~/g, '$1') // Strikethrough
			.replace(/`([^`]+)`/g, '$1') // Inline code

			// Links and images
			.replace(/!?\[([^\]]*)\](?:\([^)]+\)|\[[^\]]*\])/g, '$1') // Links & images
			.replace(/^\[[^\]]+\]:\s*.*$/gm, '') // Reference definitions

			// Block formatting
			.replace(/^#{1,6}\s+/gm, '') // Headers
			.replace(/^\s*[-*+]\s+/gm, '') // Lists
			.replace(/^\s*(?:\d+\.)\s+/gm, '') // Numbered lists
			.replace(/^\s*>[> ]*/gm, '') // Blockquotes
			.replace(/^\s*:\s+/gm, '') // Definition lists

			// Cleanup
			.replace(/\[\^[^\]]*\]/g, '') // Footnotes
			.replace(/\n{2,}/g, '\n')
	); // Multiple newlines
};

export const removeDetails = (content: string, types: string[]) => {
	return replaceOutsideCode(content, (segment) => {
		for (const type of types) {
			segment = segment.replace(
				new RegExp(`<details\\s+type="${type}"[^>]*>.*?<\\/details>`, 'gis'),
				''
			);
		}
		return segment;
	});
};

export const removeAllDetails = (content: string) => {
	return replaceOutsideCode(content, (segment) => {
		return segment.replace(/<details[^>]*>.*?<\/details>/gis, '');
	});
};

export const processDetails = (content: string) => {
	content = removeDetails(content, ['reasoning', 'web_search']);

	// This regex matches <details> tags with type="tool_calls" and captures their attributes to convert them to a string
	const detailsRegex = /<details\s+type="tool_calls"([^>]*)>([\s\S]*?)<\/details>/gis;
	const matches = content.match(detailsRegex);
	if (matches) {
		for (const match of matches) {
			const attributesRegex = /(\w+)="([^"]*)"/g;
			const attributes: Record<string, string> = {};
			let attributeMatch;
			while ((attributeMatch = attributesRegex.exec(match)) !== null) {
				attributes[attributeMatch[1]] = attributeMatch[2];
			}

			if (attributes.result) {
				content = content.replace(match, unescapeHtml(attributes.result));
			}
		}
	}

	return content;
};

export const blobToFile = (blob: Blob, fileName: string) => {
	// Create a new File object from the Blob
	const file = new File([blob], fileName, { type: blob.type });
	return file;
};

export const approximateToHumanReadable = (nanoseconds: number) => {
	const seconds = Math.floor((nanoseconds / 1e9) % 60);
	const minutes = Math.floor((nanoseconds / 6e10) % 60);
	const hours = Math.floor((nanoseconds / 3.6e12) % 24);

	const results: string[] = [];

	if (seconds >= 0) {
		results.push(`${seconds}s`);
	}

	if (minutes > 0) {
		results.push(`${minutes}m`);
	}

	if (hours > 0) {
		results.push(`${hours}h`);
	}

	return results.reverse().join(' ');
};

export const getTimeRange = (timestamp: number) => {
	const now = new Date();
	const date = new Date(timestamp * 1000); // Convert Unix timestamp to milliseconds

	// Calculate the difference in milliseconds
	const diffTime = now.getTime() - date.getTime();
	const diffDays = diffTime / (1000 * 3600 * 24);

	const nowDate = now.getDate();
	const nowMonth = now.getMonth();
	const nowYear = now.getFullYear();

	const dateDate = date.getDate();
	const dateMonth = date.getMonth();
	const dateYear = date.getFullYear();

	if (nowYear === dateYear && nowMonth === dateMonth && nowDate === dateDate) {
		return 'Today';
	} else if (nowYear === dateYear && nowMonth === dateMonth && nowDate - dateDate === 1) {
		return 'Yesterday';
	} else if (diffDays <= 7) {
		return 'Previous 7 days';
	} else if (diffDays <= 30) {
		return 'Previous 30 days';
	} else if (nowYear === dateYear) {
		return date.toLocaleString('default', { month: 'long' });
	} else {
		return date.getFullYear().toString();
	}
};

/**
 * Extract frontmatter as a dictionary from the specified content string.
 * @param content {string} - The content string with potential frontmatter.
 * @returns {Object} - The extracted frontmatter as a dictionary.
 */
export const extractFrontmatter = (content: string) => {
	const frontmatter: Record<string, string> = {};
	let frontmatterStarted = false;
	let frontmatterEnded = false;
	const frontmatterPattern = /^\s*([a-z_]+):\s*(.*)\s*$/i;

	// Split content into lines
	const lines = content.split('\n');

	// Check if the content starts with triple quotes
	if (lines[0].trim() !== '"""') {
		return {};
	}

	frontmatterStarted = true;

	for (let i = 1; i < lines.length; i++) {
		const line = lines[i];

		if (line.includes('"""')) {
			if (frontmatterStarted) {
				frontmatterEnded = true;
				break;
			}
		}

		if (frontmatterStarted && !frontmatterEnded) {
			const match = frontmatterPattern.exec(line);
			if (match) {
				const [, key, value] = match;
				frontmatter[key.trim()] = value.trim();
			}
		}
	}

	return frontmatter;
};

// Function to determine the best matching language
export const bestMatchingLanguage = (
	supportedLanguages: { code: string }[],
	preferredLanguages: string[],
	defaultLocale: string
) => {
	const languages = supportedLanguages.map((lang) => lang.code);

	const match = preferredLanguages
		.map((prefLang: string) => languages.find((lang: string) => lang.startsWith(prefLang)))
		.find(Boolean);

	return match || defaultLocale;
};

export const createMessagesList = (
	history: { messages: Record<string, any> },
	messageId: string | null
): any[] => {
	if (messageId === null) {
		return [];
	}

	const message = history.messages[messageId];
	if (message === undefined) {
		return [];
	}
	if (message?.parentId) {
		return [...createMessagesList(history, message.parentId), message];
	} else {
		return [message];
	}
};

export const formatFileSize = (size: number | null | undefined) => {
	if (size == null) return 'Unknown size';
	if (typeof size !== 'number' || size < 0) return 'Invalid size';
	if (size === 0) return '0 B';
	const units = ['B', 'KB', 'MB', 'GB', 'TB'];
	let unitIndex = 0;

	while (size >= 1024 && unitIndex < units.length - 1) {
		size /= 1024;
		unitIndex++;
	}
	return `${size.toFixed(1)} ${units[unitIndex]}`;
};

export const getLineCount = (text: string) => {
	console.log(typeof text);
	return text ? text.split('\n').length : 0;
};

export const slugify = (str: string): string => {
	return (
		str
			// 1. Normalize: separate accented letters into base + combining marks
			.normalize('NFD')
			// 2. Remove all combining marks (the accents)
			.replace(/[\u0300-\u036f]/g, '')
			// 3. Replace any sequence of whitespace with a single hyphen
			.replace(/\s+/g, '-')
			// 4. Remove all characters except alphanumeric characters, hyphens, and underscores
			.replace(/[^a-zA-Z0-9-_]/g, '')
			// 5. Convert to lowercase
			.toLowerCase()
	);
};

export const extractContentFromFile = async (file: File) => {
	// Known text file extensions for extra fallback
	const textExtensions = [
		'.txt',
		'.md',
		'.csv',
		'.json',
		'.js',
		'.ts',
		'.css',
		'.html',
		'.xml',
		'.yaml',
		'.yml',
		'.rtf'
	];

	function getExtension(filename: string) {
		const dot = filename.lastIndexOf('.');
		return dot === -1 ? '' : filename.substr(dot).toLowerCase();
	}

	// Reads file as text using FileReader
	function readAsText(file: File) {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(reader.result);
			reader.onerror = reject;
			reader.readAsText(file);
		});
	}

	const type = file.type || '';
	const ext = getExtension(file.name);

	// Text check (plain or common text-based)
	if (type.startsWith('text/') || textExtensions.includes(ext)) {
		return await readAsText(file);
	}

	// Fallback: try to read as text, if decodable
	try {
		return await readAsText(file);
	} catch (err) {
		throw new Error('Unsupported or non-text file type: ' + (file.name || type));
	}
};

export const decodeString = (str: string) => {
	try {
		return decodeURIComponent(str);
	} catch (e) {
		return str;
	}
};

export const initMermaid = async () => {
	const { default: mermaid } = await import('mermaid');
	mermaid.initialize({
		startOnLoad: false, // Should be false when using render API
		theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
		securityLevel: 'loose'
	});
	return mermaid;
};

export const renderMermaidDiagram = async (mermaid: any, code: string) => {
	const parseResult = await mermaid.parse(code, { suppressErrors: false });
	if (parseResult) {
		const { svg } = await mermaid.render(`mermaid-${uuidv4()}`, code);
		return svg;
	}
	return '';
};

export const renderVegaVisualization = async (spec: string, i18n?: any) => {
	const vega = await import('vega');
	const parsedSpec = JSON.parse(spec);
	let vegaSpec = parsedSpec;
	if (parsedSpec.$schema && parsedSpec.$schema.includes('vega-lite')) {
		const vegaLite = await import('vega-lite');
		vegaSpec = vegaLite.compile(parsedSpec).spec;
	}
	const view = new vega.View(vega.parse(vegaSpec), { renderer: 'none' });
	const svg = await view.toSVG();
	return svg;
};

export const parseFrontmatter = (content: string) => {
	const match = content.match(/^---\s*\n([\s\S]*?)\n---/);
	if (match) {
		const frontmatter: Record<string, string> = {};
		match[1].split('\n').forEach((line) => {
			const [key, ...value] = line.split(':');
			if (key && value) {
				frontmatter[key.trim()] = value
					.join(':')
					.trim()
					.replace(/^["']|["']$/g, '');
			}
		});
		return frontmatter;
	}
	return {};
};

export const formatSkillName = (name: string) => {
	return name.replace(/[-_]/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
};
