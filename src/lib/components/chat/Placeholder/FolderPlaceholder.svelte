<script lang="ts">
	import { untrack } from 'svelte';

	import ChatList from './ChatList.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getChatListByFolderId } from '$lib/apis/chats';

	let { folder = null } = $props();

	let page = $state(1);

	let chats: any[] | null = $state(null);
	let chatListLoading = $state(false);
	let allChatsLoaded = $state(false);

	const loadChats = async () => {
		chatListLoading = true;

		page += 1;

		let newChatList: any[] = [];

		newChatList = await getChatListByFolderId(localStorage.token, folder.id, page).catch(
			(error) => {
				console.error(error);
				return [];
			}
		);

		allChatsLoaded = newChatList.length === 0;
		chats = [...(chats || []), ...(newChatList || [])];

		chatListLoading = false;
	};

	const setChatList = async () => {
		chats = null;
		page = 1;
		allChatsLoaded = false;
		chatListLoading = false;

		if (folder && folder.id) {
			const res = await getChatListByFolderId(localStorage.token, folder.id, page);

			if (res) {
				chats = res;
			} else {
				chats = [];
			}
		} else {
			chats = [];
		}
	};

	$effect(() => {
		if (folder) {
			untrack(() => setChatList());
		}
	});
</script>

<div>
	<div class="">
		{#if chats !== null}
			<ChatList {chats} {chatListLoading} {allChatsLoaded} loadHandler={loadChats} />
		{:else}
			<div class="py-10">
				<Spinner />
			</div>
		{/if}
	</div>
</div>
