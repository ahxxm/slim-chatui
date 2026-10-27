<script lang="ts">
	import TagItem from './TagItem.svelte';
	export let tags: { name: string }[] = [];
	export let disabled = false;
	export let onDelete: (name: string) => void = () => {};
</script>

{#each tags as tag (tag.name)}
	<TagItem {tag} {disabled} onDelete={() => onDelete(tag.name)} />
{/each}
