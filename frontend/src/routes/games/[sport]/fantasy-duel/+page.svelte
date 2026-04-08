<script lang="ts">
  import FantasyDuelApp from '$lib/components/games/FantasyDuelApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba'; roomId: string | null } } = $props();
</script>

<FantasyDuelApp sport={data.sport} roomId={data.roomId} />
