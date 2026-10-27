<script lang="ts">
	import { saveAs } from '#lib/utils/index.js';

	import { downloadDatabase } from '#lib/apis/utils/index.js';
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getAllUserChats } from '#lib/apis/chats/index.js';
	import { getAllUsers } from '#lib/apis/users/index.js';
	import { exportConfig, importConfig } from '#lib/apis/configs/index.js';
	import type { SessionUser } from '#lib/stores/index.js';

	const i18n = getContext('i18n');

	const exportAllUserChats = async () => {
		let blob = new Blob([JSON.stringify(await getAllUserChats(localStorage.token))], {
			type: 'application/json'
		});
		saveAs(blob, `all-chats-export-${Date.now()}.json`);
	};

	const exportUsers = async () => {
		const users = await getAllUsers(localStorage.token);

		const headers = ['id', 'name', 'email', 'role'];

		const csv = [
			headers.join(','),
			...users.users.map((user: SessionUser) => {
				return headers
					.map((header) => {
						if (user[header] === null || user[header] === undefined) {
							return '';
						}
						return `"${String(user[header]).replace(/"/g, '""')}"`;
					})
					.join(',');
			})
		].join('\n');

		const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
		saveAs(blob, 'users.csv');
	};
</script>

<div class="flex flex-col h-full justify-between text-sm">
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		<input
			id="config-json-input"
			hidden
			type="file"
			accept=".json"
			onchange={(e) => {
				const input = e.currentTarget;
				const file = input.files?.[0];
				if (!file) return;

				const reader = new FileReader();
				reader.onload = async () => {
					if (typeof reader.result !== 'string') return;
					const res = await importConfig(localStorage.token, JSON.parse(reader.result)).catch(
						(error) => {
							toast.error(`${error}`);
						}
					);

					if (res) {
						toast.success($i18n.t('Config imported successfully'));
					}
					input.value = '';
				};

				reader.readAsText(file);
			}}
		/>

		<div>
			<div class="mb-1 text-sm font-medium">{$i18n.t('Config')}</div>

			<div>
				<div class="py-0.5 flex w-full justify-between">
					<div class="self-center text-xs">{$i18n.t('Import Config')}</div>
					<label
						for="config-json-input"
						class="p-1 px-3 text-xs flex rounded-sm transition cursor-pointer"
					>
						<span class="self-center">{$i18n.t('Import')}</span>
					</label>
				</div>
			</div>

			<div>
				<div class="py-0.5 flex w-full justify-between">
					<div class="self-center text-xs">{$i18n.t('Export Config')}</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={async () => {
							const config = await exportConfig(localStorage.token);
							const blob = new Blob([JSON.stringify(config)], {
								type: 'application/json'
							});
							saveAs(blob, `config-${Date.now()}.json`);
						}}
						type="button"
					>
						<span class="self-center">{$i18n.t('Export')}</span>
					</button>
				</div>
			</div>
		</div>

		<div>
			<div class="mb-1 text-sm font-medium">{$i18n.t('Database')}</div>

			<div>
				<div class="py-0.5 flex w-full justify-between">
					<div class="self-center text-xs">{$i18n.t('Download Database')}</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							downloadDatabase(localStorage.token).catch((error) => {
								toast.error(`${error}`);
							});
						}}
						type="button"
					>
						<span class="self-center">{$i18n.t('Download')}</span>
					</button>
				</div>
			</div>

			<div>
				<div class="py-0.5 flex w-full justify-between">
					<div class="self-center text-xs">{$i18n.t('Export All Chats (All Users)')}</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							exportAllUserChats();
						}}
						type="button"
					>
						<span class="self-center">{$i18n.t('Export')}</span>
					</button>
				</div>
			</div>

			<div>
				<div class="py-0.5 flex w-full justify-between">
					<div class="self-center text-xs">{$i18n.t('Export Users')}</div>
					<button
						class="p-1 px-3 text-xs flex rounded-sm transition"
						onclick={() => {
							exportUsers();
						}}
						type="button"
					>
						<span class="self-center">{$i18n.t('Export')}</span>
					</button>
				</div>
			</div>
		</div>
	</div>
</div>
