<script lang="ts">
	import { getContext, untrack } from 'svelte';

	import dayjs from 'dayjs';
	import localizedFormat from 'dayjs/plugin/localizedFormat';

	dayjs.extend(localizedFormat);

	import { getChatListByUserId } from '$lib/apis/chats';

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
		filter;
		untrack(() => searchHandler());
	});

	const searchHandler = async () => {
		if (!show) {
			return;
		}

		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
		}

		page = 1;

		const fetchChats = async () => {
			chatList = await getChatListByUserId(localStorage.token, user.id, page, filter);
			allChatsLoaded = (chatList ?? []).length === 0;
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

		let newChatList = [];

		newChatList = await getChatListByUserId(localStorage.token, user.id, page, filter);

		// once the bottom of the list has been reached (no results) there is no need to continue querying
		allChatsLoaded = newChatList.length === 0;

		if (newChatList.length > 0) {
			chatList = [...chatList, ...newChatList];
		}

		chatListLoading = false;
	};

	const init = async () => {
		chatList = await getChatListByUserId(localStorage.token, user.id, page, filter);
	};

	$effect(() => {
		if (show) {
			untrack(() => init());
		} else {
			page = 1;
			allChatsLoaded = false;
			chatListLoading = false;
		}
	});
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
		init();
	}}
	loadHandler={loadMoreChats}
></ChatsModal>
