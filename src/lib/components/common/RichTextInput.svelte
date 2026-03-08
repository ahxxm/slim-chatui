<script lang="ts">
	import { Marked } from 'marked';
	import DOMPurify from 'dompurify';

	const richTextMarked = new Marked({
		breaks: true,
		gfm: true,
		renderer: {
			list(body, ordered, start) {
				const isTaskList = body.includes('data-checked=');

				if (isTaskList) {
					return `<ul data-type="taskList">${body}</ul>`;
				}

				const type = ordered ? 'ol' : 'ul';
				const startatt = ordered && start !== 1 ? ` start="${start}"` : '';
				return `<${type}${startatt}>${body}</${type}>`;
			},

			listitem(text, task, checked) {
				if (task) {
					const checkedAttr = checked ? 'true' : 'false';
					return `<li data-type="taskItem" data-checked="${checkedAttr}">${text}</li>`;
				}
				return `<li>${text}</li>`;
			}
		}
	});

	import TurndownService from 'turndown';
	import { gfm } from '@joplin/turndown-plugin-gfm';
	const turndownService = new TurndownService({
		codeBlockStyle: 'fenced',
		headingStyle: 'atx'
	});
	turndownService.escape = (string) => string;

	// Use turndown-plugin-gfm for proper GFM table support
	turndownService.use(gfm);

	// Add custom table header rule before using GFM plugin
	turndownService.addRule('tableHeaders', {
		filter: 'th',
		replacement: function (content) {
			return content;
		}
	});

	// Add custom table rule to handle headers properly
	turndownService.addRule('tables', {
		filter: 'table',
		replacement: function (content, node) {
			// Extract rows
			const rows = Array.from(node.querySelectorAll('tr'));
			if (rows.length === 0) return content;

			let markdown = '\n';

			rows.forEach((row, rowIndex) => {
				const cells = Array.from(row.querySelectorAll('th, td'));
				const cellContents = cells.map((cell) => {
					// Get the text content and clean it up
					let cellContent = turndownService.turndown(cell.innerHTML).trim();
					// Remove extra paragraph tags that might be added
					cellContent = cellContent.replace(/^\n+|\n+$/g, '');
					return cellContent;
				});

				// Add the row
				markdown += '| ' + cellContents.join(' | ') + ' |\n';

				// Add separator after first row (which should be headers)
				if (rowIndex === 0) {
					const separator = cells.map(() => '---').join(' | ');
					markdown += '| ' + separator + ' |\n';
				}
			});

			return markdown + '\n';
		}
	});

	turndownService.addRule('taskListItems', {
		filter: (node) =>
			node.nodeName === 'LI' &&
			(node.getAttribute('data-checked') === 'true' ||
				node.getAttribute('data-checked') === 'false'),
		replacement: function (content, node) {
			const checked = node.getAttribute('data-checked') === 'true';
			content = content.replace(/^\s+/, '');
			return `- [${checked ? 'x' : ' '}] ${content}\n`;
		}
	});

	// Convert TipTap mention spans -> <@id>
	turndownService.addRule('mentions', {
		filter: (node) => node.nodeName === 'SPAN' && node.getAttribute('data-type') === 'mention',
		replacement: (_content, node: HTMLElement) => {
			const id = node.getAttribute('data-id') || '';
			// TipTap stores the trigger char in data-mention-suggestion-char (usually "@")
			const ch = node.getAttribute('data-mention-suggestion-char') || '@';
			// Emit <@id> style, e.g. <@llama3.2:latest>
			return `<${ch}${id}>`;
		}
	});

	import { onMount, onDestroy, tick, getContext, untrack } from 'svelte';
	const i18n = getContext('i18n');

	import { Fragment, DOMParser } from 'prosemirror-model';
	import { Plugin, PluginKey, TextSelection, Selection } from 'prosemirror-state';
	import { Decoration, DecorationSet } from 'prosemirror-view';
	import { Editor, Extension } from '@tiptap/core';

	import StarterKit from '@tiptap/starter-kit';

	import { TableKit } from '@tiptap/extension-table';
	import { ListKit } from '@tiptap/extension-list';
	import { Placeholder, CharacterCount } from '@tiptap/extensions';

	import Image from './RichTextInput/Image/index.js';
	// import TiptapImage from '@tiptap/extension-image';

	import FileHandler from '@tiptap/extension-file-handler';
	import Typography from '@tiptap/extension-typography';
	import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';

	import Mention from '@tiptap/extension-mention';
	import FormattingButtons from './RichTextInput/FormattingButtons.svelte';

	import { PASTED_TEXT_CHARACTER_LIMIT } from '$lib/constants';
	import { createLowlight } from 'lowlight';
	import hljs from 'highlight.js';

	let {
		oncompositionstart = (e) => {},
		oncompositionend = (e) => {},
		onChange = (e) => {},
		editor = $bindable(null),
		files = $bindable([]),
		className = 'input-prose min-h-fit h-full',
		placeholder = $i18n.t('Type here...'),
		richText = true,
		dragHandle = false,
		link = false,
		image = false,
		fileHandler = false,
		suggestions = null,
		onFileDrop: onFileDropProp = undefined,
		onFilePaste: onFilePasteProp = undefined,
		onSelectionUpdate = (e) => {},
		id = '',
		value = $bindable(''),
		html = $bindable(''),
		json = false,
		raw = false,
		editable = true,
		showFormattingToolbar = true,
		preserveBreaks = false,
		messageInput = false,
		shiftEnter = false,
		largeTextAsFile = false,
		insertPromptAsRichText = false,
		onfocus = (event: FocusEvent) => {},
		onkeyup = (event: KeyboardEvent) => {},
		onkeydown = (event: KeyboardEvent) => {},
		onpaste = (event: ClipboardEvent) => {}
	}: {
		oncompositionstart?: (e: any) => void;
		oncompositionend?: (e: any) => void;
		onChange?: (e: any) => void;
		editor?: any;
		files?: any[];
		className?: string;
		placeholder?: string;
		richText?: boolean;
		dragHandle?: boolean;
		link?: boolean;
		image?: boolean;
		fileHandler?: boolean;
		suggestions?: any;
		onFileDrop?: (currentEditor: any, files: any[], pos: number) => void;
		onFilePaste?: (currentEditor: any, files: any[], htmlContent: string) => void;
		onSelectionUpdate?: (e: any) => void;
		id?: string;
		value?: string;
		html?: string;
		json?: boolean;
		raw?: boolean;
		editable?: boolean;
		showFormattingToolbar?: boolean;
		preserveBreaks?: boolean;
		messageInput?: boolean;
		shiftEnter?: boolean;
		largeTextAsFile?: boolean;
		insertPromptAsRichText?: boolean;
		onfocus: (event: FocusEvent) => void;
		onkeyup: (event: KeyboardEvent) => void;
		onkeydown: (event: KeyboardEvent) => void;
		onpaste: (event: ClipboardEvent) => void;
	} = $props();

	// create a lowlight instance with all languages loaded
	const lowlight = createLowlight(
		hljs.listLanguages().reduce(
			(obj, lang) => {
				obj[lang] = () => hljs.getLanguage(lang);
				return obj;
			},
			{} as Record<string, any>
		)
	);

	let _placeholder = $state(placeholder);

	$effect(() => {
		if (placeholder !== _placeholder) {
			untrack(() => setPlaceholder());
		}
	});

	const setPlaceholder = () => {
		_placeholder = placeholder;
		if (editor) {
			editor?.view.dispatch(editor.state.tr);
		}
	};

	const defaultOnFileDrop = (currentEditor, files, pos) => {
		files.forEach((file) => {
			const fileReader = new FileReader();

			fileReader.readAsDataURL(file);
			fileReader.onload = () => {
				currentEditor
					.chain()
					.insertContentAt(pos, {
						type: 'image',
						attrs: {
							src: fileReader.result
						}
					})
					.focus()
					.run();
			};
		});
	};

	const defaultOnFilePaste = (currentEditor, files, htmlContent) => {
		files.forEach((file) => {
			if (htmlContent) {
				// if there is htmlContent, stop manual insertion & let other extensions handle insertion via inputRule
				// you could extract the pasted file from this url string and upload it to a server for example
				console.log(htmlContent); // eslint-disable-line no-console
				return false;
			}

			const fileReader = new FileReader();

			fileReader.readAsDataURL(file);
			fileReader.onload = () => {
				currentEditor
					.chain()
					.insertContentAt(currentEditor.state.selection.anchor, {
						type: 'image',
						attrs: {
							src: fileReader.result
						}
					})
					.focus()
					.run();
			};
		});
	};

	const onFileDrop = onFileDropProp ?? defaultOnFileDrop;
	const onFilePaste = onFilePasteProp ?? defaultOnFilePaste;

	let content = $state(null);
	let htmlValue = $state('');
	let jsonValue = $state('');
	let mdValue = $state('');

	let element: Element | null = $state(null);

	$effect(() => {
		if (editor) {
			editor.setOptions({
				editable: editable
			});
		}
	});

	$effect(() => {
		if (value === null && html !== null && editor) {
			untrack(() => editor.commands.setContent(html));
		}
	});

	export const getWordAtDocPos = () => {
		if (!editor) return '';
		const { state } = editor.view;
		const pos = state.selection.from;
		const doc = state.doc;
		const resolvedPos = doc.resolve(pos);
		const textBlock = resolvedPos.parent;
		const text = textBlock.textContent;
		const offset = resolvedPos.parentOffset;

		let wordStart = offset,
			wordEnd = offset;
		while (wordStart > 0 && !/\s/.test(text[wordStart - 1])) wordStart--;
		while (wordEnd < text.length && !/\s/.test(text[wordEnd])) wordEnd++;

		return text.slice(wordStart, wordEnd);
	};

	// Returns {start, end} of the word at pos
	function getWordBoundsAtPos(doc, pos) {
		const resolvedPos = doc.resolve(pos);
		const textBlock = resolvedPos.parent;
		const paraStart = resolvedPos.start();
		const text = textBlock.textContent;

		const offset = resolvedPos.parentOffset;
		let wordStart = offset,
			wordEnd = offset;
		while (wordStart > 0 && !/\s/.test(text[wordStart - 1])) wordStart--;
		while (wordEnd < text.length && !/\s/.test(text[wordEnd])) wordEnd++;
		return {
			start: paraStart + wordStart,
			end: paraStart + wordEnd
		};
	}

	export const replaceCommandWithText = async (text) => {
		const { state, dispatch } = editor.view;
		const { selection } = state;
		const pos = selection.from;

		// Get the plain text of this document
		// const docText = state.doc.textBetween(0, state.doc.content.size, '\n', '\n');

		// Find the word boundaries at cursor
		const { start, end } = getWordBoundsAtPos(state.doc, pos);

		let tr = state.tr;

		if (insertPromptAsRichText) {
			const htmlContent = DOMPurify.sanitize(richTextMarked.parse(text).trim());

			// Create a temporary div to parse HTML
			const tempDiv = document.createElement('div');
			tempDiv.innerHTML = htmlContent;

			// Convert HTML to ProseMirror nodes
			const fragment = DOMParser.fromSchema(state.schema).parse(tempDiv);

			// Extract just the content, not the wrapper paragraphs
			const content = fragment.content;
			let nodesToInsert = [];

			content.forEach((node) => {
				if (node.type.name === 'paragraph') {
					// If it's a paragraph, extract its content
					nodesToInsert.push(...node.content.content);
				} else {
					nodesToInsert.push(node);
				}
			});

			tr = tr.replaceWith(start, end, nodesToInsert);
			// Calculate new position
			const newPos = start + nodesToInsert.reduce((sum, node) => sum + node.nodeSize, 0);
			tr = tr.setSelection(Selection.near(tr.doc.resolve(newPos)));
		} else {
			if (text.includes('\n')) {
				// Split the text into lines and create a <p> node for each line
				const lines = text.split('\n');
				const nodes = lines.map(
					(line, index) =>
						index === 0
							? state.schema.text(line ? line : []) // First line is plain text
							: state.schema.nodes.paragraph.create({}, line ? state.schema.text(line) : undefined) // Subsequent lines are paragraphs
				);

				// Build and dispatch the transaction to replace the word at cursor
				tr = tr.replaceWith(start, end, nodes);

				let newSelectionPos;

				// +1 because the insert happens at start, so last para starts at (start + sum of all previous nodes' sizes)
				let lastPos = start;
				for (let i = 0; i < nodes.length; i++) {
					lastPos += nodes[i].nodeSize;
				}
				// Place cursor inside the last paragraph at its end
				newSelectionPos = lastPos;

				tr = tr.setSelection(TextSelection.near(tr.doc.resolve(newSelectionPos)));
			} else {
				tr = tr.replaceWith(
					start,
					end, // replace this range
					text !== '' ? state.schema.text(text) : []
				);

				tr = tr.setSelection(
					state.selection.constructor.near(tr.doc.resolve(start + text.length + 1))
				);
			}
		}

		dispatch(tr);

		await tick();
		// selectNextTemplate(state, dispatch);
	};

	export const setText = (text: string) => {
		if (!editor || !editor.view) return;
		text = text.replaceAll('\n\n', '\n');

		// reset the editor content
		editor.commands.clearContent();

		const { state, view } = editor;
		const { schema, tr } = state;

		if (text.includes('\n')) {
			// Multiple lines: make paragraphs
			const lines = text.split('\n');
			// Map each line to a paragraph node (empty lines -> empty paragraph)
			const nodes = lines.map((line) =>
				schema.nodes.paragraph.create({}, line ? schema.text(line) : undefined)
			);
			// Create a document fragment containing all parsed paragraphs
			const fragment = Fragment.fromArray(nodes);
			// Replace current selection with these paragraphs
			tr.replaceSelectionWith(fragment, false /* don't select new */);
			view.dispatch(tr);
		} else if (text === '') {
			// Empty: replace with empty paragraph using tr
			editor.commands.clearContent();
		} else {
			// Single line: create paragraph with text
			const paragraph = schema.nodes.paragraph.create({}, schema.text(text));
			tr.replaceSelectionWith(paragraph, false);
			view.dispatch(tr);
		}

		selectNextTemplate(editor.view.state, editor.view.dispatch);

		// Ensure the editor is still valid before trying to focus
		focus();
	};

	export const insertContent = (content) => {
		if (!editor || !editor.view) return;

		// If content is a string, convert it to a ProseMirror node
		const htmlContent = richTextMarked.parse(content);

		// insert the HTML content at the current selection
		editor.commands.insertContent(htmlContent);

		focus();
	};

	export const focus = () => {
		if (editor && editor.view) {
			// Check if the editor is destroyed
			if (editor.isDestroyed) {
				return;
			}

			try {
				editor.view.focus();
				// Scroll to the current selection
				editor.view.dispatch(editor.view.state.tr.scrollIntoView());
			} catch (e) {
				// sometimes focusing throws an error, ignore
				console.warn('Error focusing editor', e);
			}
		}
	};

	// Function to find the next template in the document
	function findNextTemplate(doc: any, from = 0): { from: number; to: number } | null {
		const patterns = [{ start: '{{', end: '}}' }];

		let result: { from: number; to: number } | null = null;

		doc.nodesBetween(from, doc.content.size, (node, pos) => {
			if (result) return false; // Stop if we've found a match
			if (node.isText) {
				const text = node.text;
				let index = Math.max(0, from - pos);
				while (index < text.length) {
					for (const pattern of patterns) {
						if (text.startsWith(pattern.start, index)) {
							const endIndex = text.indexOf(pattern.end, index + pattern.start.length);
							if (endIndex !== -1) {
								result = {
									from: pos + index,
									to: pos + endIndex + pattern.end.length
								};
								return false; // Stop searching
							}
						}
					}
					index++;
				}
			}
		});

		return result;
	}

	// Function to select the next template in the document
	function selectNextTemplate(state, dispatch) {
		const { doc, selection } = state;
		const from = selection.to;
		let template = findNextTemplate(doc, from);

		if (!template) {
			// If not found, search from the beginning
			template = findNextTemplate(doc, 0);
		}

		if (template) {
			if (dispatch) {
				const tr = state.tr.setSelection(TextSelection.create(doc, template.from, template.to));
				dispatch(tr);

				// Scroll to the selected template
				dispatch(
					tr.scrollIntoView().setMeta('preventScroll', true) // Prevent default scrolling behavior
				);
			}
			return true;
		}
		return false;
	}

	export const setContent = (content) => {
		editor.commands.setContent(content);
	};

	const selectTemplate = () => {
		if (value !== '') {
			// After updating the state, try to find and select the next template
			setTimeout(() => {
				const templateFound = selectNextTemplate(editor.view.state, editor.view.dispatch);
				if (!templateFound) {
					editor.commands.focus('end');
				}
			}, 0);
		}
	};

	const SelectionDecoration = Extension.create({
		name: 'selectionDecoration',
		addProseMirrorPlugins() {
			return [
				new Plugin({
					key: new PluginKey('selection'),
					props: {
						decorations: (state) => {
							const { selection } = state;
							const { focused } = this.editor;

							if (focused || selection.empty) {
								return null;
							}

							return DecorationSet.create(state.doc, [
								Decoration.inline(selection.from, selection.to, {
									class: 'editor-selection'
								})
							]);
						}
					}
				})
			];
		}
	});

	import { listDragHandlePlugin } from './RichTextInput/listDragHandlePlugin';

	const ListItemDragHandle = Extension.create({
		name: 'listItemDragHandle',
		addProseMirrorPlugins() {
			return [
				listDragHandlePlugin({
					itemTypeNames: ['listItem', 'taskItem'],
					getEditor: () => this.editor
				})
			];
		}
	});

	onMount(async () => {
		content = value;

		if (json) {
			if (!content) {
				content = html ? html : null;
			}
		} else {
			if (preserveBreaks) {
				turndownService.addRule('preserveBreaks', {
					filter: 'br', // Target <br> elements
					replacement: function () {
						return '<br/>';
					}
				});
			}

			if (!raw) {
				async function tryParse(value, attempts = 3, interval = 100) {
					try {
						// Try parsing the value
						return richTextMarked.parse(value.replaceAll(`\n<br/>`, `<br/>`), {
							breaks: false
						});
					} catch {
						// If no attempts remain, fallback to plain text
						if (attempts <= 1) {
							return value;
						}
						// Wait for the interval, then retry
						await new Promise((resolve) => setTimeout(resolve, interval));
						return tryParse(value, attempts - 1, interval); // Recursive call
					}
				}

				// Usage example
				content = await tryParse(value);
			}
		}

		editor = new Editor({
			element: element,
			extensions: [
				StarterKit.configure({
					link: link,
					// StarterKit bundles codeBlock/bulletList/listItem/orderedList/listKeymap,
					// which conflict with CodeBlockLowlight + ListKit added below in richText mode.
					// In plain mode, disable Strike so Mod-Shift-s stays free for Toggle Sidebar.
					...(richText
						? {
								codeBlock: false,
								bulletList: false,
								listItem: false,
								orderedList: false,
								listKeymap: false
							}
						: { strike: false })
				}),
				...(dragHandle ? [ListItemDragHandle] : []),
				Placeholder.configure({ placeholder: () => _placeholder, showOnlyWhenEditable: false }),
				SelectionDecoration,

				...(richText
					? [
							CodeBlockLowlight.configure({
								lowlight
							}),
							Typography,
							TableKit.configure({
								table: { resizable: true }
							}),
							ListKit.configure({
								taskItem: {
									nested: true
								}
							})
						]
					: []),
				...(suggestions
					? [
							Mention.configure({
								HTMLAttributes: { class: 'mention' },
								suggestions: suggestions
							})
						]
					: []),

				CharacterCount.configure({}),
				...(image ? [Image] : []),
				...(fileHandler
					? [
							FileHandler.configure({
								onDrop: onFileDrop,
								onPaste: onFilePaste
							})
						]
					: [])
			],
			content,
			autofocus: messageInput ? true : false,
			onTransaction: () => {
				// Defer state mutations out of the synchronous TipTap transaction
				// to avoid Svelte 5 state_unsafe_mutation errors.
				queueMicrotask(() => {
					if (!editor) return;

					htmlValue = editor.getHTML();
					jsonValue = editor.getJSON();

					const sanitizedHtml = htmlValue
						.replace(/<p><\/p>/g, '<br/>')
						.replace(/ {2,}/g, (m) => m.replace(/ /g, '\u00a0'));

					if (richText) {
						mdValue = turndownService.turndown(sanitizedHtml).replace(/\u00a0/g, ' ');
					} else {
						mdValue = turndownService
							.turndown(sanitizedHtml.replace(/\t/g, '\u00a0\u00a0\u00a0\u00a0'))
							.replace(/\u00a0/g, ' ');
					}

					onChange({
						html: htmlValue,
						json: jsonValue,
						md: mdValue
					});

					if (json) {
						value = jsonValue;
					} else if (raw) {
						value = htmlValue;
					} else {
						if (!preserveBreaks) {
							mdValue = mdValue.replace(/<br\/>/g, '');
						}

						if (value !== mdValue) {
							value = mdValue;

							if (editor.isActive('paragraph') && value === '') {
								editor.commands.clearContent();
							}
						}
					}
				});
			},
			editorProps: {
				attributes: { id },
				handlePaste: (view, event) => {
					// Force plain-text pasting when richText === false
					if (!richText) {
						// swallow HTML completely
						event.preventDefault();
						const { state, dispatch } = view;

						const plainText = (event.clipboardData?.getData('text/plain') ?? '').replace(
							/\r\n/g,
							'\n'
						);

						const lines = plainText.split('\n');
						const nodes = [];

						lines.forEach((line, index) => {
							if (index > 0) {
								nodes.push(state.schema.nodes.hardBreak.create());
							}
							if (line.length > 0) {
								nodes.push(state.schema.text(line));
							}
						});

						const fragment = Fragment.fromArray(nodes);
						dispatch(state.tr.replaceSelectionWith(fragment, false).scrollIntoView());

						return true; // handled
					}

					return false;
				},
				handleDOMEvents: {
					compositionstart: (view, event) => {
						oncompositionstart(event);
						return false;
					},
					compositionend: (view, event) => {
						oncompositionend(event);
						return false;
					},
					beforeinput: (view, event) => {
						// Workaround for Gboard's clipboard suggestion strip which sends
						// multi-line pastes as 'insertText' rather than a standard paste event.
						// Manually insert with hard breaks to preserve multi-line formatting.
						const isAndroid = /Android/i.test(navigator.userAgent);
						if (isAndroid && event.inputType === 'insertText' && event.data?.includes('\n')) {
							event.preventDefault();

							const { state, dispatch } = view;
							const { from, to } = state.selection;
							const lines = event.data.split('\n');
							const nodes = [];

							lines.forEach((line, index) => {
								if (index > 0) {
									nodes.push(state.schema.nodes.hardBreak.create());
								}
								if (line.length > 0) {
									nodes.push(state.schema.text(line));
								}
							});

							const fragment = Fragment.fromArray(nodes);
							dispatch(state.tr.replaceWith(from, to, fragment).scrollIntoView());
							return true;
						}
						return false;
					},
					focus: (view, event) => {
						onfocus(event);
						return false;
					},
					keyup: (view, event) => {
						onkeyup(event);
						return false;
					},
					keydown: (view, event) => {
						if (messageInput) {
							// Check if the current selection is inside a structured block (like codeBlock or list)
							const { state } = view;
							const head = state.selection.$head;

							// Recursive function to check ancestors for specific node types
							function isInside(nodeTypes: string[]): boolean {
								let currentNode = head;
								while (currentNode) {
									if (nodeTypes.includes(currentNode.parent.type.name)) {
										return true;
									}
									if (!currentNode.depth) break; // Stop if we reach the top
									currentNode = state.doc.resolve(currentNode.before()); // Move to the parent node
								}
								return false;
							}

							// Handle Tab Key
							if (event.key === 'Tab') {
								const isInCodeBlock = isInside(['codeBlock']);

								if (isInCodeBlock) {
									// Handle tab in code block - insert tab character or spaces
									const tabChar = '\t'; // or '    ' for 4 spaces
									editor.commands.insertContent(tabChar);
									event.preventDefault();
									return true; // Prevent further propagation
								} else {
									const handled = selectNextTemplate(view.state, view.dispatch);
									if (handled) {
										event.preventDefault();
										return true;
									}
								}
							}

							if (event.key === 'Enter') {
								const isCtrlPressed = event.ctrlKey || event.metaKey; // metaKey is for Cmd key on Mac

								const { state } = view;
								const fromPos = state.selection.$from;
								const lineStart = fromPos.before(fromPos.depth);
								const lineEnd = fromPos.after(fromPos.depth);
								const lineText = state.doc.textBetween(lineStart, lineEnd, '\n', '\0').trim();
								if (event.shiftKey && !isCtrlPressed) {
									if (lineText.startsWith('```')) {
										// Fix GitHub issue #16337: prevent backtick removal for lines starting with ```
										return false; // Let ProseMirror handle the Enter key normally
									}

									editor.commands.enter(); // Insert a new line
									view.dispatch(view.state.tr.scrollIntoView()); // Move viewport to the cursor
									event.preventDefault();
									return true;
								} else {
									const isInCodeBlock = isInside(['codeBlock']);
									const isInList = isInside(['listItem', 'bulletList', 'orderedList', 'taskList']);
									const isInHeading = isInside(['heading']);

									console.log({ isInCodeBlock, isInList, isInHeading });

									if (isInCodeBlock || isInList || isInHeading) {
										// Let ProseMirror handle the normal Enter behavior
										return false;
									}

									const suggestionsElement = document.getElementById('suggestions-container');
									if (lineText.startsWith('#') && suggestionsElement) {
										console.log('Letting heading suggestion handle Enter key');
										return true;
									}
								}
							}

							// Handle shift + Enter for a line break
							if (shiftEnter) {
								if (event.key === 'Enter' && event.shiftKey && !event.ctrlKey && !event.metaKey) {
									editor.commands.setHardBreak(); // Insert a hard break
									view.dispatch(view.state.tr.scrollIntoView()); // Move viewport to the cursor
									event.preventDefault();
									return true;
								}
							}
						}
						onkeydown(event);
						return false;
					},
					paste: (view, event) => {
						if (event.clipboardData) {
							const plainText = event.clipboardData.getData('text/plain');
							if (plainText) {
								if (largeTextAsFile && plainText.length > PASTED_TEXT_CHARACTER_LIMIT) {
									// Delegate handling of large text pastes to the parent component.
									onpaste(event);
									event.preventDefault();
									return true;
								}

								// Workaround for mobile WebViews that strip line breaks when pasting from
								// clipboard suggestions (e.g., Gboard clipboard history).
								const isMobile = /Android|iPhone|iPad|iPod|Windows Phone/i.test(
									navigator.userAgent
								);
								const isWebView =
									typeof window !== 'undefined' &&
									(/wv/i.test(navigator.userAgent) || // Standard Android WebView flag
										(navigator.userAgent.includes('Android') &&
											!navigator.userAgent.includes('Chrome')) || // Other generic Android WebViews
										(navigator.userAgent.includes('Safari') &&
											!navigator.userAgent.includes('Version'))); // iOS WebView (in-app browsers)

								if (isMobile && isWebView && plainText.includes('\n')) {
									// Manually deconstruct the pasted text and insert it with hard breaks
									// to preserve the multi-line formatting.
									const { state, dispatch } = view;
									const { from, to } = state.selection;

									const lines = plainText.split('\n');
									const nodes = [];

									lines.forEach((line, index) => {
										if (index > 0) {
											nodes.push(state.schema.nodes.hardBreak.create());
										}
										if (line.length > 0) {
											nodes.push(state.schema.text(line));
										}
									});

									const fragment = Fragment.fromArray(nodes);
									const tr = state.tr.replaceWith(from, to, fragment);
									dispatch(tr.scrollIntoView());
									event.preventDefault();
									return true;
								}
								// Let ProseMirror handle normal text paste in non-problematic environments.
								return false;
							}

							// Delegate image paste handling to the parent component.
							const hasImageFile = Array.from(event.clipboardData.files).some((file) =>
								file.type.startsWith('image/')
							);
							// Fallback for cases where an image is in dataTransfer.items but not clipboardData.files.
							const hasImageItem = Array.from(event.clipboardData.items).some((item) =>
								item.type.startsWith('image/')
							);

							const hasFile = Array.from(event.clipboardData.files).length > 0;

							if (hasImageFile || hasImageItem || hasFile) {
								onpaste(event);
								event.preventDefault();
								return true;
							}
						}
						// For all other cases, let ProseMirror perform its default paste behavior.
						view.dispatch(view.state.tr.scrollIntoView());
						return false;
					},
					copy: (view, event: ClipboardEvent) => {
						if (!event.clipboardData) return false;
						if (richText) return false; // Let ProseMirror handle normal copy in rich text mode

						const { state } = view;
						const { from, to } = state.selection;

						// Only take the selected text & HTML, not the full doc
						const plain = state.doc.textBetween(from, to, '\n');
						const slice = state.doc.cut(from, to);
						const html = editor.schema ? editor.getHTML(slice) : editor.getHTML(); // depending on your editor API

						event.clipboardData.setData('text/plain', plain);
						event.clipboardData.setData('text/html', html);

						event.preventDefault();
						return true;
					}
				}
			},
			onBeforeCreate: ({ editor }) => {
				if (files) {
					editor.storage.files = files;
				}
			},
			onSelectionUpdate: onSelectionUpdate,
			enableInputRules: richText,
			enablePasteRules: richText
		});

		if (messageInput) {
			selectTemplate();
		}
	});

	onDestroy(() => {
		if (editor) {
			editor.destroy();
		}
	});

	$effect(() => {
		if (value !== null && editor) {
			untrack(() => onValueChange());
		}
	});

	const onValueChange = () => {
		if (!editor) return;

		const jsonValue = editor.getJSON();
		const htmlValue = editor.getHTML();
		let mdValue = turndownService
			.turndown(
				(preserveBreaks ? htmlValue.replace(/<p><\/p>/g, '<br/>') : htmlValue).replace(
					/ {2,}/g,
					(m) => m.replace(/ /g, '\u00a0')
				)
			)
			.replace(/\u00a0/g, ' ');

		if (value === '') {
			editor.commands.clearContent(); // Clear content if value is empty
			selectTemplate();

			return;
		}

		if (json) {
			if (JSON.stringify(value) !== JSON.stringify(jsonValue)) {
				editor.commands.setContent(value);
				selectTemplate();
			}
		} else {
			if (raw) {
				if (value !== htmlValue) {
					editor.commands.setContent(value);
					selectTemplate();
				}
			} else {
				if (value !== mdValue) {
					editor.commands.setContent(
						preserveBreaks
							? value
							: richTextMarked.parse(value.replaceAll(`\n<br/>`, `<br/>`), {
									breaks: false
								})
					);

					selectTemplate();
				}
			}
		}
	};
</script>

{#if richText && showFormattingToolbar && editor}
	<div class="mb-1">
		<FormattingButtons {editor} />
	</div>
{/if}

<div
	bind:this={element}
	dir="auto"
	class="relative w-full min-w-full {className} {!editable ? 'cursor-not-allowed' : ''}"
/>
