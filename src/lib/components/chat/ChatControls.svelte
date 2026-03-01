<script lang="ts">
	import { Pane, PaneResizer } from 'paneforge';

	import { onDestroy, onMount, tick } from 'svelte';
	import { mobile, showControls, showOverview, showArtifacts, showEmbeds } from '$lib/stores';

	import Controls from './Controls/Controls.svelte';
	import Drawer from '../common/Drawer.svelte';
	import Artifacts from './Artifacts.svelte';
	import Embeds from './ChatControls/Embeds.svelte';

	export let history;

	export let chatId = null;

	export let chatFiles = [];
	export let params = {};

	export let showMessage: Function;

	export let pane;

	let mediaQuery;
	let largeScreen = false;
	let dragged = false;

	let minSize = 0;

	export const openPane = () => {
		if (parseInt(localStorage?.chatControlsSize)) {
			const container = document.getElementById('chat-container');
			let size = Math.floor(
				(parseInt(localStorage?.chatControlsSize) / container.clientWidth) * 100
			);
			pane.resize(size);
		} else {
			pane.resize(minSize);
		}
	};

	const handleMediaQuery = async (e) => {
		if (e.matches) {
			largeScreen = true;
		} else {
			largeScreen = false;
			pane = null;
		}
	};

	const onMouseDown = (event) => {
		dragged = true;
	};

	const onMouseUp = (event) => {
		dragged = false;
	};

	onMount(() => {
		// listen to resize 1024px
		mediaQuery = window.matchMedia('(min-width: 1024px)');

		mediaQuery.addEventListener('change', handleMediaQuery);
		handleMediaQuery(mediaQuery);

		// Select the container element you want to observe
		const container = document.getElementById('chat-container');

		// initialize the minSize based on the container width
		minSize = Math.floor((350 / container.clientWidth) * 100);

		// Create a new ResizeObserver instance
		const resizeObserver = new ResizeObserver((entries) => {
			for (let entry of entries) {
				const width = entry.contentRect.width;
				// calculate the percentage of 350px
				const percentage = (350 / width) * 100;
				// set the minSize to the percentage, must be an integer
				minSize = Math.floor(percentage);

				if ($showControls) {
					if (pane && pane.isExpanded() && pane.getSize() < minSize) {
						pane.resize(minSize);
					} else {
						let size = Math.floor(
							(parseInt(localStorage?.chatControlsSize) / container.clientWidth) * 100
						);
						if (size < minSize) {
							pane.resize(minSize);
						}
					}
				}
			}
		});

		// Start observing the container's size changes
		resizeObserver.observe(container);

		document.addEventListener('mousedown', onMouseDown);
		document.addEventListener('mouseup', onMouseUp);
	});

	onDestroy(() => {
		showControls.set(false);

		mediaQuery.removeEventListener('change', handleMediaQuery);
		document.removeEventListener('mousedown', onMouseDown);
		document.removeEventListener('mouseup', onMouseUp);
	});

	const closeHandler = () => {
		showControls.set(false);
		showOverview.set(false);
		showArtifacts.set(false);
		showEmbeds.set(false);
	};

	$: if (!chatId) {
		closeHandler();
	}
</script>

{#if !largeScreen}
	{#if $showControls}
		<Drawer
			show={$showControls}
			onClose={() => {
				showControls.set(false);
			}}
		>
			<div
				class=" {$showOverview || $showArtifacts || $showEmbeds
					? ' h-screen  w-full'
					: 'px-4 py-3'} h-full"
			>
				{#if $showEmbeds}
					<Embeds />
				{:else if $showArtifacts}
					<Artifacts {history} />
				{:else if $showOverview}
					{#await import('./Overview.svelte') then { default: Overview }}
						<Overview
							{history}
							onNodeClick={(e) => {
								const node = e.node;
								showMessage(node.data.message, true);
							}}
							onClose={() => {
								showControls.set(false);
							}}
						/>
					{/await}
				{:else}
					<Controls
						on:close={() => {
							showControls.set(false);
						}}
						bind:chatFiles
						bind:params
					/>
				{/if}
			</div>
		</Drawer>
	{/if}
{:else}
	<!-- if $showControls -->

	{#if $showControls}
		<PaneResizer
			class="relative flex items-center justify-center group border-l border-gray-50 dark:border-gray-850/30 hover:border-gray-200 dark:hover:border-gray-800  transition z-20"
			id="controls-resizer"
		>
			<div
				class=" absolute -left-1.5 -right-1.5 -top-0 -bottom-0 z-20 cursor-col-resize bg-transparent"
			/>
		</PaneResizer>
	{/if}

	<Pane
		bind:pane
		defaultSize={0}
		onResize={(size) => {
			if ($showControls && pane.isExpanded()) {
				if (size < minSize) {
					pane.resize(minSize);
				}

				if (size < minSize) {
					localStorage.chatControlsSize = 0;
				} else {
					// save the size in  pixels to localStorage
					const container = document.getElementById('chat-container');
					localStorage.chatControlsSize = Math.floor((size / 100) * container.clientWidth);
				}
			}
		}}
		onCollapse={() => {
			showControls.set(false);
		}}
		collapsible={true}
		class=" z-10 bg-white dark:bg-gray-850"
	>
		{#if $showControls}
			<div class="flex max-h-full min-h-full">
				<div
					class="w-full {$showOverview || $showArtifacts || $showEmbeds
						? ' '
						: 'px-4 py-3 bg-white dark:shadow-lg dark:bg-gray-850 '} z-40 pointer-events-auto overflow-y-auto scrollbar-hidden"
					id="controls-container"
				>
					{#if $showEmbeds}
						<Embeds overlay={dragged} />
					{:else if $showArtifacts}
						<Artifacts {history} overlay={dragged} />
					{:else if $showOverview}
						{#await import('./Overview.svelte') then { default: Overview }}
							<Overview
								{history}
								onNodeClick={(e) => {
									const node = e.node;
									if (node?.data?.message?.favorite) {
										history.messages[node.data.message.id].favorite = true;
									} else {
										history.messages[node.data.message.id].favorite = null;
									}

									showMessage(node.data.message, true);
								}}
								onClose={() => {
									showControls.set(false);
								}}
							/>
						{/await}
					{:else}
						<Controls
							on:close={() => {
								showControls.set(false);
							}}
							bind:chatFiles
							bind:params
						/>
					{/if}
				</div>
			</div>
		{/if}
	</Pane>
{/if}
