<script lang="ts">
  import SelectedQuizzesApp from '$lib/components/games/SelectedQuizzesApp.svelte';

  let { data }: { data: { sport: 'nfl' | 'nba' } } = $props();
</script>

<SelectedQuizzesApp sport={data.sport} />
