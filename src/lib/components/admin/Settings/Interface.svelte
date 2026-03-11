<script lang="ts">
	import { getTaskConfig, updateTaskConfig } from '$lib/apis';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	let { onsave }: { onsave: () => void } = $props();

	const i18n = getContext('i18n');

	let taskConfig = $state(null);

	const updateInterfaceHandler = async () => {
		taskConfig = await updateTaskConfig(localStorage.token, taskConfig);
	};

	const init = async () => {
		try {
			taskConfig = await getTaskConfig(localStorage.token);
		} catch (err) {
			console.error('Failed to initialize Interface settings:', err);
			toast.error(err?.detail ?? err?.message ?? $i18n.t('Failed to load Interface settings'));
		}
	};

	onMount(async () => {
		await init();
	});
</script>

{#if taskConfig}
	<form
		class="flex flex-col h-full justify-between space-y-3 text-sm"
		onsubmit={(e) => {
			e.preventDefault();
			updateInterfaceHandler();
			onsave();
		}}
	>
		<div class="  overflow-y-scroll scrollbar-hidden h-full pr-1.5">
			<div class="mb-3.5">
				<div class=" mt-0.5 mb-2.5 text-base font-medium">{$i18n.t('Tasks')}</div>

				<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

				<div class="mb-2.5 flex w-full items-center justify-between">
					<div class=" self-center text-xs font-medium">
						{$i18n.t('Title Generation')}
					</div>

					<Switch bind:state={taskConfig.ENABLE_TITLE_GENERATION} />
				</div>

				{#if taskConfig.ENABLE_TITLE_GENERATION}
					<div class="mb-2.5">
						<div class=" mb-1 text-xs font-medium">{$i18n.t('Title Generation Prompt')}</div>

						<Tooltip
							content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
							placement="top-start"
						>
							<Textarea
								bind:value={taskConfig.TITLE_GENERATION_PROMPT_TEMPLATE}
								placeholder={$i18n.t(
									'Leave empty to use the default prompt, or enter a custom prompt'
								)}
							/>
						</Tooltip>
					</div>
				{/if}

				<div class="mb-2.5 flex w-full items-center justify-between">
					<div class=" self-center text-xs font-medium">
						{$i18n.t('Follow Up Generation')}
					</div>

					<Switch bind:state={taskConfig.ENABLE_FOLLOW_UP_GENERATION} />
				</div>

				{#if taskConfig.ENABLE_FOLLOW_UP_GENERATION}
					<div class="mb-2.5">
						<div class=" mb-1 text-xs font-medium">{$i18n.t('Follow Up Generation Prompt')}</div>

						<Tooltip
							content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
							placement="top-start"
						>
							<Textarea
								bind:value={taskConfig.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE}
								placeholder={$i18n.t(
									'Leave empty to use the default prompt, or enter a custom prompt'
								)}
							/>
						</Tooltip>
					</div>
				{/if}
			</div>
		</div>

		<div class="flex justify-end text-sm font-medium">
			<button
				class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
				type="submit"
			>
				{$i18n.t('Save')}
			</button>
		</div>
	</form>
{:else}
	<div class=" h-full w-full flex justify-center items-center">
		<Spinner className="size-5" />
	</div>
{/if}
