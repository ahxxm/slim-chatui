<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { getLanguages, changeLanguage } from '$lib/i18n';

	import { settings, theme } from '$lib/stores';
	import { applyCjkFont } from '$lib/utils/cjk-font';

	const i18n = getContext('i18n');

	import Textarea from '$lib/components/common/Textarea.svelte';

	let {
		saveSettings,
		onsave
	}: {
		saveSettings: (settings: Record<string, unknown>) => void;
		onsave: () => void;
	} = $props();

	const themes = ['dark', 'light', 'oled-dark'];
	let selectedTheme = $state('system');
	let languages: Awaited<ReturnType<typeof getLanguages>> = $state([]);
	let lang = $state($i18n.language);
	let notificationEnabled = $state(false);
	let cjkFont = $state('default');
	let system = $state('');

	const toggleNotification = () => {
		notificationEnabled = !notificationEnabled;
		saveSettings({ notificationEnabled });
	};

	const saveHandler = async () => {
		saveSettings({
			system: system !== '' ? system : undefined
		});
		onsave();
	};

	onMount(async () => {
		selectedTheme = localStorage.theme ?? 'system';

		languages = await getLanguages();

		notificationEnabled = $settings.notificationEnabled ?? false;
		cjkFont = $settings.cjkFont ?? 'default';
		applyCjkFont(cjkFont);
		system = $settings.system ?? '';
	});

	const applyTheme = (_theme: string) => {
		let themeToApply = _theme === 'oled-dark' ? 'dark' : _theme;

		if (_theme === 'system') {
			themeToApply = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
		}

		if (themeToApply === 'dark' && !_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#333');
			document.documentElement.style.setProperty('--color-gray-850', '#262626');
			document.documentElement.style.setProperty('--color-gray-900', '#171717');
			document.documentElement.style.setProperty('--color-gray-950', '#0d0d0d');
		}

		themes
			.filter((e) => e !== themeToApply)
			.forEach((e) => {
				e.split(' ').forEach((e) => {
					document.documentElement.classList.remove(e);
				});
			});

		themeToApply.split(' ').forEach((e) => {
			document.documentElement.classList.add(e);
		});

		const metaThemeColor = document.querySelector('meta[name="theme-color"]');
		if (metaThemeColor) {
			if (_theme.includes('system')) {
				const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
					? 'dark'
					: 'light';
				console.log('Setting system meta theme color: ' + systemTheme);
				metaThemeColor.setAttribute('content', systemTheme === 'light' ? '#ffffff' : '#171717');
			} else {
				console.log('Setting meta theme color: ' + _theme);
				metaThemeColor.setAttribute(
					'content',
					_theme === 'dark' ? '#171717' : _theme === 'oled-dark' ? '#000000' : '#ffffff'
				);
			}
		}

		if (typeof window !== 'undefined' && window.applyTheme) {
			window.applyTheme();
		}

		if (_theme.includes('oled')) {
			document.documentElement.style.setProperty('--color-gray-800', '#101010');
			document.documentElement.style.setProperty('--color-gray-850', '#050505');
			document.documentElement.style.setProperty('--color-gray-900', '#000000');
			document.documentElement.style.setProperty('--color-gray-950', '#000000');
			document.documentElement.classList.add('dark');
		}

		console.log(_theme);
	};

	const themeChangeHandler = (_theme: string) => {
		theme.set(_theme);
		localStorage.setItem('theme', _theme);
		applyTheme(_theme);
	};
</script>

<div class="flex flex-col h-full justify-between text-sm" id="tab-general">
	<div class="  overflow-y-scroll max-h-[28rem] md:max-h-full">
		<div class="">
			<div class=" mb-1 text-sm font-medium">{$i18n.t('WebUI Settings')}</div>

			<div class="flex w-full justify-between">
				<div class=" self-center text-xs font-medium">{$i18n.t('Theme')}</div>
				<div class="flex items-center relative">
					<select
						class="w-fit pr-8 rounded-sm py-2 px-2 text-xs bg-transparent text-right {$settings.highContrastMode
							? ''
							: 'outline-hidden'}"
						bind:value={selectedTheme}
						placeholder={$i18n.t('Select a theme')}
						onchange={() => themeChangeHandler(selectedTheme)}
					>
						<option value="system">⚙️ {$i18n.t('System')}</option>
						<option value="dark">🌑 {$i18n.t('Dark')}</option>
						<option value="oled-dark">🌃 {$i18n.t('OLED Dark')}</option>
						<option value="light">☀️ {$i18n.t('Light')}</option>
					</select>
				</div>
			</div>

			<div class=" flex w-full justify-between">
				<div class=" self-center text-xs font-medium">{$i18n.t('Language')}</div>
				<div class="flex items-center relative">
					<select
						class="w-fit pr-8 rounded-sm py-2 px-2 text-xs bg-transparent text-right {$settings.highContrastMode
							? ''
							: 'outline-hidden'}"
						bind:value={lang}
						placeholder={$i18n.t('Select a language')}
						onchange={() => {
							changeLanguage(lang);
						}}
					>
						{#each languages as language}
							<option value={language['code']}>{language['title']}</option>
						{/each}
					</select>
				</div>
			</div>

			{#if lang.startsWith('zh')}
				<div class="flex w-full justify-between">
					<div class="self-center text-xs font-medium">字体</div>
					<div class="flex items-center relative">
						<select
							class="w-fit pr-8 rounded-sm py-2 px-2 text-xs bg-transparent text-right {$settings.highContrastMode
								? ''
								: 'outline-hidden'}"
							bind:value={cjkFont}
							onchange={() => {
								applyCjkFont(cjkFont);
								saveSettings({ cjkFont });
							}}
						>
							<option value="default">默认</option>
							<option value="noto">思源黑体</option>
							<option value="lxgw">霞鹜文楷</option>
						</select>
					</div>
				</div>
			{/if}

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">{$i18n.t('Notifications')}</div>

					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleNotification();
						}}
						type="button"
						role="switch"
						aria-checked={notificationEnabled}
					>
						{#if notificationEnabled === true}
							<span class="ml-2 self-center">{$i18n.t('On')}</span>
						{:else}
							<span class="ml-2 self-center">{$i18n.t('Off')}</span>
						{/if}
					</button>
				</div>
			</div>
		</div>

		<hr class="border-gray-100/30 dark:border-gray-850/30 my-3" />

		<div>
			<div class=" my-2.5 text-sm font-medium">{$i18n.t('System Prompt')}</div>
			<Textarea
				bind:value={system}
				className={'w-full text-sm outline-hidden resize-vertical' +
					($settings.highContrastMode
						? ' p-2.5 border-2 border-gray-300 dark:border-gray-700 rounded-lg bg-transparent text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 overflow-y-hidden'
						: '  dark:text-gray-300 ')}
				rows="4"
				placeholder={$i18n.t('Enter system prompt here')}
			/>
		</div>
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			onclick={() => {
				saveHandler();
			}}
		>
			{$i18n.t('Save')}
		</button>
	</div>
</div>
