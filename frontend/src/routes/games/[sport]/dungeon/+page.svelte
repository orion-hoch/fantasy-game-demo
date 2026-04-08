<script lang="ts">
  import DungeonApp from '$lib/components/games/DungeonApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba' } } = $props();
</script>

<DungeonApp sport={data.sport} />
