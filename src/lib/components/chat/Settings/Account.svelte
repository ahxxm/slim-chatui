<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext } from 'svelte';

	import { user, config, settings } from '$lib/stores';
	import { updateUserProfile, getSessionUser } from '$lib/apis/auths';

	import UpdatePassword from './Account/UpdatePassword.svelte';
	import { defaultUserImage } from '$lib/utils';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import UserProfileImage from './Account/UserProfileImage.svelte';

	const i18n = getContext('i18n');

	export let saveHandler: Function;
	export let saveSettings: Function;

	let loaded = false;

	let profileImageUrl = '';
	let name = '';
	let bio = '';

	let _gender = '';
	let gender = '';
	let dateOfBirth = '';

	let profileImageInputElement: HTMLInputElement;

	const submitHandler = async () => {
		if (name !== $user?.name) {
			if (profileImageUrl === defaultUserImage() || profileImageUrl === '') {
				profileImageUrl = defaultUserImage();
			}
		}

		const updatedUser = await updateUserProfile(localStorage.token, {
			name: name,
			profile_image_url: profileImageUrl,
			bio: bio ? bio : null,
			gender: gender ? gender : null,
			date_of_birth: dateOfBirth ? dateOfBirth : null
		}).catch((error) => {
			toast.error(`${error}`);
		});

		if (updatedUser) {
			// Get Session User Info
			const sessionUser = await getSessionUser(localStorage.token).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			await user.set(sessionUser);
			return true;
		}
		return false;
	};

	onMount(async () => {
		const user = await getSessionUser(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (user) {
			name = user?.name ?? '';
			profileImageUrl = user?.profile_image_url ?? '';
			bio = user?.bio ?? '';

			_gender = user?.gender ?? '';
			gender = _gender;

			dateOfBirth = user?.date_of_birth ?? '';
		}

		loaded = true;
	});
</script>

<div id="tab-account" class="flex flex-col h-full justify-between text-sm">
	<div class=" overflow-y-scroll max-h-[28rem] md:max-h-full">
		<div class="space-y-1">
			<div>
				<div class="text-base font-medium">{$i18n.t('Your Account')}</div>

				<div class="text-xs text-gray-500 mt-0.5">
					{$i18n.t('Manage your account information.')}
				</div>
			</div>

			<!-- <div class=" text-sm font-medium">{$i18n.t('Account')}</div> -->

			<div class="flex space-x-5 my-4">
				<UserProfileImage bind:profileImageUrl user={$user} />

				<div class="flex flex-1 flex-col">
					<div class=" flex-1">
						<div class="flex flex-col w-full">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Name')}</div>

							<div class="flex-1">
								<input
									class="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
									type="text"
									bind:value={name}
									aria-label={$i18n.t('Name')}
									required
									placeholder={$i18n.t('Enter your name')}
								/>
							</div>
						</div>

						<div class="flex flex-col w-full mt-2">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Bio')}</div>

							<div class="flex-1">
								<Textarea
									className="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
									minSize={60}
									bind:value={bio}
									ariaLabel={$i18n.t('Bio')}
									placeholder={$i18n.t('Share your background and interests')}
								/>
							</div>
						</div>

						<div class="flex flex-col w-full mt-2">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Gender')}</div>

							<div class="flex-1">
								<select
									class="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden"
									bind:value={_gender}
									aria-label={$i18n.t('Gender')}
									on:change={(e) => {
										console.log(_gender);

										if (_gender === 'custom') {
											// Handle custom gender input
											gender = '';
										} else {
											gender = _gender;
										}
									}}
								>
									<option value="" selected>{$i18n.t('Prefer not to say')}</option>
									<option value="male">{$i18n.t('Male')}</option>
									<option value="female">{$i18n.t('Female')}</option>
									<option value="custom">{$i18n.t('Custom')}</option>
								</select>
							</div>

							{#if _gender === 'custom'}
								<input
									class="w-full text-sm dark:text-gray-300 bg-transparent outline-hidden mt-1"
									type="text"
									required
									aria-label={$i18n.t('Custom Gender')}
									placeholder={$i18n.t('Enter your gender')}
									bind:value={gender}
								/>
							{/if}
						</div>

						<div class="flex flex-col w-full mt-2">
							<div class=" mb-1 text-xs font-medium">{$i18n.t('Birth Date')}</div>

							<div class="flex-1">
								<input
									class="w-full text-sm dark:text-gray-300 dark:placeholder:text-gray-300 bg-transparent outline-hidden"
									type="date"
									aria-label={$i18n.t('Birth Date')}
									bind:value={dateOfBirth}
									required
								/>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<hr class="border-gray-50 dark:border-gray-850/30 my-4" />

		<div class="mt-2">
			<UpdatePassword />
		</div>
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			on:click={async () => {
				const res = await submitHandler();

				if (res) {
					saveHandler();
				}
			}}
		>
			{$i18n.t('Save')}
		</button>
	</div>
</div>
