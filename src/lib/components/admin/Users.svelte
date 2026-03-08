<script>
	import { onMount } from 'svelte';

	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';

	import UserList from './Users/UserList.svelte';

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
		}
	});
</script>

<div class="flex flex-col w-full h-full pb-2">
	<div class="flex-1 mt-1 lg:mt-0 px-[16px] lg:pr-[16px] lg:pl-0 overflow-y-scroll">
		<UserList />
	</div>
</div>
