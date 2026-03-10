<script lang="ts">
	import { getContext, untrack } from 'svelte';

	import dayjs from 'dayjs';
	import localizedFormat from 'dayjs/plugin/localizedFormat';

	dayjs.extend(localizedFormat);

	import { getChatListByUserId } from '$lib/apis/chats';
	import { PAGE_SIZE } from '$lib/stores';

	import ChatsModal from '$lib/components/layout/ChatsModal.svelte';

	const i18n = getContext('i18n');

	let { show = $bindable(false), user } = $props();

	let chatList = $state(null);
	let page = $state(1);

	let query = $state('');
	let orderBy = $state('updated_at');
	let direction = $state('desc');

	let allChatsLoaded = $state(false);
	let chatListLoading = $state(false);

	let searchDebounceTimeout;

	let filter = $derived({
		...(query ? { query } : {}),
		...(orderBy ? { order_by: orderBy } : {}),
		...(direction ? { direction } : {})
	});

	$effect(() => {
		show;
		filter;
		untrack(() => loadFirstPage());
	});

	const loadFirstPage = async () => {
		if (!show) {
			page = 1;
			chatList = null;
			allChatsLoaded = false;
			chatListLoading = false;
			return;
		}

		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
		}

		page = 1;

		const fetchChats = async () => {
			chatList = await getChatListByUserId(localStorage.token, user.id, page, filter);
			allChatsLoaded = (chatList ?? []).length < PAGE_SIZE;
		};

		if (query === '') {
			await fetchChats();
		} else {
			searchDebounceTimeout = setTimeout(fetchChats, 500);
		}
	};

	const loadMoreChats = async () => {
		chatListLoading = true;
		page += 1;

		const newChatList = await getChatListByUserId(localStorage.token, user.id, page, filter);

		allChatsLoaded = newChatList.length < PAGE_SIZE;

		if (newChatList.length > 0) {
			chatList = [...chatList, ...newChatList];
		}

		chatListLoading = false;
	};
</script>

<ChatsModal
	bind:show
	bind:query
	bind:orderBy
	bind:direction
	title={$i18n.t("{{user}}'s Chats", {
		user: user.name.length > 32 ? `${user.name.slice(0, 32)}...` : user.name
	})}
	{chatList}
	{allChatsLoaded}
	{chatListLoading}
	onUpdate={() => {
		loadFirstPage();
	}}
	loadHandler={loadMoreChats}
></ChatsModal>
