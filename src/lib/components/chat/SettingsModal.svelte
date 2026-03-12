<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { models, settings, user } from '$lib/stores';
	import { updateUserSettings } from '$lib/apis/users';
	import { getModels as _getModels } from '$lib/apis';
	import { goto } from '$app/navigation';

	import Modal from '../common/Modal.svelte';
	import Account from './Settings/Account.svelte';
	import About from './Settings/About.svelte';
	import General from './Settings/General.svelte';
	import Interface from './Settings/Interface.svelte';
	import DataControls from './Settings/DataControls.svelte';
	import XMark from '../icons/XMark.svelte';
	import DatabaseSettings from '../icons/DatabaseSettings.svelte';
	import SettingsAlt from '../icons/SettingsAlt.svelte';
	import UserCircle from '../icons/UserCircle.svelte';
	import InfoCircle from '../icons/InfoCircle.svelte';
	import AppNotification from '../icons/AppNotification.svelte';
	import UserBadgeCheck from '../icons/UserBadgeCheck.svelte';

	const i18n = getContext('i18n');

	let { show = $bindable(false) } = $props();

	$effect(() => {
		if (show) {
			untrack(() => addScrollListener());
		} else {
			untrack(() => removeScrollListener());
		}
	});

	const saveSettings = async (updated) => {
		console.log(updated);
		await settings.set({ ...$settings, ...updated });
		await models.set(await getModels());
		await updateUserSettings(localStorage.token, { ui: $settings });
	};

	const getModels = async () => {
		return await _getModels(localStorage.token);
	};

	let selectedTab = $state('general');

	const scrollHandler = (event) => {
		const settingsTabsContainer = document.getElementById('settings-tabs-container');
		if (settingsTabsContainer) {
			event.preventDefault();
			settingsTabsContainer.scrollLeft += event.deltaY;
		}
	};

	const addScrollListener = async () => {
		await tick();
		const settingsTabsContainer = document.getElementById('settings-tabs-container');
		if (settingsTabsContainer) {
			settingsTabsContainer.addEventListener('wheel', scrollHandler);
		}
	};

	const removeScrollListener = async () => {
		await tick();
		const settingsTabsContainer = document.getElementById('settings-tabs-container');
		if (settingsTabsContainer) {
			settingsTabsContainer.removeEventListener('wheel', scrollHandler);
		}
	};
</script>

<Modal size="2xl" bind:show>
	<div class="text-gray-700 dark:text-gray-100 mx-1">
		<div class=" flex justify-between dark:text-gray-300 px-4 md:px-4.5 pt-4.5 pb-0.5 md:pb-2.5">
			<div class=" text-lg font-medium self-center">{$i18n.t('Settings')}</div>
			<button
				aria-label={$i18n.t('Close settings modal')}
				class="self-center"
				onclick={() => {
					show = false;
				}}
			>
				<XMark className="w-5 h-5"></XMark>
			</button>
		</div>

		<div class="flex flex-col md:flex-row w-full pt-1 pb-4">
			<div
				role="tablist"
				id="settings-tabs-container"
				class="tabs flex flex-row overflow-x-auto gap-2.5 mx-3 md:pr-4 md:gap-1 md:flex-col flex-1 md:flex-none md:w-50 md:min-h-[42rem] md:max-h-[42rem] dark:text-gray-200 text-sm text-left mb-1 md:mb-0 -translate-y-1"
			>
				{#each ['general', 'interface', 'data_controls', 'account', 'about'] as tabId (tabId)}
					{#if tabId === 'general'}
						<button
							role="tab"
							aria-controls="tab-general"
							aria-selected={selectedTab === 'general'}
							class={`px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none flex text-left transition
								${
									selectedTab === 'general'
										? ($settings?.highContrastMode ?? false)
											? 'dark:bg-gray-800 bg-gray-200'
											: ''
										: ($settings?.highContrastMode ?? false)
											? 'hover:bg-gray-200 dark:hover:bg-gray-800'
											: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'
								}`}
							onclick={() => {
								selectedTab = 'general';
							}}
						>
							<div class=" self-center mr-2">
								<SettingsAlt strokeWidth="2" />
							</div>
							<div class=" self-center">{$i18n.t('General')}</div>
						</button>
					{:else if tabId === 'interface'}
						<button
							role="tab"
							aria-controls="tab-interface"
							aria-selected={selectedTab === 'interface'}
							class={`px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none flex text-left transition
								${
									selectedTab === 'interface'
										? ($settings?.highContrastMode ?? false)
											? 'dark:bg-gray-800 bg-gray-200'
											: ''
										: ($settings?.highContrastMode ?? false)
											? 'hover:bg-gray-200 dark:hover:bg-gray-800'
											: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'
								}`}
							onclick={() => {
								selectedTab = 'interface';
							}}
						>
							<div class=" self-center mr-2">
								<AppNotification strokeWidth="2" />
							</div>
							<div class=" self-center">{$i18n.t('Interface')}</div>
						</button>
					{:else if tabId === 'data_controls'}
						<button
							role="tab"
							aria-controls="tab-data-controls"
							aria-selected={selectedTab === 'data_controls'}
							class={`px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none flex text-left transition
								${
									selectedTab === 'data_controls'
										? ($settings?.highContrastMode ?? false)
											? 'dark:bg-gray-800 bg-gray-200'
											: ''
										: ($settings?.highContrastMode ?? false)
											? 'hover:bg-gray-200 dark:hover:bg-gray-800'
											: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'
								}`}
							onclick={() => {
								selectedTab = 'data_controls';
							}}
						>
							<div class=" self-center mr-2">
								<DatabaseSettings strokeWidth="2" />
							</div>
							<div class=" self-center">{$i18n.t('Data Controls')}</div>
						</button>
					{:else if tabId === 'account'}
						<button
							role="tab"
							aria-controls="tab-account"
							aria-selected={selectedTab === 'account'}
							class={`px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none flex text-left transition
								${
									selectedTab === 'account'
										? ($settings?.highContrastMode ?? false)
											? 'dark:bg-gray-800 bg-gray-200'
											: ''
										: ($settings?.highContrastMode ?? false)
											? 'hover:bg-gray-200 dark:hover:bg-gray-800'
											: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'
								}`}
							onclick={() => {
								selectedTab = 'account';
							}}
						>
							<div class=" self-center mr-2">
								<UserCircle strokeWidth="2" />
							</div>
							<div class=" self-center">{$i18n.t('Account')}</div>
						</button>
					{:else if tabId === 'about'}
						<button
							role="tab"
							aria-controls="tab-about"
							aria-selected={selectedTab === 'about'}
							class={`px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none flex text-left transition
								${
									selectedTab === 'about'
										? ($settings?.highContrastMode ?? false)
											? 'dark:bg-gray-800 bg-gray-200'
											: ''
										: ($settings?.highContrastMode ?? false)
											? 'hover:bg-gray-200 dark:hover:bg-gray-800'
											: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'
								}`}
							onclick={() => {
								selectedTab = 'about';
							}}
						>
							<div class=" self-center mr-2">
								<InfoCircle strokeWidth="2" />
							</div>
							<div class=" self-center">{$i18n.t('About')}</div>
						</button>
					{/if}
				{/each}
				{#if $user?.role === 'admin'}
					<a
						href="/admin/settings"
						draggable="false"
						class="px-0.5 md:px-2.5 py-1 min-w-fit rounded-xl flex-1 md:flex-none md:mt-auto flex select-none text-left transition {$settings?.highContrastMode
							? 'hover:bg-gray-200 dark:hover:bg-gray-800'
							: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
						onclick={async (e) => {
							e.preventDefault();
							await goto('/admin/settings');
							show = false;
						}}
					>
						<div class=" self-center mr-2">
							<UserBadgeCheck strokeWidth="2" />
						</div>
						<div class=" self-center">{$i18n.t('Admin Settings')}</div>
					</a>
				{/if}
			</div>
			<div class="flex-1 px-3.5 md:pl-0 md:pr-4.5 md:min-h-[42rem] max-h-[42rem]">
				{#if selectedTab === 'general'}
					<General
						{saveSettings}
						onsave={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'interface'}
					<Interface {saveSettings} />
				{:else if selectedTab === 'data_controls'}
					<DataControls />
				{:else if selectedTab === 'account'}
					<Account
						{saveSettings}
						saveHandler={() => {
							toast.success($i18n.t('Settings saved successfully!'));
						}}
					/>
				{:else if selectedTab === 'about'}
					<About />
				{/if}
			</div>
		</div>
	</div>
</Modal>

<style>
	.tabs::-webkit-scrollbar {
		display: none;
	}

	.tabs {
		-ms-overflow-style: none;
		scrollbar-width: none;
	}
</style>
