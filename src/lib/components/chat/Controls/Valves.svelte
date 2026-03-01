<script lang="ts">
	import { toast } from 'svelte-sonner';

	import { functions } from '$lib/stores';
	import { createEventDispatcher, getContext, tick } from 'svelte';

	import {
		getUserValvesSpecById as getFunctionUserValvesSpecById,
		getUserValvesById as getFunctionUserValvesById,
		updateUserValvesById as updateFunctionUserValvesById,
		getFunctions
	} from '$lib/apis/functions';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Valves from '$lib/components/common/Valves.svelte';

	const dispatch = createEventDispatcher();

	const i18n = getContext('i18n');

	export let show = false;

	let selectedId = '';

	let loading = false;

	let valvesSpec = null;
	let valves = {};

	let debounceTimer;

	const debounceSubmitHandler = async () => {
		if (debounceTimer) {
			clearTimeout(debounceTimer);
		}

		// Set a new timer
		debounceTimer = setTimeout(() => {
			submitHandler();
		}, 500); // 0.5 second debounce
	};

	const getUserValves = async () => {
		loading = true;
		valves = await getFunctionUserValvesById(localStorage.token, selectedId);
		valvesSpec = await getFunctionUserValvesSpecById(localStorage.token, selectedId);

		if (valvesSpec) {
			// Convert array to string
			for (const property in valvesSpec.properties) {
				if (valvesSpec.properties[property]?.type === 'array') {
					valves[property] = (valves[property] ?? []).join(',');
				}
			}
		}

		loading = false;
	};

	const submitHandler = async () => {
		if (valvesSpec) {
			// Convert string to array
			for (const property in valvesSpec.properties) {
				if (valvesSpec.properties[property]?.type === 'array') {
					valves[property] = (valves[property] ?? '').split(',').map((v) => v.trim());
				}
			}

			const res = await updateFunctionUserValvesById(localStorage.token, selectedId, valves).catch(
				(error) => {
					toast.error(`${error}`);
					return null;
				}
			);

			if (res) {
				toast.success($i18n.t('Valves updated'));
				valves = res;
			}
		}
	};

	$: if (selectedId) {
		getUserValves();
	}

	$: if (show) {
		init();
	}

	const init = async () => {
		loading = true;

		if ($functions === null) {
			functions.set(await getFunctions(localStorage.token));
		}

		loading = false;
	};
</script>

{#if show && !loading}
	<form
		class="flex flex-col h-full justify-between space-y-3 text-sm"
		on:submit|preventDefault={() => {
			submitHandler();
			dispatch('save');
		}}
	>
		<div class="flex flex-col">
			<div class="space-y-1">
				<div>
					<select
						class="w-full rounded-sm py-2 px-1 text-xs bg-transparent outline-hidden"
						bind:value={selectedId}
						on:change={async () => {
							await tick();
						}}
					>
						<option value="" selected disabled class="bg-gray-100 dark:bg-gray-800"
							>{$i18n.t('Select a function')}</option
						>

						{#each ($functions ?? []).sort( (a, b) => (a.name ?? '').localeCompare(b.name ?? '') ) as func, funcIdx}
							<option value={func.id} class="bg-gray-100 dark:bg-gray-800">{func.name}</option>
						{/each}
					</select>
				</div>
			</div>

			{#if selectedId}
				<hr class="border-gray-50/30 dark:border-gray-800/30 my-1 w-full" />

				<div class="my-2 text-xs">
					{#if !loading}
						<Valves
							{valvesSpec}
							bind:valves
							on:change={() => {
								debounceSubmitHandler();
							}}
						/>
					{:else}
						<Spinner className="size-5" />
					{/if}
				</div>
			{/if}
		</div>
	</form>
{:else}
	<Spinner className="size-4" />
{/if}
