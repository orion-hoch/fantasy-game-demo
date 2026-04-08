<script lang="ts">
  import BalatroApp from '$lib/components/games/balatro/BalatroApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba' } } = $props();
</script>

<BalatroApp sport={data.sport} />
