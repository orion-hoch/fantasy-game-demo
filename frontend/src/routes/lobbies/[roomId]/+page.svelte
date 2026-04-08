<script lang="ts">
  import LobbyApp from '$lib/components/lobby/LobbyApp.svelte';
  import type { SupportedGame } from '$lib/api/lobbies';

  let { data }: { data: { roomId: string; supportedGames: SupportedGame[] } } = $props();
</script>

<LobbyApp createMode={false} roomId={data.roomId} gameType={null} supportedGames={data.supportedGames} />
