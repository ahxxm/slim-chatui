<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { createEventDispatcher, getContext, tick } from 'svelte';

	import { userSignOut } from '$lib/apis/auths';

	import { showSettings, mobile, showSidebar, showShortcuts, user } from '$lib/stores';

	import Keyboard from '$lib/components/icons/Keyboard.svelte';
	import ShortcutsModal from '$lib/components/chat/ShortcutsModal.svelte';
	import Settings from '$lib/components/icons/Settings.svelte';

	import UserGroup from '$lib/components/icons/UserGroup.svelte';
	import SignOut from '$lib/components/icons/SignOut.svelte';

	const i18n = getContext('i18n');

	export let show = false;
	export let role = '';

	export let help = false;

	export let className = 'max-w-[240px]';

	const dispatch = createEventDispatcher();

	const handleDropdownChange = (state: boolean) => {
		dispatch('change', state);
	};
</script>

<ShortcutsModal bind:show={$showShortcuts} />

<!-- svelte-ignore a11y-no-static-element-interactions -->
<DropdownMenu.Root bind:open={show} onOpenChange={handleDropdownChange}>
	<DropdownMenu.Trigger>
		{#snippet child({ props })}
			<div {...props}>
				<slot />
			</div>
		{/snippet}
	</DropdownMenu.Trigger>

	<DropdownMenu.Portal>
		<slot name="content">
			<DropdownMenu.Content
				class="bits-content w-full {className} rounded-2xl px-1 py-1 border border-gray-100 dark:border-gray-800 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg text-sm"
				sideOffset={4}
				side="top"
				align="end"
			>
				<DropdownMenu.Item
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
					onclick={async () => {
						show = false;

						await showSettings.set(true);

						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<Settings className="w-5 h-5" strokeWidth="1.5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Settings')}</div>
				</DropdownMenu.Item>

				{#if role === 'admin'}
					<DropdownMenu.Item>
						{#snippet child({ props })}
							<a
								href="/admin"
								draggable="false"
								{...props}
								class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
								onclick={async () => {
									show = false;
									if ($mobile) {
										await tick();
										showSidebar.set(false);
									}
								}}
							>
								<div class=" self-center mr-3">
									<UserGroup className="w-5 h-5" strokeWidth="1.5" />
								</div>
								<div class=" self-center truncate">{$i18n.t('Admin Panel')}</div>
							</a>
						{/snippet}
					</DropdownMenu.Item>
				{/if}

				{#if help}
					<hr class=" border-gray-50/30 dark:border-gray-800/30 my-1 p-0" />

					<!-- {$i18n.t('Help')} -->

					<DropdownMenu.Item
						class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
						id="chat-share-button"
						onclick={async () => {
							show = false;
							showShortcuts.set(!$showShortcuts);

							if ($mobile) {
								await tick();
								showSidebar.set(false);
							}
						}}
					>
						<div class=" self-center mr-3">
							<Keyboard className="size-5" />
						</div>
						<div class=" self-center truncate">{$i18n.t('Keyboard shortcuts')}</div>
					</DropdownMenu.Item>
				{/if}

				<hr class=" border-gray-50/30 dark:border-gray-800/30 my-1 p-0" />

				<DropdownMenu.Item
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
					onclick={async () => {
						const res = await userSignOut();
						user.set(null);
						localStorage.removeItem('token');

						location.href = res?.redirect_url ?? '/auth';
						show = false;
					}}
				>
					<div class=" self-center mr-3">
						<SignOut className="w-5 h-5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Sign Out')}</div>
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</slot>
	</DropdownMenu.Portal>
</DropdownMenu.Root>
