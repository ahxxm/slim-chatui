<script lang="ts">
	import { getContext, tick, untrack } from 'svelte';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import EmojiPicker from '$lib/components/common/EmojiPicker.svelte';
	import Emoji from '$lib/components/common/Emoji.svelte';
	import Folder from '$lib/components/icons/Folder.svelte';

	import { toast } from 'svelte-sonner';

	import Textarea from '$lib/components/common/Textarea.svelte';
	import { getFolderById } from '$lib/apis/folders';
	const i18n = getContext('i18n');

	let {
		show = $bindable(false),
		onSubmit = (e) => {},
		folderId = null,
		edit = false
	}: {
		show?: boolean;
		onSubmit?: Function;
		folderId?: string | null;
		edit?: boolean;
	} = $props();

	let folder = $state(null);
	let name = $state('');
	let meta = $state({});
	let data: { system_prompt: string; files: any[] } = $state({
		system_prompt: '',
		files: []
	});

	let loading = $state(false);

	const submitHandler = async () => {
		loading = true;

		if ((data?.files ?? []).some((file) => file.status === 'uploading')) {
			toast.error($i18n.t('Please wait until all files are uploaded.'));
			loading = false;
			return;
		}

		await onSubmit({
			name,
			meta,
			data
		});
		show = false;
		loading = false;
	};

	const init = async () => {
		if (folderId) {
			folder = await getFolderById(localStorage.token, folderId).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			name = folder.name;
			meta = folder.meta || {};
			data = folder.data || {
				system_prompt: '',
				files: []
			};
		}

		focusInput();
	};

	const focusInput = async () => {
		await tick();
		const input = document.getElementById('folder-name') as HTMLInputElement;
		if (input) {
			input.focus();
			input.select();
		}
	};

	$effect(() => {
		if (show) {
			untrack(() => init());
		}
	});

	$effect(() => {
		if (!show && !edit) {
			name = '';
			meta = {};
			data = {
				system_prompt: '',
				files: []
			};
		}
	});
</script>

<Modal size="md" bind:show>
	<div>
		<div class=" flex justify-between dark:text-gray-300 px-5 pt-4 pb-1">
			<div class=" text-lg font-medium self-center">
				{#if edit}
					{$i18n.t('Edit Folder')}
				{:else}
					{$i18n.t('Create Folder')}
				{/if}
			</div>
			<button
				class="self-center"
				onclick={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full px-5 pb-4 md:space-x-4 dark:text-gray-200">
			<div class=" flex flex-col w-full sm:flex-row sm:justify-center sm:space-x-6">
				<form
					class="flex flex-col w-full"
					onsubmit={(e) => {
						e.preventDefault();
						submitHandler();
					}}
				>
					<div class="flex flex-col w-full mt-1">
						<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Folder Name')}</div>

						<div class="flex items-center gap-2">
							<EmojiPicker
								side="bottom"
								onSubmit={(iconName) => {
									meta = { ...meta, icon: iconName };
								}}
							>
								<button
									type="button"
									class="relative rounded-full bg-gray-50 dark:bg-gray-800 size-9 flex justify-center items-center shrink-0 hover:brightness-95 dark:hover:brightness-110 transition"
									aria-label={$i18n.t('Change folder icon')}
								>
									{#if meta?.icon}
										<Emoji className="size-5" shortCode={meta.icon} />
									{:else}
										<Folder className="size-4" strokeWidth="2" />
									{/if}
									<div
										class="absolute -bottom-0.5 -right-0.5 rounded-full bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 size-4 flex items-center justify-center"
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 16 16"
											fill="currentColor"
											class="size-2.5 text-gray-500 dark:text-gray-300"
										>
											<path
												d="M13.488 2.513a1.75 1.75 0 0 0-2.475 0L6.75 6.774a2.75 2.75 0 0 0-.596.892l-.848 2.047a.75.75 0 0 0 .98.98l2.047-.848a2.75 2.75 0 0 0 .892-.596l4.261-4.262a1.75 1.75 0 0 0 0-2.474Z"
											/>
											<path
												d="M4.75 3.5c-.69 0-1.25.56-1.25 1.25v6.5c0 .69.56 1.25 1.25 1.25h6.5c.69 0 1.25-.56 1.25-1.25V9A.75.75 0 0 1 14 9v2.25A2.75 2.75 0 0 1 11.25 14h-6.5A2.75 2.75 0 0 1 2 11.25v-6.5A2.75 2.75 0 0 1 4.75 2H7a.75.75 0 0 1 0 1.5H4.75Z"
											/>
										</svg>
									</div>
								</button>
							</EmojiPicker>

							<input
								id="folder-name"
								class="w-full text-sm bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-700 outline-hidden"
								type="text"
								bind:value={name}
								placeholder={$i18n.t('Enter folder name')}
								autocomplete="off"
							/>
						</div>
					</div>

					<hr class=" border-gray-50 dark:border-gray-850/30 my-2.5 w-full" />

					<div class="my-1">
						<div class="mb-2 text-xs text-gray-500">{$i18n.t('System Prompt')}</div>
						<div>
							<Textarea
								className=" text-sm w-full bg-transparent outline-hidden "
								placeholder={$i18n.t(
									'Write your model system prompt content here\ne.g.) You are Mario from Super Mario Bros, acting as an assistant.'
								)}
								maxSize={200}
								bind:value={data.system_prompt}
							/>
						</div>
					</div>

					<div class="flex justify-end pt-3 text-sm font-medium gap-1.5">
						<button
							class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-950 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full flex flex-row space-x-1 items-center {loading
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
