<script lang="ts">
  import ChainApp from '$lib/components/games/ChainApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba'; roomId: string | null } } = $props();
</script>

<ChainApp sport={data.sport} roomId={data.roomId} />
