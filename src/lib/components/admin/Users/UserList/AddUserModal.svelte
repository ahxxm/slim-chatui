<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { untrack, getContext } from 'svelte';
	import { addUser } from '$lib/apis/auths';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	const i18n = getContext('i18n');

	let {
		show = $bindable(false),
		onsave
	}: {
		show?: boolean;
		onsave: () => void;
	} = $props();

	let loading = $state(false);

	let _user = $state({
		name: '',
		email: '',
		password: '',
		role: 'user'
	});

	$effect(() => {
		if (show) {
			untrack(() => {
				_user = {
					name: '',
					email: '',
					password: '',
					role: 'user'
				};
			});
		}
	});

	const submitHandler = async () => {
		loading = true;

		const res = await addUser(
			localStorage.token,
			_user.name,
			_user.email,
			_user.password,
			_user.role
		).catch((error) => {
			toast.error(`${error}`);
		});

		loading = false;

		if (res) {
			onsave();
			show = false;
		}
	};
</script>

<Modal size="sm" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class=" text-lg font-medium self-center">{$i18n.t('Add User')}</div>
			<button
				class="self-center"
				aria-label={$i18n.t('Close')}
				onclick={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full px-4 pb-3 md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<form
					class="flex flex-col w-full"
					onsubmit={(e) => {
						e.preventDefault();
						submitHandler();
					}}
				>
					<div class="px-1">
						<div class="flex flex-col w-full mb-3">
							<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Role')}</div>

							<div class="flex-1">
								<select
									class="w-full capitalize rounded-lg text-sm bg-transparent dark:disabled:text-gray-500 outline-hidden"
									bind:value={_user.role}
									aria-label={$i18n.t('Role')}
									placeholder={$i18n.t('Enter Your Role')}
									required
								>
									<option value="pending"> {$i18n.t('pending')} </option>
									<option value="user"> {$i18n.t('user')} </option>
									<option value="admin"> {$i18n.t('admin')} </option>
								</select>
							</div>
						</div>

						<div class="flex flex-col w-full mt-1">
							<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Name')}</div>

							<div class="flex-1">
								<input
									class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
									type="text"
									bind:value={_user.name}
									aria-label={$i18n.t('Name')}
									placeholder={$i18n.t('Enter Your Full Name')}
									autocomplete="off"
									required
								/>
							</div>
						</div>

						<hr class=" border-gray-100/30 dark:border-gray-850/30 my-2.5 w-full" />

						<div class="flex flex-col w-full">
							<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Email')}</div>

							<div class="flex-1">
								<input
									class="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
									type="email"
									bind:value={_user.email}
									aria-label={$i18n.t('Email')}
									placeholder={$i18n.t('Enter Your Email')}
									required
								/>
							</div>
						</div>

						<div class="flex flex-col w-full mt-1">
							<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Password')}</div>

							<div class="flex-1">
								<SensitiveInput
									inputClassName="w-full text-sm bg-transparent disabled:text-gray-500 dark:disabled:text-gray-500 outline-hidden"
									bind:value={_user.password}
									placeholder={$i18n.t('Enter Your Password')}
									required
								/>
							</div>
						</div>
					</div>

					<div class="flex justify-end pt-3 text-sm font-medium">
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
