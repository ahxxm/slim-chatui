<script lang="ts">
	import { config, settings } from '$lib/stores';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { setTextScale } from '$lib/utils/text-scale';

	import Switch from '$lib/components/common/Switch.svelte';
	import ManageFloatingActionButtonsModal from './Interface/ManageFloatingActionButtonsModal.svelte';
	import ManageImageCompressionModal from './Interface/ManageImageCompressionModal.svelte';

	const i18n = getContext('i18n');

	let {
		saveSettings
	}: {
		saveSettings: (settings: Record<string, unknown>) => void;
	} = $props();

	let inputFiles = $state(null);
	let filesInputElement: HTMLInputElement;
	let showManageFloatingActionButtonsModal = $state(false);
	let showManageImageCompressionModal = $state(false);

	// Settings state — initialized from $settings store, defaults match store schema
	let titleAutoGenerate = $state($settings?.title?.auto ?? true);
	let autoFollowUps = $state($settings?.autoFollowUps ?? true);
	let responseAutoCopy = $state($settings?.responseAutoCopy ?? false);
	let widescreenMode = $state($settings?.widescreenMode ?? false);

	let defaultModelId = $state(
		$config?.default_models?.split(',')[0] ?? $settings?.models?.at(0) ?? ''
	);
	let showUsername = $state($settings?.showUsername ?? false);
	let notificationSound = $state($settings?.notificationSound ?? true);
	let notificationSoundAlways = $state($settings?.notificationSoundAlways ?? false);
	let highContrastMode = $state($settings?.highContrastMode ?? false);
	let richTextInput = $state($settings?.richTextInput ?? true);
	let showFormattingToolbar = $state($settings?.showFormattingToolbar ?? false);
	let insertPromptAsRichText = $state($settings?.insertPromptAsRichText ?? false);
	let largeTextAsFile = $state($settings?.largeTextAsFile ?? false);
	let insertSuggestionPrompt = $state($settings?.insertSuggestionPrompt ?? false);
	let keepFollowUpPrompts = $state($settings?.keepFollowUpPrompts ?? false);
	let insertFollowUpPrompt = $state($settings?.insertFollowUpPrompt ?? false);
	let regenerateMenu = $state($settings?.regenerateMenu ?? true);
	let enableMessageQueue = $state($settings?.enableMessageQueue ?? true);
	let landingPageMode = $state($settings?.landingPageMode ?? '');
	let chatBubble = $state($settings?.chatBubble ?? true);
	let chatDirection: 'LTR' | 'RTL' | 'auto' = $state($settings?.chatDirection ?? 'auto');
	let ctrlEnterToSend = $state($settings?.ctrlEnterToSend ?? false);
	let copyFormatted = $state($settings?.copyFormatted ?? false);
	let temporaryChatByDefault = $state($settings?.temporaryChatByDefault ?? false);
	let chatFadeStreamingText = $state($settings?.chatFadeStreamingText ?? true);
	let collapseCodeBlocks = $state($settings?.collapseCodeBlocks ?? false);
	let expandDetails = $state($settings?.expandDetails ?? false);
	let renderMarkdownInPreviews = $state($settings?.renderMarkdownInPreviews ?? true);
	let showChatTitleInTab = $state($settings?.showChatTitleInTab ?? true);
	let showFloatingActionButtons = $state($settings?.showFloatingActionButtons ?? true);
	let floatingActionButtons = $state($settings?.floatingActionButtons ?? null);
	let imageCompression = $state($settings?.imageCompression ?? false);
	let imageCompressionSize = $state($settings?.imageCompressionSize ?? { width: '', height: '' });
	let hapticFeedback = $state($settings?.hapticFeedback ?? false);
	let iframeSandboxAllowSameOrigin = $state($settings?.iframeSandboxAllowSameOrigin ?? false);
	let iframeSandboxAllowForms = $state($settings?.iframeSandboxAllowForms ?? false);
	let backgroundImageUrl = $state($settings?.backgroundImageUrl ?? null);
	let textScale: number | null = $state($settings?.textScale ?? null);

	const toggleLandingPageMode = async () => {
		landingPageMode = landingPageMode === '' ? 'chat' : '';
		saveSettings({ landingPageMode: landingPageMode });
	};

	const toggleTitleAutoGenerate = async () => {
		saveSettings({
			title: {
				...$settings.title,
				auto: titleAutoGenerate
			}
		});
	};

	const toggleResponseAutoCopy = async () => {
		const permission = await navigator.clipboard
			.readText()
			.then(() => {
				return 'granted';
			})
			.catch(() => {
				return '';
			});

		if (permission === 'granted') {
			saveSettings({ responseAutoCopy: responseAutoCopy });
		} else {
			responseAutoCopy = false;
			toast.error(
				$i18n.t(
					'Clipboard write permission denied. Please check your browser settings to grant the necessary access.'
				)
			);
		}
	};

	const toggleChangeChatDirection = async () => {
		if (chatDirection === 'auto') {
			chatDirection = 'LTR';
		} else if (chatDirection === 'LTR') {
			chatDirection = 'RTL';
		} else if (chatDirection === 'RTL') {
			chatDirection = 'auto';
		}
		saveSettings({ chatDirection });
	};

	const togglectrlEnterToSend = async () => {
		ctrlEnterToSend = !ctrlEnterToSend;
		saveSettings({ ctrlEnterToSend });
	};

	const setTextScaleHandler = (scale) => {
		textScale = scale;
		setTextScale(textScale);

		if (textScale === 1) {
			textScale = null;
		}
		saveSettings({ textScale });
	};
</script>

<ManageFloatingActionButtonsModal
	bind:show={showManageFloatingActionButtonsModal}
	{floatingActionButtons}
	onSave={(buttons) => {
		floatingActionButtons = buttons;
		saveSettings({ floatingActionButtons });
	}}
/>

<ManageImageCompressionModal
	bind:show={showManageImageCompressionModal}
	size={imageCompressionSize}
	onSave={(size) => {
		saveSettings({ imageCompressionSize: size });
	}}
/>

<div id="tab-interface" class="flex flex-col h-full justify-between space-y-3 text-sm">
	<input
		bind:this={filesInputElement}
		bind:files={inputFiles}
		type="file"
		hidden
		accept="image/*"
		onchange={() => {
			let reader = new FileReader();
			reader.onload = (event) => {
				let originalImageUrl = `${event.target.result}`;

				backgroundImageUrl = originalImageUrl;
				saveSettings({ backgroundImageUrl });
			};

			if (
				inputFiles &&
				inputFiles.length > 0 &&
				['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(inputFiles[0]['type'])
			) {
				reader.readAsDataURL(inputFiles[0]);
			} else {
				console.log(`Unsupported File Type '${inputFiles[0]['type']}'.`);
				inputFiles = null;
			}
		}}
	/>

	<div class=" space-y-3 overflow-y-scroll max-h-[28rem] md:max-h-full">
		<div>
			<h1 class=" mb-2 text-sm font-medium">{$i18n.t('UI')}</h1>

			<div class="py-0.5 flex w-full justify-between">
				<div class="self-center text-xs font-medium">{$i18n.t('UI Scale')}</div>
				<div class="self-center text-xs">{(textScale ?? 1).toFixed(2)}x</div>
			</div>
			<div class="px-1 pb-1">
				<input
					class="w-full"
					type="range"
					min="1"
					max="1.5"
					step={0.05}
					value={textScale ?? 1}
					oninput={(e) => {
						const val = parseFloat(parseFloat(e.currentTarget.value).toFixed(2));
						textScale = val === 1 ? null : val;
						setTextScaleHandler(val);
					}}
				/>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="high-contrast-mode-label" class=" self-center text-xs">
						{$i18n.t('High Contrast Mode')} ({$i18n.t('Beta')})
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="high-contrast-mode-label"
							tooltip={true}
							bind:state={highContrastMode}
							onchange={() => {
								saveSettings({ highContrastMode });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="use-chat-title-as-tab-title-label" class=" self-center text-xs">
						{$i18n.t('Display chat title in tab')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="use-chat-title-as-tab-title-label"
							tooltip={true}
							bind:state={showChatTitleInTab}
							onchange={() => {
								saveSettings({ showChatTitleInTab });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class="py-0.5 flex w-full justify-between">
					<div id="notification-sound-label" class=" self-center text-xs">
						{$i18n.t('Notification Sound')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="notification-sound-label"
							tooltip={true}
							bind:state={notificationSound}
							onchange={() => {
								saveSettings({ notificationSound });
							}}
						/>
					</div>
				</div>
			</div>

			{#if notificationSound}
				<div>
					<div class=" py-0.5 flex w-full justify-between">
						<div id="play-notification-sound-label" class=" self-center text-xs">
							{$i18n.t('Always Play Notification Sound')}
						</div>

						<div class="flex items-center gap-2 p-1">
							<Switch
								ariaLabelledbyId="play-notification-sound-label"
								tooltip={true}
								bind:state={notificationSoundAlways}
								onchange={() => {
									saveSettings({ notificationSoundAlways });
								}}
							/>
						</div>
					</div>
				</div>
			{/if}

			<div></div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="haptic-feedback-label" class=" self-center text-xs">
						{$i18n.t('Haptic Feedback')} ({$i18n.t('Android')})
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="haptic-feedback-label"
							tooltip={true}
							bind:state={hapticFeedback}
							onchange={() => {
								saveSettings({ hapticFeedback });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="copy-formatted-label" class=" self-center text-xs">
						{$i18n.t('Copy Formatted Text')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="copy-formatted-label"
							tooltip={true}
							bind:state={copyFormatted}
							onchange={() => {
								saveSettings({ copyFormatted });
							}}
						/>
					</div>
				</div>
			</div>

			<div class=" my-2 text-sm font-medium">{$i18n.t('Chat')}</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="enable-message-queue-label" class=" self-center text-xs">
						{$i18n.t('Enable Message Queue')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="enable-message-queue-label"
							tooltip={true}
							bind:state={enableMessageQueue}
							onchange={() => {
								saveSettings({ enableMessageQueue });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="chat-direction-label" class=" self-center text-xs">
						{$i18n.t('Chat direction')}
					</div>

					<button
						aria-labelledby="chat-direction-label chat-direction-mode"
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={toggleChangeChatDirection}
						type="button"
					>
						<span class="ml-2 self-center" id="chat-direction-mode">
							{chatDirection === 'LTR'
								? $i18n.t('LTR')
								: chatDirection === 'RTL'
									? $i18n.t('RTL')
									: $i18n.t('Auto')}
						</span>
					</button>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="landing-page-mode-label" class=" self-center text-xs">
						{$i18n.t('Landing Page Mode')}
					</div>

					<button
						aria-labelledby="landing-page-mode-label notification-sound-state"
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							toggleLandingPageMode();
						}}
						type="button"
					>
						<span class="ml-2 self-center" id="notification-sound-state"
							>{landingPageMode === '' ? $i18n.t('Default') : $i18n.t('Chat')}</span
						>
					</button>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="chat-background-label" class=" self-center text-xs">
						{$i18n.t('Chat Background Image')}
					</div>

					<button
						aria-labelledby="chat-background-label background-image-url-state"
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							if (backgroundImageUrl !== null) {
								backgroundImageUrl = null;
								saveSettings({ backgroundImageUrl });
							} else {
								filesInputElement.click();
							}
						}}
						type="button"
					>
						<span class="ml-2 self-center" id="background-image-url-state"
							>{backgroundImageUrl !== null ? $i18n.t('Reset') : $i18n.t('Upload')}</span
						>
					</button>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="chat-bubble-ui-label" class=" self-center text-xs">
						{$i18n.t('Chat Bubble UI')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							tooltip={true}
							ariaLabelledbyId="chat-bubble-ui-label"
							bind:state={chatBubble}
							onchange={() => {
								saveSettings({ chatBubble });
							}}
						/>
					</div>
				</div>
			</div>

			{#if !$settings.chatBubble}
				<div>
					<div class=" py-0.5 flex w-full justify-between">
						<div id="chat-bubble-username-label" class=" self-center text-xs">
							{$i18n.t('Display the username instead of You in the Chat')}
						</div>

						<div class="flex items-center gap-2 p-1">
							<Switch
								ariaLabelledbyId="chat-bubble-username-label"
								tooltip={true}
								bind:state={showUsername}
								onchange={() => {
									saveSettings({ showUsername });
								}}
							/>
						</div>
					</div>
				</div>
			{/if}

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="widescreen-mode-label" class=" self-center text-xs">
						{$i18n.t('Widescreen Mode')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="widescreen-mode-label"
							tooltip={true}
							bind:state={widescreenMode}
							onchange={() => {
								saveSettings({ widescreenMode });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="temp-chat-default-label" class=" self-center text-xs">
						{$i18n.t('Temporary Chat by Default')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="temp-chat-default-label"
							tooltip={true}
							bind:state={temporaryChatByDefault}
							onchange={() => {
								saveSettings({ temporaryChatByDefault });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="fade-streaming-label" class=" self-center text-xs">
						{$i18n.t('Fade Effect for Streaming Text')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="fade-streaming-label"
							tooltip={true}
							bind:state={chatFadeStreamingText}
							onchange={() => {
								saveSettings({ chatFadeStreamingText });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="auto-generation-label" class=" self-center text-xs">
						{$i18n.t('Title Auto-Generation')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="auto-generation-label"
							tooltip={true}
							bind:state={titleAutoGenerate}
							onchange={() => {
								toggleTitleAutoGenerate();
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div class=" self-center text-xs" id="follow-up-auto-generation-label">
						{$i18n.t('Follow-Up Auto-Generation')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="follow-up-auto-generation-label"
							tooltip={true}
							bind:state={autoFollowUps}
							onchange={() => {
								saveSettings({ autoFollowUps });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="auto-copy-label" class=" self-center text-xs">
						{$i18n.t('Auto-Copy Response to Clipboard')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="auto-copy-label"
							tooltip={true}
							bind:state={responseAutoCopy}
							onchange={() => {
								toggleResponseAutoCopy();
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="insert-suggestion-prompt-label" class=" self-center text-xs">
						{$i18n.t('Insert Suggestion Prompt to Input')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="insert-suggestion-prompt-label"
							tooltip={true}
							bind:state={insertSuggestionPrompt}
							onchange={() => {
								saveSettings({ insertSuggestionPrompt });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="keep-follow-up-prompts-label" class=" self-center text-xs">
						{$i18n.t('Keep Follow-Up Prompts in Chat')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="keep-follow-up-prompts-label"
							tooltip={true}
							bind:state={keepFollowUpPrompts}
							onchange={() => {
								saveSettings({ keepFollowUpPrompts });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="insert-follow-up-prompt-label" class=" self-center text-xs">
						{$i18n.t('Insert Follow-Up Prompt to Input')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="insert-follow-up-prompt-label"
							tooltip={true}
							bind:state={insertFollowUpPrompt}
							onchange={() => {
								saveSettings({ insertFollowUpPrompt });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="regenerate-menu-label" class=" self-center text-xs">
						{$i18n.t('Regenerate Menu')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="regenerate-menu-label"
							tooltip={true}
							bind:state={regenerateMenu}
							onchange={() => {
								saveSettings({ regenerateMenu });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="always-collapse-label" class=" self-center text-xs">
						{$i18n.t('Always Collapse Code Blocks')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="always-collapse-label"
							tooltip={true}
							bind:state={collapseCodeBlocks}
							onchange={() => {
								saveSettings({ collapseCodeBlocks });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="always-expand-label" class=" self-center text-xs">
						{$i18n.t('Always Expand Details')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="always-expand-label"
							tooltip={true}
							bind:state={expandDetails}
							onchange={() => {
								saveSettings({ expandDetails });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="render-markdown-in-previews-label" class=" self-center text-xs">
						{$i18n.t('Render Markdown in Previews')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="render-markdown-in-previews-label"
							tooltip={true}
							bind:state={renderMarkdownInPreviews}
							onchange={() => {
								saveSettings({ renderMarkdownInPreviews });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<label id="floating-action-buttons-label" class=" self-center text-xs">
						{$i18n.t('Floating Quick Actions')}
					</label>

					<div class="flex items-center gap-3 p-1">
						{#if showFloatingActionButtons}
							<button
								class="text-xs text-gray-700 dark:text-gray-400 underline"
								type="button"
								aria-label={$i18n.t('Open Modal To Manage Floating Quick Actions')}
								onclick={() => {
									showManageFloatingActionButtonsModal = true;
								}}
							>
								{$i18n.t('Manage')}
							</button>
						{/if}

						<Switch
							ariaLabelledbyId="floating-action-buttons-label"
							tooltip={true}
							bind:state={showFloatingActionButtons}
							onchange={() => {
								saveSettings({ showFloatingActionButtons });
							}}
						/>
					</div>
				</div>
			</div>

			<div class=" my-2 text-sm font-medium">{$i18n.t('Input')}</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="enter-key-behavior-label ctrl-enter-to-send-state" class=" self-center text-xs">
						{$i18n.t('Enter Key Behavior')}
					</div>

					<button
						aria-labelledby="enter-key-behavior-label"
						class="p-1 px-3 text-xs flex rounded transition"
						onclick={() => {
							togglectrlEnterToSend();
						}}
						type="button"
					>
						<span class="ml-2 self-center" id="ctrl-enter-to-send-state"
							>{ctrlEnterToSend === true
								? $i18n.t('Ctrl+Enter to Send')
								: $i18n.t('Enter to Send')}</span
						>
					</button>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="rich-input-label" class=" self-center text-xs">
						{$i18n.t('Rich Text Input for Chat')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							tooltip={true}
							ariaLabelledbyId="rich-input-label"
							bind:state={richTextInput}
							onchange={() => {
								saveSettings({ richTextInput });
							}}
						/>
					</div>
				</div>
			</div>

			{#if richTextInput}
				<div>
					<div class=" py-0.5 flex w-full justify-between">
						<div id="show-formatting-toolbar-label" class=" self-center text-xs">
							{$i18n.t('Show Formatting Toolbar')}
						</div>

						<div class="flex items-center gap-2 p-1">
							<Switch
								ariaLabelledbyId="show-formatting-toolbar-label"
								tooltip={true}
								bind:state={showFormattingToolbar}
								onchange={() => {
									saveSettings({ showFormattingToolbar });
								}}
							/>
						</div>
					</div>
				</div>

				<div>
					<div class=" py-0.5 flex w-full justify-between">
						<div id="insert-prompt-as-rich-text-label" class=" self-center text-xs">
							{$i18n.t('Insert Prompt as Rich Text')}
						</div>

						<div class="flex items-center gap-2 p-1">
							<Switch
								ariaLabelledbyId="insert-prompt-as-rich-text-label"
								tooltip={true}
								bind:state={insertPromptAsRichText}
								onchange={() => {
									saveSettings({ insertPromptAsRichText });
								}}
							/>
						</div>
					</div>
				</div>
			{/if}

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="paste-large-label" class=" self-center text-xs">
						{$i18n.t('Paste Large Text as File')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							tooltip={true}
							ariaLabelledbyId="paste-large-label"
							bind:state={largeTextAsFile}
							onchange={() => {
								saveSettings({ largeTextAsFile });
							}}
						/>
					</div>
				</div>
			</div>

			<div class=" my-2 text-sm font-medium">{$i18n.t('Iframe Security')}</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="iframe-sandbox-allow-same-origin-label" class=" self-center text-xs">
						{$i18n.t('iframe Sandbox Allow Same Origin')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="iframe-sandbox-allow-same-origin-label"
							tooltip={true}
							bind:state={iframeSandboxAllowSameOrigin}
							onchange={() => {
								saveSettings({ iframeSandboxAllowSameOrigin });
							}}
						/>
					</div>
				</div>
			</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="iframe-sandbox-allow-forms-label" class=" self-center text-xs">
						{$i18n.t('iframe Sandbox Allow Forms')}
					</div>

					<div class="flex items-center gap-2 p-1">
						<Switch
							ariaLabelledbyId="iframe-sandbox-allow-forms-label"
							tooltip={true}
							bind:state={iframeSandboxAllowForms}
							onchange={() => {
								saveSettings({ iframeSandboxAllowForms });
							}}
						/>
					</div>
				</div>
			</div>
			<div class=" my-2 text-sm font-medium">{$i18n.t('File')}</div>

			<div>
				<div class=" py-0.5 flex w-full justify-between">
					<div id="image-compression-label" class=" self-center text-xs">
						{$i18n.t('Image Compression')}
					</div>

					<div class="flex items-center gap-3 p-1">
						{#if imageCompression}
							<button
								class="text-xs text-gray-700 dark:text-gray-400 underline"
								type="button"
								aria-label={$i18n.t('Open Modal To Manage Image Compression')}
								onclick={() => {
									showManageImageCompressionModal = true;
								}}
							>
								{$i18n.t('Manage')}
							</button>
						{/if}

						<Switch
							ariaLabelledbyId="image-compression-label"
							tooltip={true}
							bind:state={imageCompression}
							onchange={() => {
								saveSettings({ imageCompression });
							}}
						/>
					</div>
				</div>
			</div>
		</div>
	</div>
</div>
