<script lang="ts">
	import Plus from '$lib/components/icons/Plus.svelte';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	const defaultParams = {};

	let {
		onChange = (params: any) => {},
		admin = false,
		custom = false,
		params = $bindable(defaultParams)
	} = $props();

	$effect(() => {
		if (params) {
			onChange(params);
		}
	});
</script>

<div class=" space-y-1 text-xs pb-safe-bottom">
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
								onchange={(e) => {
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
							onclick={() => {
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
				onclick={() => {
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
