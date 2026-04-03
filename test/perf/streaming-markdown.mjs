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

function buildSampleSection(sectionNumber) {
	return [
		`## Section ${sectionNumber}`,
		`This response explains **trade-offs**, includes _emphasis_, inline code like \`const value = ${sectionNumber};\`, and a citation [^${sectionNumber}] for reference.`,
		'',
		'- First point with a [link](https://example.com/docs).',
		'- Second point with math $E = mc^2$ and a placeholder for {{char}} talking to {{user}}.',
		'- Third point with nested detail and a short quote.',
		'',
		'| Column | Value | Notes |',
		'| --- | ---: | --- |',
		`| Iteration | ${sectionNumber} | Stable markdown table row |`,
		'| Status | active | Streaming re-parse benchmark |',
		'',
		'```python',
		'def fibonacci(limit: int) -> list[int]:',
		'    numbers = [0, 1]',
		'    while len(numbers) < limit:',
		'        numbers.append(numbers[-1] + numbers[-2])',
		'    return numbers[:limit]',
		'',
		`print(fibonacci(${10 + (sectionNumber % 5)}))`,
		'```',
		'',
		`[^${sectionNumber}]: Footnote ${sectionNumber} with extra explanation and some repeated prose to keep the content realistic.`
	].join('\n');
}

function buildScenario({ sections, includeChinese = false }) {
	const parts = [];

	for (let sectionNumber = 1; sectionNumber <= sections; sectionNumber += 1) {
		parts.push(buildSampleSection(sectionNumber));

		if (includeChinese) {
			parts.push(`中文段落 ${sectionNumber}：**中文名（English）**中文内容，以及一些额外说明。`);
		}

		parts.push('');
	}

	return parts.join('\n');
}

function buildFlushes(content, totalFlushes) {
	const flushes = [];

	for (let flushIndex = 1; flushIndex <= totalFlushes; flushIndex += 1) {
		const end = Math.max(1, Math.floor((content.length * flushIndex) / totalFlushes));
		flushes.push(content.slice(0, end));
	}

	return flushes;
}

function summarize(times) {
	const total = times.reduce((sum, value) => sum + value, 0);

	return {
		total,
		average: total / times.length,
		p95: percentile(times, 95),
		max: Math.max(...times),
		last: times.at(-1)
	};
}

function benchmarkScenario({
	name,
	content,
	flushes,
	processResponseContent,
	replaceTokens,
	chatMarked
}) {
	const processTimes = [];
	const replaceTimes = [];
	const lexerTimes = [];
	const totalTimes = [];

	for (const partialContent of flushes) {
		const totalStart = performance.now();

		const processStart = performance.now();
		const processedContent = processResponseContent(partialContent);
		processTimes.push(performance.now() - processStart);

		const replaceStart = performance.now();
		const replacedContent = replaceTokens(processedContent, 'Assistant', 'User');
		replaceTimes.push(performance.now() - replaceStart);

		const lexerStart = performance.now();
		chatMarked.lexer(replacedContent);
		lexerTimes.push(performance.now() - lexerStart);

		totalTimes.push(performance.now() - totalStart);
	}

	return {
		name,
		finalChars: content.length,
		flushes: flushes.length,
		process: summarize(processTimes),
		replace: summarize(replaceTimes),
		lexer: summarize(lexerTimes),
		total: summarize(totalTimes)
	};
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
	const { processResponseContent, replaceTokens } = utils;
	const { chatMarked } = marked;

	const scenarios = [
		{
			name: 'rich-markdown-en-2k-ish',
			content: buildScenario({ sections: 18 }),
			totalFlushes: 280
		},
		{
			name: 'rich-markdown-en-4k-ish',
			content: buildScenario({ sections: 36 }),
			totalFlushes: 280
		},
		{
			name: 'rich-markdown-han-2k-ish',
			content: buildScenario({ sections: 18, includeChinese: true }),
			totalFlushes: 280
		},
		{
			name: 'rich-markdown-han-4k-ish',
			content: buildScenario({ sections: 36, includeChinese: true }),
			totalFlushes: 280
		}
	];

	for (const partialContent of buildFlushes(scenarios[0].content, 60)) {
		chatMarked.lexer(replaceTokens(processResponseContent(partialContent), 'Assistant', 'User'));
	}

	const results = scenarios.map((scenario) =>
		benchmarkScenario({
			name: scenario.name,
			content: scenario.content,
			flushes: buildFlushes(scenario.content, scenario.totalFlushes),
			processResponseContent,
			replaceTokens,
			chatMarked
		})
	);

	console.table(
		results.map((result) => ({
			scenario: result.name,
			finalChars: result.finalChars,
			flushes: result.flushes,
			totalAvgMs: result.total.average.toFixed(2),
			totalP95Ms: result.total.p95.toFixed(2),
			totalMaxMs: result.total.max.toFixed(2),
			totalLastMs: result.total.last.toFixed(2),
			lexerAvgMs: result.lexer.average.toFixed(2),
			lexerP95Ms: result.lexer.p95.toFixed(2),
			lexerLastMs: result.lexer.last.toFixed(2)
		}))
	);
} finally {
	await vite.close();
}
