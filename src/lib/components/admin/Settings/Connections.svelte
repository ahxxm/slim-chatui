<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';

	import { getOpenAIConfig, updateOpenAIConfig, getOpenAIModels } from '$lib/apis/openai';
	import { getModels as _getModels, getBackendConfig } from '$lib/apis';
	import { config, models, user } from '$lib/stores';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';

	import OpenAIConnection from './Connections/OpenAIConnection.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';

	const i18n = getContext('i18n');

	let { onsave }: { onsave: () => void } = $props();

	const getModels = async () => {
		const models = await _getModels(localStorage.token, false, true);
		return models;
	};

	let OPENAI_API_KEYS = $state(['']);
	let OPENAI_API_BASE_URLS = $state(['']);
	let OPENAI_API_CONFIGS: Record<number, any> = $state({});

	let loaded = $state(false);

	let showAddOpenAIConnectionModal = $state(false);

	const updateOpenAIHandler = async () => {
		// Remove trailing slashes
		OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS.map((url) => url.replace(/\/$/, ''));

		// Check if API KEYS length is same than API URLS length
		if (OPENAI_API_KEYS.length !== OPENAI_API_BASE_URLS.length) {
			// if there are more keys than urls, remove the extra keys
			if (OPENAI_API_KEYS.length > OPENAI_API_BASE_URLS.length) {
				OPENAI_API_KEYS = OPENAI_API_KEYS.slice(0, OPENAI_API_BASE_URLS.length);
			}

			// if there are more urls than keys, add empty keys
			if (OPENAI_API_KEYS.length < OPENAI_API_BASE_URLS.length) {
				const diff = OPENAI_API_BASE_URLS.length - OPENAI_API_KEYS.length;
				for (let i = 0; i < diff; i++) {
					OPENAI_API_KEYS.push('');
				}
			}
		}

		const res = await updateOpenAIConfig(localStorage.token, {
			OPENAI_API_BASE_URLS: OPENAI_API_BASE_URLS,
			OPENAI_API_KEYS: OPENAI_API_KEYS,
			OPENAI_API_CONFIGS: OPENAI_API_CONFIGS
		}).catch((error) => {
			toast.error(`${error}`);
		});

		if (res) {
			toast.success($i18n.t('OpenAI API settings updated'));
			await models.set(await getModels());
		}
	};

	const addOpenAIConnectionHandler = async (connection) => {
		OPENAI_API_BASE_URLS = [...OPENAI_API_BASE_URLS, connection.url];
		OPENAI_API_KEYS = [...OPENAI_API_KEYS, connection.key];
		OPENAI_API_CONFIGS[OPENAI_API_BASE_URLS.length - 1] = connection.config;

		await updateOpenAIHandler();
	};

	onMount(async () => {
		if ($user?.role === 'admin') {
			let openaiConfig = {};

			openaiConfig = await getOpenAIConfig(localStorage.token);

			OPENAI_API_BASE_URLS = openaiConfig.OPENAI_API_BASE_URLS;
			OPENAI_API_KEYS = openaiConfig.OPENAI_API_KEYS;
			OPENAI_API_CONFIGS = openaiConfig.OPENAI_API_CONFIGS;

			// get url and idx
			for (const [idx, url] of OPENAI_API_BASE_URLS.entries()) {
				if (!OPENAI_API_CONFIGS[idx]) {
					// Legacy support, url as key
					OPENAI_API_CONFIGS[idx] = OPENAI_API_CONFIGS[url] || {};
				}
			}

			OPENAI_API_BASE_URLS.forEach(async (url, idx) => {
				OPENAI_API_CONFIGS[idx] = OPENAI_API_CONFIGS[idx] || {};
				if (!(OPENAI_API_CONFIGS[idx]?.enable ?? true)) {
					return;
				}
				await getOpenAIModels(localStorage.token, idx);
			});

			loaded = true;
		}
	});

	const submitHandler = async () => {
		updateOpenAIHandler();

		onsave();

		await config.set(await getBackendConfig());
	};
</script>

<AddConnectionModal
	bind:show={showAddOpenAIConnectionModal}
	onSubmit={addOpenAIConnectionHandler}
/>

<form
	class="flex flex-col h-full justify-between text-sm"
	onsubmit={(e) => {
		e.preventDefault();
		submitHandler();
	}}
>
	<div class=" overflow-y-scroll scrollbar-hidden h-full">
		{#if loaded}
			<div class="mb-3.5">
				<div class=" mt-0.5 mb-2.5 text-base font-medium">{$i18n.t('General')}</div>

				<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

				<div class="my-2">
					<div class="mt-2 space-y-2">
						<div class="flex justify-between items-center text-sm">
							<div class="  font-medium">{$i18n.t('OpenAI API')}</div>

							<Tooltip content={$i18n.t(`Add Connection`)}>
								<button
									class="px-1"
									onclick={() => {
										showAddOpenAIConnectionModal = true;
									}}
									type="button"
								>
									<Plus />
								</button>
							</Tooltip>
						</div>

						<div class="flex flex-col gap-1.5 mt-1.5">
							{#each OPENAI_API_BASE_URLS as url, idx}
								<OpenAIConnection
									bind:url={OPENAI_API_BASE_URLS[idx]}
									bind:key={OPENAI_API_KEYS[idx]}
									bind:config={OPENAI_API_CONFIGS[idx]}
									onSubmit={() => {
										updateOpenAIHandler();
									}}
									onDelete={() => {
										OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS.filter(
											(url, urlIdx) => idx !== urlIdx
										);
										OPENAI_API_KEYS = OPENAI_API_KEYS.filter((key, keyIdx) => idx !== keyIdx);

										let newConfig = {};
										OPENAI_API_BASE_URLS.forEach((url, newIdx) => {
											newConfig[newIdx] = OPENAI_API_CONFIGS[newIdx < idx ? newIdx : newIdx + 1];
										});
										OPENAI_API_CONFIGS = newConfig;
										updateOpenAIHandler();
									}}
								/>
							{/each}
						</div>
					</div>
				</div>
			</div>
		{:else}
			<div class="flex h-full justify-center">
				<div class="my-auto">
					<Spinner className="size-6" />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
