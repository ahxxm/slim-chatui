<script lang="ts">
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let onChange: (params: any) => void = () => {};

	export let admin = false;
	export let custom = false;

	const defaultParams = {
		stream_delta_chunk_size: null,
		reasoning_tags: null,
		seed: null,
		stop: null,
		temperature: null,
		reasoning_effort: null,
		logit_bias: null,
		max_tokens: null,
		top_p: null,
	};

	export let params = defaultParams;
	$: if (params) {
		onChange(params);
	}
</script>

<div class=" space-y-1 text-xs pb-safe-bottom">
	{#if admin}
		<div>
			<Tooltip
				content={$i18n.t(
					'The stream delta chunk size for the model. Increasing the chunk size will make the model respond with larger pieces of text at once.'
				)}
				placement="top-start"
				className="inline-tooltip"
			>
				<div class="flex w-full justify-between">
					<div class=" self-center text-xs font-medium">
						{$i18n.t('Stream Delta Chunk Size')}
					</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
						type="button"
						on:click={() => {
							params.stream_delta_chunk_size =
								(params?.stream_delta_chunk_size ?? null) === null ? 1 : null;
						}}
					>
						{#if (params?.stream_delta_chunk_size ?? null) === null}
							<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
						{:else}
							<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
						{/if}
					</button>
				</div>
			</Tooltip>

			{#if (params?.stream_delta_chunk_size ?? null) !== null}
				<div class="flex mt-0.5 space-x-2">
					<div class=" flex-1">
						<input
							id="steps-range"
							type="range"
							min="1"
							max="128"
							step="1"
							bind:value={params.stream_delta_chunk_size}
							class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
						/>
					</div>
					<div>
						<input
							bind:value={params.stream_delta_chunk_size}
							type="number"
							class=" bg-transparent text-center w-14"
							min="1"
							step="any"
						/>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Enable, disable, or customize the reasoning tags used by the model. "Enabled" uses default tags, "Disabled" turns off reasoning tags, and "Custom" lets you specify your own start and end tags.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{$i18n.t('Reasoning Tags')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						if ((params?.reasoning_tags ?? null) === null) {
							params.reasoning_tags = ['', ''];
						} else if ((params?.reasoning_tags ?? []).length === 2) {
							params.reasoning_tags = true;
						} else if ((params?.reasoning_tags ?? null) !== false) {
							params.reasoning_tags = false;
						} else {
							params.reasoning_tags = null;
						}
					}}
				>
					{#if (params?.reasoning_tags ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else if (params?.reasoning_tags ?? null) === true}
						<span class="ml-2 self-center"> {$i18n.t('Enabled')} </span>
					{:else if (params?.reasoning_tags ?? null) === false}
						<span class="ml-2 self-center"> {$i18n.t('Disabled')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if ![true, false, null].includes(params?.reasoning_tags ?? null) && (params?.reasoning_tags ?? []).length === 2}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="text-sm w-full bg-transparent outline-hidden outline-none"
						type="text"
						placeholder={$i18n.t('Start Tag')}
						bind:value={params.reasoning_tags[0]}
						autocomplete="off"
					/>
				</div>

				<div class=" flex-1">
					<input
						class="text-sm w-full bg-transparent outline-hidden outline-none"
						type="text"
						placeholder={$i18n.t('End Tag')}
						bind:value={params.reasoning_tags[1]}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Sets the random number seed to use for generation. Setting this to a specific number will make the model generate the same text for the same prompt.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{$i18n.t('Seed')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.seed = (params?.seed ?? null) === null ? 0 : null;
					}}
				>
					{#if (params?.seed ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.seed ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="text-sm w-full bg-transparent outline-hidden outline-none"
						type="number"
						placeholder={$i18n.t('Enter Seed')}
						bind:value={params.seed}
						autocomplete="off"
						min="0"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Sets the stop sequences to use. When this pattern is encountered, the LLM will stop generating text and return. Multiple stop patterns may be set by specifying multiple separate stop parameters in a modelfile.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{$i18n.t('Stop Sequence')}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.stop = (params?.stop ?? null) === null ? '' : null;
					}}
				>
					{#if (params?.stop ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.stop ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="text-sm w-full bg-transparent outline-hidden outline-none"
						type="text"
						placeholder={$i18n.t('Enter stop sequence')}
						bind:value={params.stop}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'The temperature of the model. Increasing the temperature will make the model answer more creatively.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{$i18n.t('Temperature')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.temperature = (params?.temperature ?? null) === null ? 0.8 : null;
					}}
				>
					{#if (params?.temperature ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.temperature ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="0.05"
						bind:value={params.temperature}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.temperature}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Constrains effort on reasoning for reasoning models. Only applicable to reasoning models from specific providers that support reasoning effort.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{$i18n.t('Reasoning Effort')}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.reasoning_effort = (params?.reasoning_effort ?? null) === null ? 'medium' : null;
					}}
				>
					{#if (params?.reasoning_effort ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.reasoning_effort ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="text-sm w-full bg-transparent outline-hidden outline-none"
						type="text"
						placeholder={$i18n.t('Enter reasoning effort')}
						bind:value={params.reasoning_effort}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'Boosting or penalizing specific tokens for constrained responses. Bias values will be clamped between -100 and 100 (inclusive). (Default: none)'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{'logit_bias'}
				</div>
				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.logit_bias = (params?.logit_bias ?? null) === null ? '' : null;
					}}
				>
					{#if (params?.logit_bias ?? null) === null}
						<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
					{:else}
						<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.logit_bias ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="text-sm w-full bg-transparent outline-hidden outline-none"
						type="text"
						placeholder={$i18n.t(
							'Enter comma-separated "token:bias_value" pairs (example: 5432:100, 413:-100)'
						)}
						bind:value={params.logit_bias}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'This option sets the maximum number of tokens the model can generate in its response. Increasing this limit allows the model to provide longer answers, but it may also increase the likelihood of unhelpful or irrelevant content being generated.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{'max_tokens'}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.max_tokens = (params?.max_tokens ?? null) === null ? 128 : null;
					}}
				>
					{#if (params?.max_tokens ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.max_tokens ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-2"
						max="131072"
						step="1"
						bind:value={params.max_tokens}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.max_tokens}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-2"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<Tooltip
			content={$i18n.t(
				'A higher value (e.g., 0.95) will lead to more diverse text, while a lower value (e.g., 0.5) will generate more focused and conservative text.'
			)}
			placement="top-start"
			className="inline-tooltip"
		>
			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">
					{'top_p'}
				</div>

				<button
					class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
					type="button"
					on:click={() => {
						params.top_p = (params?.top_p ?? null) === null ? 0.9 : null;
					}}
				>
					{#if (params?.top_p ?? null) === null}
						<span class="ml-2 self-center">{$i18n.t('Default')}</span>
					{:else}
						<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
					{/if}
				</button>
			</div>
		</Tooltip>

		{#if (params?.top_p ?? null) !== null}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.top_p}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.top_p}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="any"
					/>
				</div>
			</div>
		{/if}
	</div>

	{#if custom && admin}
		<div class="flex flex-col justify-center">
			{#each Object.keys(params?.custom_params ?? {}) as key}
				<div class=" py-0.5 w-full justify-between mb-1">
					<div class="flex w-full justify-between">
						<div class=" self-center text-xs font-medium">
							<input
								type="text"
								class=" text-xs w-full bg-transparent outline-none"
								placeholder={$i18n.t('Custom Parameter Name')}
								value={key}
								on:change={(e) => {
									const newKey = e.target.value.trim();
									if (newKey && newKey !== key) {
										params.custom_params[newKey] = params.custom_params[key];
										delete params.custom_params[key];
										params = {
											...params,
											custom_params: { ...params.custom_params }
										};
									}
								}}
							/>
						</div>
						<button
							class="p-1 px-3 text-xs flex rounded-sm transition shrink-0 outline-hidden"
							type="button"
							on:click={() => {
								delete params.custom_params[key];
								params = {
									...params,
									custom_params: { ...params.custom_params }
								};
							}}
						>
							{$i18n.t('Remove')}
						</button>
					</div>
					<div class="flex mt-0.5 space-x-2">
						<div class=" flex-1">
							<input
								bind:value={params.custom_params[key]}
								type="text"
								class="text-sm w-full bg-transparent outline-hidden outline-none"
								placeholder={$i18n.t('Custom Parameter Value')}
							/>
						</div>
					</div>
				</div>
			{/each}

			<button
				class=" flex gap-2 items-center w-full text-center justify-center mt-1 mb-5"
				type="button"
				on:click={() => {
					params.custom_params = (params?.custom_params ?? {}) || {};
					params.custom_params['custom_param_name'] = 'custom_param_value';
				}}
			>
				<div>
					<Plus />
				</div>
				<div>{$i18n.t('Add Custom Parameter')}</div>
			</button>
		</div>
	{/if}
</div>
