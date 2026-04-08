<script lang="ts">
  import BullseyeApp from '$lib/components/games/BullseyeApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba'; roomId: string | null; soloMode: boolean } } = $props();
</script>

<BullseyeApp sport={data.sport} roomId={data.roomId} soloMode={data.soloMode} />
