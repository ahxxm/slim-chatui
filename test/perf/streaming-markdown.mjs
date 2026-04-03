import { dirname, resolve } from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';

import { createServer } from 'vite';

globalThis.Image = class ImageStub {
	constructor() {
		this.src = '';
	}
};

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

process.chdir(root);

function percentile(values, percentileValue) {
	if (values.length === 0) return 0;

	const sorted = [...values].sort((left, right) => left - right);
	const index = Math.min(
		sorted.length - 1,
		Math.max(0, Math.ceil((percentileValue / 100) * sorted.length) - 1)
	);

	return sorted[index];
}

const STEADY_STATE_FLUSH_WINDOW = 40;

function mean(values) {
	if (values.length === 0) return 0;
	return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function summarize(times) {
	const total = times.reduce((sum, value) => sum + value, 0);
	const steadyStateTimes = times.slice(-Math.min(STEADY_STATE_FLUSH_WINDOW, times.length));

	return {
		total,
		average: total / times.length,
		steadyStateAverage: mean(steadyStateTimes),
		p95: percentile(times, 95),
		max: Math.max(...times),
		last: times.at(-1)
	};
}

function speedup(left, right) {
	if (right === 0) return Number.POSITIVE_INFINITY;
	return left / right;
}

function buildSampleSection(sectionNumber) {
	return [
		`## Section ${sectionNumber}`,
		`This response explains **trade-offs**, includes _emphasis_, inline code like \`const value = ${sectionNumber};\`, and a citation [${(sectionNumber % 9) + 1}] for reference.`,
		'',
		'- First point with a [link](https://example.com/docs).',
		'- Second point with math $E = mc^2$ and a placeholder for {{char}} talking to {{user}}.',
		'- Third point with nested detail and a short quote.',
		'',
		'| Column | Value | Notes |',
		'| --- | ---: | --- |',
		`| Iteration | ${sectionNumber} | Stable markdown table row |`,
		'| Status | active | Streaming incremental benchmark |',
		'',
		'```python',
		'def fibonacci(limit: int) -> list[int]:',
		'    numbers = [0, 1]',
		'    while len(numbers) < limit:',
		'        numbers.append(numbers[-1] + numbers[-2])',
		'    return numbers[:limit]',
		'',
		`print(fibonacci(${10 + (sectionNumber % 5)}))`,
		'```'
	].join('\n');
}

function buildRichBlockScenario({ sections }) {
	const parts = [];

	for (let sectionNumber = 1; sectionNumber <= sections; sectionNumber += 1) {
		parts.push(buildSampleSection(sectionNumber));
		parts.push('');
	}

	return parts.join('\n');
}

function buildLongParagraphScenario({ segments, includeChinese = false }) {
	const parts = [];

	for (let segmentNumber = 1; segmentNumber <= segments; segmentNumber += 1) {
		parts.push(
			`Segment ${segmentNumber} explains **trade-offs**, _emphasis_, [link](https://example.com/${segmentNumber}), \`value_${segmentNumber}\`, citation [${(segmentNumber % 9) + 1}], and placeholder {{char}} talking to {{user}}.`
		);

		if (includeChinese) {
			parts.push(`中文片段${segmentNumber}：**中文名（English）**中文内容与连续解释。`);
		}
	}

	return parts.join(' ');
}

function buildFlushes(content, totalFlushes) {
	const flushes = [];

	for (let flushIndex = 1; flushIndex <= totalFlushes; flushIndex += 1) {
		const end = Math.max(1, Math.floor((content.length * flushIndex) / totalFlushes));
		flushes.push(content.slice(0, end));
	}

	return flushes;
}

function normalizeFlushes(flushes, processResponseContent, replaceTokens) {
	return flushes.map((partialContent) =>
		replaceTokens(processResponseContent(partialContent), 'Assistant', 'User')
	);
}

function collectRootInlineSourcesFromBlockTokens(tokens, baseId, top = true, sources = []) {
	tokens.forEach((token, tokenIdx) => {
		const tokenId = `${baseId}-${tokenIdx}`;

		if (token.type === 'heading') {
			sources.push({
				id: `${tokenId}-h`,
				source: token.text ?? ''
			});
			return;
		}

		if (token.type === 'table') {
			token.header.forEach((cell, headerIdx) => {
				sources.push({
					id: `${tokenId}-header-${headerIdx}`,
					source: cell.text ?? ''
				});
			});

			token.rows.forEach((row, rowIdx) => {
				row.forEach((cell, cellIdx) => {
					sources.push({
						id: `${tokenId}-row-${rowIdx}-${cellIdx}`,
						source: cell.text ?? ''
					});
				});
			});

			return;
		}

		if (token.type === 'blockquote') {
			collectRootInlineSourcesFromBlockTokens(token.tokens ?? [], tokenId, true, sources);
			return;
		}

		if (token.type === 'list') {
			token.items.forEach((item, itemIdx) => {
				collectRootInlineSourcesFromBlockTokens(
					item.tokens ?? [],
					`${tokenId}-${itemIdx}`,
					token.loose,
					sources
				);
			});
			return;
		}

		if (token.type === 'details') {
			collectRootInlineSourcesFromBlockTokens(token.tokens ?? [], `${tokenId}-d`, true, sources);
			return;
		}

		if (token.type === 'paragraph') {
			sources.push({
				id: `${tokenId}-p`,
				source: token.text ?? ''
			});
			return;
		}

		if (token.type === 'text' && token.tokens) {
			sources.push({
				id: `${tokenId}-${top ? 't' : 'p'}`,
				source: token.text ?? ''
			});
		}
	});

	return sources;
}

function collectNestedInlineSources(token, baseId, shouldRenderNestedLinkTokens, sources = []) {
	if (token.type === 'link' && shouldRenderNestedLinkTokens(token)) {
		sources.push({
			id: `${baseId}-a`,
			source: token.text ?? ''
		});
		return sources;
	}

	if (token.type === 'strong') {
		sources.push({
			id: `${baseId}-strong`,
			source: token.text ?? ''
		});
		return sources;
	}

	if (token.type === 'em') {
		sources.push({
			id: `${baseId}-em`,
			source: token.text ?? ''
		});
		return sources;
	}

	if (token.type === 'del') {
		sources.push({
			id: `${baseId}-del`,
			source: token.text ?? ''
		});
	}

	return sources;
}

function benchmarkFullReparse(normalizedFlushes, chatMarked) {
	const fullReparseTimes = [];

	for (const content of normalizedFlushes) {
		const start = performance.now();
		chatMarked.lexer(content);
		fullReparseTimes.push(performance.now() - start);
	}

	return summarize(fullReparseTimes);
}

function updateInlineRenderTree(
	rootInlineSource,
	previousInlineStates,
	nextInlineStates,
	links,
	shouldRenderNestedLinkTokens,
	createIncrementalTokenState,
	updateIncrementalTokenState,
	getRenderSegments
) {
	const previousInlineState =
		previousInlineStates.get(rootInlineSource.id) ??
		createIncrementalTokenState('inline', { seedLinks: links });
	const nextInlineState = updateIncrementalTokenState(previousInlineState, rootInlineSource.source, {
		seedLinks: links
	});

	nextInlineStates.set(rootInlineSource.id, nextInlineState);

	const childInlineSources = [];

	getRenderSegments(nextInlineState).forEach((segment) => {
		collectNestedInlineSources(
			segment.tokens[0],
			`${rootInlineSource.id}-${segment.id}`,
			shouldRenderNestedLinkTokens,
			childInlineSources
		);
	});

	childInlineSources.forEach((childInlineSource) => {
		updateInlineRenderTree(
			childInlineSource,
			previousInlineStates,
			nextInlineStates,
			links,
			shouldRenderNestedLinkTokens,
			createIncrementalTokenState,
			updateIncrementalTokenState,
			getRenderSegments
		);
	});
}

function benchmarkIncrementalRenderPath(
	normalizedFlushes,
	shouldRenderNestedLinkTokens,
	createIncrementalTokenState,
	updateIncrementalTokenState,
	getRenderSegments
) {
	let blockState = createIncrementalTokenState('block');
	let inlineStates = new Map();

	const blockUpdateTimes = [];
	const inlineUpdateTimes = [];
	const totalTimes = [];

	for (const content of normalizedFlushes) {
		const totalStart = performance.now();

		const blockStart = performance.now();
		blockState = updateIncrementalTokenState(blockState, content);
		const blockSegments = getRenderSegments(blockState);
		blockUpdateTimes.push(performance.now() - blockStart);

		const inlineStart = performance.now();
		const nextInlineStates = new Map();
		const rootInlineSources = [];

		blockSegments.forEach((segment) => {
			collectRootInlineSourcesFromBlockTokens(segment.tokens, segment.id, true, rootInlineSources);
		});

		rootInlineSources.forEach((inlineSource) => {
			updateInlineRenderTree(
				inlineSource,
				inlineStates,
				nextInlineStates,
				blockState.links,
				shouldRenderNestedLinkTokens,
				createIncrementalTokenState,
				updateIncrementalTokenState,
				getRenderSegments
			);
		});

		inlineStates = nextInlineStates;
		inlineUpdateTimes.push(performance.now() - inlineStart);
		totalTimes.push(performance.now() - totalStart);
	}

	return {
		block: summarize(blockUpdateTimes),
		inline: summarize(inlineUpdateTimes),
		total: summarize(totalTimes)
	};
}

function benchmarkScenario(
	scenario,
	processResponseContent,
	replaceTokens,
	chatMarked,
	shouldRenderNestedLinkTokens,
	createIncrementalTokenState,
	updateIncrementalTokenState,
	getRenderSegments
) {
	const flushes = buildFlushes(scenario.content, scenario.totalFlushes);
	const normalizedFlushes = normalizeFlushes(flushes, processResponseContent, replaceTokens);
	const fullReparse = benchmarkFullReparse(normalizedFlushes, chatMarked);
	const incremental = benchmarkIncrementalRenderPath(
		normalizedFlushes,
		shouldRenderNestedLinkTokens,
		createIncrementalTokenState,
		updateIncrementalTokenState,
		getRenderSegments
	);

	return {
		scenario: scenario.name,
		finalChars: normalizedFlushes.at(-1)?.length ?? 0,
		flushes: normalizedFlushes.length,
		fullReparse,
		incremental
	};
}

function warmUp(
	normalizedFlushes,
	chatMarked,
	shouldRenderNestedLinkTokens,
	createIncrementalTokenState,
	updateIncrementalTokenState,
	getRenderSegments
) {
	benchmarkFullReparse(normalizedFlushes, chatMarked);
	benchmarkIncrementalRenderPath(
		normalizedFlushes,
		shouldRenderNestedLinkTokens,
		createIncrementalTokenState,
		updateIncrementalTokenState,
		getRenderSegments
	);
}

const vite = await createServer({
	configFile: resolve(root, 'vite.config.ts'),
	logLevel: 'error',
	server: {
		middlewareMode: true,
		hmr: false
	}
});

try {
	const utils = await vite.ssrLoadModule('/src/lib/utils/index.ts');
	const marked = await vite.ssrLoadModule('/src/lib/utils/marked/chat-marked.ts');
	const incremental = await vite.ssrLoadModule('/src/lib/utils/marked/incremental.ts');
	const render = await vite.ssrLoadModule('/src/lib/utils/marked/render.ts');

	const { processResponseContent, replaceTokens } = utils;
	const { chatMarked } = marked;
	const { createIncrementalTokenState, updateIncrementalTokenState, getRenderSegments } =
		incremental;
	const { shouldRenderNestedLinkTokens } = render;

	const scenarios = [
		{
			name: 'rich-block-en-2k-ish',
			content: buildRichBlockScenario({ sections: 18 }),
			totalFlushes: 280
		},
		{
			name: 'rich-block-en-4k-ish',
			content: buildRichBlockScenario({ sections: 36 }),
			totalFlushes: 280
		},
		{
			name: 'long-paragraph-en-2k-ish',
			content: buildLongParagraphScenario({ segments: 36 }),
			totalFlushes: 280
		},
		{
			name: 'long-paragraph-en-4k-ish',
			content: buildLongParagraphScenario({ segments: 72 }),
			totalFlushes: 280
		}
	];

	const warmupFlushes = normalizeFlushes(
		buildFlushes(scenarios[0].content, 60),
		processResponseContent,
		replaceTokens
	);
	warmUp(
		warmupFlushes,
		chatMarked,
		shouldRenderNestedLinkTokens,
		createIncrementalTokenState,
		updateIncrementalTokenState,
		getRenderSegments
	);

	const results = scenarios.map((scenario) =>
		benchmarkScenario(
			scenario,
			processResponseContent,
			replaceTokens,
			chatMarked,
			shouldRenderNestedLinkTokens,
			createIncrementalTokenState,
			updateIncrementalTokenState,
			getRenderSegments
		)
	);

	console.log(
		`Markdown stage only: normalized content is precomputed, then full reparse is compared against the actual incremental block+inline update path. steadyStateAvgMs uses the last ${STEADY_STATE_FLUSH_WINDOW} flushes.`
	);

	console.table(
		results.map((result) => ({
			scenario: result.scenario,
			finalChars: result.finalChars,
			flushes: result.flushes,
			fullReparseAvgMs: result.fullReparse.average.toFixed(2),
			incrementalAvgMs: result.incremental.total.average.toFixed(2),
			speedupAvgX: speedup(result.fullReparse.average, result.incremental.total.average).toFixed(2),
			fullReparseSteadyStateAvgMs: result.fullReparse.steadyStateAverage.toFixed(2),
			incrementalSteadyStateAvgMs: result.incremental.total.steadyStateAverage.toFixed(2),
			speedupSteadyStateX: speedup(
				result.fullReparse.steadyStateAverage,
				result.incremental.total.steadyStateAverage
			).toFixed(2),
			incrementalBlockAvgMs: result.incremental.block.average.toFixed(2),
			incrementalInlineAvgMs: result.incremental.inline.average.toFixed(2),
			incrementalBlockSteadyStateAvgMs: result.incremental.block.steadyStateAverage.toFixed(2),
			incrementalInlineSteadyStateAvgMs: result.incremental.inline.steadyStateAverage.toFixed(2)
		}))
	);
} finally {
	await vite.close();
}
