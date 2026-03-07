<script lang="ts">
	import { toast } from 'svelte-sonner';

	import { onMount, getContext, tick, untrack } from 'svelte';
	import { models, user } from '$lib/stores';
	import { WEBUI_BASE_URL, DEFAULT_CAPABILITIES } from '$lib/constants';

	import AdvancedParams from '$lib/components/chat/Settings/Advanced/AdvancedParams.svelte';
	import Tags from '$lib/components/common/Tags.svelte';
	import Capabilities from './Capabilities.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import PromptSuggestions from './PromptSuggestions.svelte';

	const i18n = getContext('i18n');

	let { onSubmit, onBack = null, model = null, edit = false, preset = true } = $props();

	let loading = $state(false);
	let success = $state(false);

	let showAdvanced = $state(false);
	let showPreview = $state(false);

	let loaded = $state(false);

	let id = $state('');
	let name = $state('');

	let enableDescription = $state(true);

	$effect(() => {
		if (!edit) {
			if (name) {
				id = name
					.replace(/\s+/g, '-')
					.replace(/[^a-zA-Z0-9-]/g, '')
					.toLowerCase();
			}
		}
	});

	let system = $state('');
	let info = $state({
		id: '',
		base_model_id: null,
		name: '',
		meta: {
			description: '',
			suggestion_prompts: null,
			tags: []
		},
		params: {
			system: ''
		}
	});

	let params = $state({
		system: ''
	});

	let capabilities = $state({ ...DEFAULT_CAPABILITIES });

	const submitHandler = async () => {
		loading = true;

		info.id = id;
		info.name = name;

		if (id === '') {
			toast.error($i18n.t('Model ID is required.'));
			loading = false;

			return;
		}

		if (name === '') {
			toast.error($i18n.t('Model Name is required.'));
			loading = false;

			return;
		}

		info.params = { ...info.params, ...params };

		info.meta.capabilities = capabilities;

		if (enableDescription) {
			info.meta.description = info.meta.description.trim() === '' ? null : info.meta.description;
		} else {
			info.meta.description = null;
		}

		info.params.system = system.trim() === '' ? null : system;
		info.params.stop = params.stop ? params.stop.split(',').filter((s) => s.trim()) : null;
		Object.keys(info.params).forEach((key) => {
			if (info.params[key] === '' || info.params[key] === null) {
				delete info.params[key];
			}
		});

		await onSubmit(info);

		loading = false;
		success = false;
	};

	onMount(async () => {
		if (model) {
			name = model.name;
			await tick();

			id = model.id;

			enableDescription = model?.meta?.description !== null;

			if (model.base_model_id) {
				const base_model = $models
					.filter((m) => !m?.preset)
					.find((m) => [model.base_model_id, `${model.base_model_id}:latest`].includes(m.id));

				console.log('base_model', base_model);

				if (base_model) {
					model.base_model_id = base_model.id;
				} else {
					model.base_model_id = null;
				}
			}

			system = model?.params?.system ?? '';

			params = { ...params, ...model?.params };
			params.stop = params?.stop
				? (typeof params.stop === 'string' ? params.stop.split(',') : (params?.stop ?? [])).join(
						','
					)
				: null;

			capabilities = { ...capabilities, ...(model?.meta?.capabilities ?? {}) };

			info = {
				...info,
				...JSON.parse(
					JSON.stringify(
						model
							? model
							: {
									id: model.id,
									name: model.name
								}
					)
				)
			};

			console.log(model);
		}

		loaded = true;
	});
</script>

{#if loaded}
	{#if onBack}
		<button
			class="flex space-x-1"
			onclick={() => {
				onBack();
			}}
		>
			<div class=" self-center">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="h-4 w-4"
				>
					<path
						fill-rule="evenodd"
						d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
						clip-rule="evenodd"
					/>
				</svg>
			</div>
			<div class=" self-center text-sm font-medium">{$i18n.t('Back')}</div>
		</button>
	{/if}

	<div class="w-full max-h-full flex justify-center">
		{#if !edit || (edit && model)}
			<form
				class="flex flex-col md:flex-row w-full gap-3 md:gap-6"
				onsubmit={(e) => {
					e.preventDefault();
					submitHandler();
				}}
			>
				<div class="w-full px-1">
					<div class="flex flex-row gap-4 md:gap-6 w-full">
						<div class="self-start flex justify-center my-2 shrink-0">
							<img
								src="{WEBUI_BASE_URL}/static/favicon.png"
								alt="model profile"
								class="rounded-xl size-20 md:size-48 object-cover shrink-0 bg-white shadow-xl"
							/>
						</div>

						<div class="flex flex-col w-full flex-1">
							<div class="flex justify-between items-start my-2">
								<div class=" flex flex-col w-full">
									<div class="flex-1 w-full">
										<input
											class="text-3xl w-full bg-transparent outline-hidden"
											placeholder={$i18n.t('Model Name')}
											bind:value={name}
											required
										/>
									</div>

									<div class="flex-1 w-full">
										<div>
											<input
												class="text-xs w-full bg-transparent outline-hidden"
												placeholder={$i18n.t('Model ID')}
												bind:value={id}
												disabled={edit}
												required
											/>
										</div>
									</div>
								</div>
							</div>

							{#if preset}
								<div class="mb-1">
									<div class=" text-xs font-medium mb-1 text-gray-500">
										{$i18n.t('Base Model (From)')}
									</div>

									<div>
										<select
											class="text-sm w-full bg-transparent outline-hidden"
											placeholder={$i18n.t('Select a base model (e.g. llama3, gpt-4o)')}
											bind:value={info.base_model_id}
											required
										>
											<option value={null} class=" text-gray-900"
												>{$i18n.t('Select a base model')}</option
											>
											{#each $models.filter((m) => (model ? m.id !== model.id : true) && !m?.preset) as model}
												<option value={model.id} class=" text-gray-900">{model.name}</option>
											{/each}
										</select>
									</div>
								</div>
							{/if}

							<div class="mb-1">
								<div class="mb-1 flex w-full justify-between items-center">
									<div class=" self-center text-xs font-medium text-gray-500">
										{$i18n.t('Description')}
									</div>

									<button
										class="p-1 text-xs flex rounded-sm transition"
										type="button"
										aria-pressed={enableDescription ? 'true' : 'false'}
										aria-label={enableDescription
											? $i18n.t('Custom description enabled')
											: $i18n.t('Default description enabled')}
										onclick={() => {
											enableDescription = !enableDescription;
										}}
									>
										{#if !enableDescription}
											<span class="ml-2 self-center">{$i18n.t('Default')}</span>
										{:else}
											<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
										{/if}
									</button>
								</div>

								{#if enableDescription}
									<Textarea
										className=" text-sm w-full bg-transparent outline-hidden resize-none overflow-y-hidden "
										placeholder={$i18n.t('Add a short description about what this model does')}
										bind:value={info.meta.description}
									/>
								{/if}
							</div>

							<div class="w-full mb-1 max-w-full">
								<div class="">
									<Tags
										tags={info?.meta?.tags ?? []}
										on:delete={(e) => {
											const tagName = e.detail;
											info.meta.tags = info.meta.tags.filter((tag) => tag.name !== tagName);
										}}
										on:add={(e) => {
											const tagName = e.detail;
											if (!(info?.meta?.tags ?? null)) {
												info.meta.tags = [{ name: tagName }];
											} else {
												info.meta.tags = [...info.meta.tags, { name: tagName }];
											}
										}}
									/>
								</div>
							</div>
						</div>
					</div>

					<div class="my-2">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs font-medium text-gray-500">
								{$i18n.t('Model Params')}
							</div>
						</div>

						<div class="mt-2">
							<div class="my-1">
								<div class=" text-xs font-medium mb-2">{$i18n.t('System Prompt')}</div>
								<div>
									<Textarea
										className=" text-sm w-full bg-transparent outline-hidden resize-none overflow-y-hidden "
										placeholder={$i18n.t(
											'Write your model system prompt content here\ne.g.) You are Mario from Super Mario Bros, acting as an assistant.'
										)}
										rows={4}
										bind:value={system}
									/>
								</div>
							</div>

							<div class="flex w-full justify-between">
								<div class=" self-center text-xs font-medium">
									{$i18n.t('Advanced Params')}
								</div>

								<button
									class="p-1 px-3 text-xs flex rounded-sm transition"
									type="button"
									onclick={() => {
										showAdvanced = !showAdvanced;
									}}
								>
									{#if showAdvanced}
										<span class="ml-2 self-center">{$i18n.t('Hide')}</span>
									{:else}
										<span class="ml-2 self-center">{$i18n.t('Show')}</span>
									{/if}
								</button>
							</div>

							{#if showAdvanced}
								<div class="my-2">
									<AdvancedParams admin={true} custom={true} bind:params />
								</div>
							{/if}
						</div>
					</div>

					<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2" />

					<div class="my-2">
						<div class="flex w-full justify-between items-center">
							<div class="flex w-full justify-between items-center">
								<div class=" self-center text-xs font-medium text-gray-500">
									{$i18n.t('Prompts')}
								</div>

								<button
									class="p-1 text-xs flex rounded-sm transition"
									type="button"
									onclick={() => {
										if ((info?.meta?.suggestion_prompts ?? null) === null) {
											info.meta.suggestion_prompts = [{ content: '', title: ['', ''] }];
										} else {
											info.meta.suggestion_prompts = null;
										}
									}}
								>
									{#if (info?.meta?.suggestion_prompts ?? null) === null}
										<span class="ml-2 self-center">{$i18n.t('Default')}</span>
									{:else}
										<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
									{/if}
								</button>
							</div>
						</div>

						{#if info?.meta?.suggestion_prompts}
							<PromptSuggestions bind:promptSuggestions={info.meta.suggestion_prompts} />
						{/if}
					</div>

					<hr class=" border-gray-100/30 dark:border-gray-850/30 my-4" />

					<div class="my-4">
						<Capabilities bind:capabilities />
					</div>

					<hr class=" border-gray-100/30 dark:border-gray-850/30 my-4" />

					<div class="my-2 flex justify-end">
						<button
							class=" text-sm px-3 py-2 transition rounded-lg {loading
								? ' cursor-not-allowed bg-black hover:bg-gray-900 text-white dark:bg-white dark:hover:bg-gray-100 dark:text-black'
								: 'bg-black hover:bg-gray-900 text-white dark:bg-white dark:hover:bg-gray-100 dark:text-black'} flex w-full justify-center"
							type="submit"
							disabled={loading}
						>
							<div class=" self-center font-medium">
								{#if edit}
									{$i18n.t('Save & Update')}
								{:else}
									{$i18n.t('Save & Create')}
								{/if}
							</div>

							{#if loading}
								<div class="ml-1.5 self-center">
									<Spinner />
								</div>
							{/if}
						</button>
					</div>

					<div class="my-2 text-gray-300 dark:text-gray-700 pb-20">
						<div class="flex w-full justify-between mb-2">
							<div class=" self-center text-sm font-medium">{$i18n.t('JSON Preview')}</div>

							<button
								class="p-1 px-3 text-xs flex rounded-sm transition"
								type="button"
								onclick={() => {
									showPreview = !showPreview;
								}}
							>
								{#if showPreview}
									<span class="ml-2 self-center">{$i18n.t('Hide')}</span>
								{:else}
									<span class="ml-2 self-center">{$i18n.t('Show')}</span>
								{/if}
							</button>
						</div>

						{#if showPreview}
							<div>
								<textarea
									class="text-sm w-full bg-transparent outline-hidden resize-none"
									rows="10"
									value={JSON.stringify(info, null, 2)}
									disabled
									readonly
								/>
							</div>
						{/if}
					</div>
				</div>
			</form>
		{/if}
	</div>
{/if}
