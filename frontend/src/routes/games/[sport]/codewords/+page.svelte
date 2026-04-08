<script lang="ts">
  import CodewordsApp from '$lib/components/games/CodewordsApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba'; roomId: string | null } } = $props();
</script>

<CodewordsApp sport={data.sport} roomId={data.roomId} />
