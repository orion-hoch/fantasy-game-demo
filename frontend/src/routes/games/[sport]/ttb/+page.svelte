<script lang="ts">
  import TTBApp from '$lib/components/games/TTBApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba' } } = $props();
</script>

<TTBApp sport={data.sport} />
