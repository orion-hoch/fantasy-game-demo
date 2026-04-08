<script lang="ts">
  import LobbyApp from '$lib/components/lobby/LobbyApp.svelte';
  import type { SupportedGame } from '$lib/api/lobbies';

  let { data }: { data: { gameType: string; supportedGames: SupportedGame[] } } = $props();
</script>

<LobbyApp createMode={true} roomId={null} gameType={data.gameType} supportedGames={data.supportedGames} />
