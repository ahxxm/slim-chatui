<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext, onMount, untrack } from 'svelte';
	const i18n = getContext('i18n');

	import { settings } from '$lib/stores';
	import { verifyOpenAIConnection } from '$lib/apis/openai';

	import Modal from '$lib/components/common/Modal.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import Minus from '$lib/components/icons/Minus.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Textarea from './common/Textarea.svelte';

	let {
		onSubmit = () => {},
		onDelete = () => {},
		show = $bindable(false),
		edit = false,
		connection = null
	}: {
		onSubmit?: Function;
		onDelete?: Function;
		show?: boolean;
		edit?: boolean;
		connection?: any;
	} = $props();

	let url = $state('');
	let key = $state('');
	let auth_type = $state('bearer');

	let prefixId = $state('');
	let enable = $state(true);
	let apiType = $state(''); // '' = chat completions (default), 'responses' = Responses API

	let headers = $state('');

	let modelId = $state('');
	let modelIds: string[] = $state([]);

	let loading = $state(false);

	const verifyOpenAIHandler = async () => {
		// remove trailing slash from url
		url = url.replace(/\/$/, '');

		let _headers = null;

		if (headers) {
			try {
				_headers = JSON.parse(headers);
				if (typeof _headers !== 'object' || Array.isArray(_headers)) {
					_headers = null;
					throw new Error('Headers must be a valid JSON object');
				}
				headers = JSON.stringify(_headers, null, 2);
			} catch (error) {
				toast.error($i18n.t('Headers must be a valid JSON object'));
				return;
			}
		}

		const res = await verifyOpenAIConnection(localStorage.token, {
			url,
			key,
			config: {
				auth_type,
				...(_headers ? { headers: _headers } : {})
			}
		}).catch((error) => {
			toast.error(`${error}`);
		});

		if (res) {
			toast.success($i18n.t('Server connection verified'));
		}
	};

	const addModelHandler = () => {
		if (modelId) {
			modelIds = [...modelIds, modelId];
			modelId = '';
		}
	};

	const submitHandler = async () => {
		loading = true;

		if (!url) {
			loading = false;
			toast.error($i18n.t('URL is required'));
			return;
		}

		if (headers) {
			try {
				const _headers = JSON.parse(headers);
				if (typeof _headers !== 'object' || Array.isArray(_headers)) {
					throw new Error('Headers must be a valid JSON object');
				}
				headers = JSON.stringify(_headers, null, 2);
			} catch (error) {
				toast.error($i18n.t('Headers must be a valid JSON object'));
				return;
			}
		}

		// remove trailing slash from url
		url = url.replace(/\/$/, '');

		const connection = {
			url,
			key,
			config: {
				enable: enable,
				prefix_id: prefixId,
				model_ids: modelIds,
				auth_type,
				headers: headers ? JSON.parse(headers) : undefined,
				...(apiType ? { api_type: apiType } : {})
			}
		};

		await onSubmit(connection);

		loading = false;
		show = false;

		url = '';
		key = '';
		auth_type = 'bearer';
		prefixId = '';
		modelIds = [];
	};

	const init = () => {
		if (connection) {
			url = connection.url;
			key = connection.key;

			auth_type = connection.config.auth_type ?? 'bearer';
			headers = connection.config?.headers
				? JSON.stringify(connection.config.headers, null, 2)
				: '';

			enable = connection.config?.enable ?? true;
			prefixId = connection.config?.prefix_id ?? '';
			modelIds = connection.config?.model_ids ?? [];

			apiType = connection.config?.api_type ?? '';
		}
	};

	$effect(() => {
		if (show) {
			untrack(() => init());
		}
	});

	onMount(() => {
		init();
	});
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-100 px-5 pt-4 pb-1.5">
			<h1 class="text-lg font-medium self-center font-primary">
				{#if edit}
					{$i18n.t('Edit Connection')}
				{:else}
					{$i18n.t('Add Connection')}
				{/if}
			</h1>
			<button
				class="self-center"
				aria-label={$i18n.t('Close modal')}
				onclick={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full px-4 pb-4 md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<form
					class="flex flex-col w-full"
					onsubmit={(e) => {
						e.preventDefault();
						submitHandler();
					}}
				>
					<div class="px-1">
						<div class="flex gap-2 mt-1.5">
							<div class="flex flex-col w-full">
								<label
									for="url-input"
									class={`mb-0.5 text-xs text-gray-500
								${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : ''}`}
									>{$i18n.t('URL')}</label
								>

								<div class="flex-1">
									<input
										id="url-input"
										class={`w-full text-sm bg-transparent ${($settings?.highContrastMode ?? false) ? 'placeholder:text-gray-700 dark:placeholder:text-gray-100' : 'outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700'}`}
										type="text"
										bind:value={url}
										placeholder={$i18n.t('API Base URL')}
										autocomplete="off"
										list="suggestions"
										required
									/>

									<datalist id="suggestions">
										<option value="https://api.openai.com/v1" />
										<option value="https://api.anthropic.com/v1" />
										<option value="https://generativelanguage.googleapis.com/v1beta/openai" />
										<option value="https://api.mistral.ai/v1" />
										<option value="https://api.groq.com/openai/v1" />
										<option value="https://openrouter.ai/api/v1" />
										<option value="https://api.x.ai/v1" />
									</datalist>
								</div>
							</div>

							<Tooltip content={$i18n.t('Verify Connection')} className="self-end -mb-1">
								<button
									class="self-center p-1 bg-transparent hover:bg-gray-100 dark:hover:bg-gray-850 rounded-lg transition"
									onclick={() => {
										verifyOpenAIHandler();
									}}
									type="button"
									aria-label={$i18n.t('Verify Connection')}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										aria-hidden="true"
										class="w-4 h-4"
									>
										<path
											fill-rule="evenodd"
											d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.39zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0V5.36l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z"
											clip-rule="evenodd"
										/>
									</svg>
								</button>
							</Tooltip>

							<div class="flex flex-col shrink-0 self-end">
								<label class="sr-only" for="toggle-connection"
									>{$i18n.t('Toggle whether current connection is active.')}</label
								>
								<Tooltip content={enable ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
									<Switch id="toggle-connection" bind:state={enable} />
								</Tooltip>
							</div>
						</div>

						<div class="flex gap-2 mt-2">
							<div class="flex flex-col w-full">
								<label
									for="select-bearer-or-session"
									class={`text-xs ${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : 'text-gray-500'}`}
									>{$i18n.t('Auth')}</label
								>

								<div class="flex gap-2">
									<div class="flex-shrink-0 self-start">
										<select
											id="select-bearer-or-session"
											class={`dark:bg-gray-900 w-full text-sm bg-transparent pr-5 ${($settings?.highContrastMode ?? false) ? 'placeholder:text-gray-700 dark:placeholder:text-gray-100' : 'outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700'}`}
											bind:value={auth_type}
										>
											<option value="none">{$i18n.t('None')}</option>
											<option value="bearer">{$i18n.t('Bearer')}</option>
											<option value="session">{$i18n.t('Session')}</option>
										</select>
									</div>

									<div class="flex flex-1 items-center">
										{#if auth_type === 'bearer'}
											<SensitiveInput
												bind:value={key}
												placeholder={$i18n.t('API Key')}
												required={false}
											/>
										{:else if auth_type === 'none'}
											<div
												class={`text-xs self-center translate-y-[1px] ${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : 'text-gray-500'}`}
											>
												{$i18n.t('No authentication')}
											</div>
										{:else if auth_type === 'session'}
											<div
												class={`text-xs self-center translate-y-[1px] ${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : 'text-gray-500'}`}
											>
												{$i18n.t('Forwards system user session credentials to authenticate')}
											</div>
										{/if}
									</div>
								</div>
							</div>
						</div>

						<div class="flex gap-2 mt-2">
							<div class="flex flex-col w-full">
								<label
									for="headers-input"
									class={`mb-0.5 text-xs text-gray-500
								${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : ''}`}
									>{$i18n.t('Headers')}</label
								>

								<div class="flex-1">
									<Tooltip
										content={$i18n.t(
											'Enter additional headers in JSON format (e.g. {"X-Custom-Header": "value"}'
										)}
									>
										<Textarea
											className="w-full text-sm outline-hidden"
											bind:value={headers}
											placeholder={$i18n.t('Enter additional headers in JSON format')}
											required={false}
											minSize={30}
										/>
									</Tooltip>
								</div>
							</div>
						</div>

						<div class="flex gap-2 mt-2">
							<div class="flex flex-col w-full">
								<label
									for="prefix-id-input"
									class={`mb-0.5 text-xs text-gray-500
								${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : ''}`}
									>{$i18n.t('Prefix ID')}</label
								>

								<div class="flex-1">
									<Tooltip
										content={$i18n.t(
											'Prefix ID is used to avoid conflicts with other connections by adding a prefix to the model IDs - leave empty to disable'
										)}
									>
										<input
											class={`w-full text-sm bg-transparent ${($settings?.highContrastMode ?? false) ? 'placeholder:text-gray-700 dark:placeholder:text-gray-100' : 'outline-hidden placeholder:text-gray-300 dark:placeholder:text-gray-700'}`}
											type="text"
											id="prefix-id-input"
											bind:value={prefixId}
											placeholder={$i18n.t('Prefix ID')}
											autocomplete="off"
										/>
									</Tooltip>
								</div>
							</div>
						</div>

						<div class="flex flex-row justify-between items-center w-full mt-1">
							<label
								for="api-type-toggle"
								class={`mb-0.5 text-xs text-gray-500
							${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : ''}`}
								>{$i18n.t('API Type')}</label
							>

							<div>
								<button
									onclick={() => {
										apiType = apiType === 'responses' ? '' : 'responses';
									}}
									type="button"
									id="api-type-toggle"
									class=" text-xs text-gray-700 dark:text-gray-300"
								>
									{#if apiType === 'responses'}
										<Tooltip
											className="flex items-center gap-1"
											content={$i18n.t(
												'This feature is currently experimental and may not work as expected.'
											)}
										>
											<span class=" text-gray-400 dark:text-gray-600"
												>{$i18n.t('Experimental')}</span
											>

											{$i18n.t('Responses')}
										</Tooltip>
									{:else}
										{$i18n.t('Chat Completions')}
									{/if}
								</button>
							</div>
						</div>

						<div class="flex flex-col w-full mt-2">
							<div class="mb-1 flex justify-between">
								<div
									class={`mb-0.5 text-xs text-gray-500
								${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : ''}`}
								>
									{$i18n.t('Model IDs')}
								</div>
							</div>

							{#if modelIds.length > 0}
								<ul class="flex flex-col">
									{#each modelIds as modelId, modelIdx}
										<li class=" flex gap-2 w-full justify-between items-center">
											<div class=" text-sm flex-1 py-1 rounded-lg">
												{modelId}
											</div>
											<div class="shrink-0">
												<button
													aria-label={$i18n.t(`Remove {{MODELID}} from list.`, {
														MODELID: modelId
													})}
													type="button"
													onclick={() => {
														modelIds = modelIds.filter((_, idx) => idx !== modelIdx);
													}}
												>
													<Minus strokeWidth="2" className="size-3.5" />
												</button>
											</div>
										</li>
									{/each}
								</ul>
							{:else}
								<div
									class={`text-gray-500 text-xs text-center py-2 px-10
								${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : ''}`}
								>
									{$i18n.t('Leave empty to include all models from "{{url}}/models" endpoint', {
										url: url
									})}
								</div>
							{/if}
						</div>

						<div class="flex items-center">
							<label class="sr-only" for="add-model-id-input">{$i18n.t('Add a model ID')}</label>
							<input
								class="w-full py-1 text-sm rounded-lg bg-transparent {modelId
									? ''
									: 'text-gray-500'} {($settings?.highContrastMode ?? false)
									? 'dark:placeholder:text-gray-100 placeholder:text-gray-700'
									: 'placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-hidden'}"
								bind:value={modelId}
								id="add-model-id-input"
								placeholder={$i18n.t('Add a model ID')}
							/>

							<div>
								<button
									type="button"
									aria-label={$i18n.t('Add')}
									onclick={() => {
										addModelHandler();
									}}
								>
									<Plus className="size-3.5" strokeWidth="2" />
								</button>
							</div>
						</div>
					</div>

					<div class="flex justify-end pt-3 text-sm font-medium gap-1.5">
						{#if edit}
							<button
								class="px-3.5 py-1.5 text-sm font-medium dark:bg-black dark:hover:bg-gray-900 dark:text-white bg-white text-black hover:bg-gray-100 transition rounded-full flex flex-row space-x-1 items-center"
								type="button"
								onclick={() => {
									onDelete();
									show = false;
								}}
							>
								{$i18n.t('Delete')}
							</button>
						{/if}

						<button
							class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full flex flex-row space-x-1 items-center {loading
								? ' cursor-not-allowed'
								: ''}"
							type="submit"
							disabled={loading}
						>
							{$i18n.t('Save')}

							{#if loading}
								<div class="ml-2 self-center">
									<Spinner />
								</div>
							{/if}
						</button>
					</div>
				</form>
			</div>
		</div>
	</div>
</Modal>
