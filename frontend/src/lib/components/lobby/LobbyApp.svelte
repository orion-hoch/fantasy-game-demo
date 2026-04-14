<script lang="ts">
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';

  import type { SupportedGame, LobbyRoom } from '$lib/api/lobbies';
  import { claimSeat, createLobby, fetchLobby, leaveSeat, startLobby, updateSeatMeta } from '$lib/api/lobbies';

  let {
    createMode,
    roomId,
    gameType,
    supportedGames
  }: {
    createMode: boolean;
    roomId: string | null;
    gameType: string | null;
    supportedGames: SupportedGame[];
  } = $props();

  const TOKEN_KEY = 'fantasy-multiplayer-token';
  const NAME_KEY = 'fantasy-multiplayer-name';

  let room = $state<LobbyRoom | null>(null);
  let displayName = $state('Player');
  let errorMessage = $state('');
  let isLoading = $state(false);
  let seatMetaPending = $state(false);
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let tokenValue = $state('');

  const game = $derived.by(() => {
    const type = room?.game_type || gameType;
    return supportedGames.find((entry) => entry.game_type === type) ?? null;
  });

  const isCodewords = $derived(room?.game_type === 'nfl_codewords' || room?.game_type === 'nba_codewords' || gameType === 'nfl_codewords' || gameType === 'nba_codewords');
  const codewordsStatus = $derived.by(() => codewordsReady(room));
  const canStart = $derived.by(() => {
    if (!room?.is_host) return false;
    if (room.status !== 'lobby') return false;
    if (isCodewords) return codewordsStatus.ready;
    return room.filled_seat_count >= room.min_players;
  });
  const seatNumbers = $derived.by(() => {
    if (!room) return [] as number[];
    return Array.from({ length: room.max_players }, (_, idx) => idx + 1);
  });

  function getToken() {
    if (tokenValue) return tokenValue;
    if (!browser) return '';
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(TOKEN_KEY, value);
    }
    tokenValue = value;
    return value;
  }

  function loadDisplayName() {
    if (!browser) return;
    displayName = localStorage.getItem(NAME_KEY) || 'Player';
  }

  function saveDisplayName(value: string) {
    displayName = value;
    if (!browser) return;
    localStorage.setItem(NAME_KEY, value.trim() || 'Player');
  }

  function setError(message: string) {
    errorMessage = message;
  }

  function teamLabel(team?: string | null) {
    if (team === 'A') return 'Team Red';
    if (team === 'B') return 'Team Yellow';
    return '';
  }

  function roleLabel(role?: string | null) {
    if (role === 'spymaster') return 'Clue Giver';
    if (role === 'guesser') return 'Guesser';
    return '';
  }

  function codewordsSummary(meta?: Record<string, string | null>) {
    const team = meta?.team ? teamLabel(meta.team) : null;
    const role = meta?.role ? roleLabel(meta.role) : null;
    if (team && role) return `${team} · ${role}`;
    if (team) return `${team} · pick role`;
    if (role) return `pick team · ${role}`;
    return 'pick team & role';
  }

  function codewordsReady(currentRoom: LobbyRoom | null) {
    if (!currentRoom || !(currentRoom.game_type === 'nfl_codewords' || currentRoom.game_type === 'nba_codewords')) {
      return { ready: false, reason: '' };
    }

    const filled: NonNullable<LobbyRoom['seats'][string]>[] = [];
    for (let seatNo = 1; seatNo <= 4; seatNo += 1) {
      const seat = currentRoom.seats[String(seatNo)];
      if (!seat) return { ready: false, reason: 'Need all 4 players seated' };
      filled.push(seat);
    }

    const counts = { A_spymaster: 0, A_guesser: 0, B_spymaster: 0, B_guesser: 0 };
    for (const seat of filled) {
      const team = seat.meta?.team;
      const role = seat.meta?.role;
      if (!team || !role) return { ready: false, reason: 'All players need a team and role' };
      const key = `${team}_${role}` as keyof typeof counts;
      counts[key] += 1;
    }

    const ready = counts.A_spymaster === 1 && counts.A_guesser === 1 && counts.B_spymaster === 1 && counts.B_guesser === 1;
    return ready ? { ready: true, reason: '' } : { ready: false, reason: 'Each team needs 1 clue giver and 1 guesser' };
  }

  async function loadRoom() {
    if (!roomId) return;
    try {
      const response = await fetchLobby(roomId, getToken());
      room = response.room;
      setError('');
      if (response.room.status === 'in_game' && response.room.redirect_url && browser) {
        window.location.href = response.room.redirect_url;
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load lobby');
    }
  }

  async function onCreateLobby() {
    if (!gameType) return;
    isLoading = true;
    setError('');
    try {
      const response = await createLobby(gameType, displayName.trim() || 'Host', getToken());
      if (browser && response.room_url) {
        window.location.href = response.room_url;
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create lobby');
    } finally {
      isLoading = false;
    }
  }

  async function onClaimSeat(seatNumber: number) {
    if (!roomId) return;
    try {
      const response = await claimSeat(roomId, seatNumber, displayName.trim() || 'Player', getToken());
      room = response.room;
      setError('');
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to claim seat');
    }
  }

  async function onLeaveSeat() {
    if (!roomId) return;
    try {
      const response = await leaveSeat(roomId, getToken());
      room = response.room;
      setError('');
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to leave seat');
    }
  }

  async function onSeatMeta(meta: Record<string, string | null>) {
    if (!roomId || seatMetaPending) return;
    seatMetaPending = true;
    try {
      const response = await updateSeatMeta(roomId, getToken(), meta);
      room = response.room;
      setError('');
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update role');
    } finally {
      seatMetaPending = false;
    }
  }

  async function onStart() {
    if (!roomId) return;
    isLoading = true;
    try {
      const response = await startLobby(roomId, getToken());
      room = response.room;
      setError('');
      if (response.room.redirect_url && browser) {
        window.location.href = response.room.redirect_url;
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to start game');
    } finally {
      isLoading = false;
    }
  }

  async function onCopyInvite() {
    if (!browser) return;
    try {
      await navigator.clipboard.writeText(window.location.href);
    } catch {
      setError('Could not copy invite link');
    }
  }

  onMount(() => {
    loadDisplayName();
    if (!createMode && roomId) {
      void loadRoom();
      pollTimer = setInterval(() => {
        void loadRoom();
      }, 2500);
    }
    return () => {
      if (pollTimer) clearInterval(pollTimer);
    };
  });
</script>

<section class="lobby-page">
  <header class="page-header">
    <a class="back-link" href="/?tab=multiplayer">&larr; Back</a>
    <div>
      <h2>{game?.label || room?.game_label || 'Multiplayer Lobby'}</h2>
    </div>
  </header>

  <section class="lobby-card">
    {#if createMode}
      <div class="lobby-title">Create Lobby</div>
      <div class="lobby-sub">Create a room, claim Player 1 automatically, and share the room code with everyone else.</div>
      <label class="name-field">
        <span>Your name</span>
        <input type="text" bind:value={displayName} maxlength="24" oninput={(event) => saveDisplayName((event.currentTarget as HTMLInputElement).value)} />
      </label>
      <button class="lobby-btn" type="button" disabled={isLoading} onclick={onCreateLobby}>
        {isLoading ? 'Creating...' : 'Create Lobby'}
      </button>
    {:else if room}
      <div class="lobby-title">{room.game_label} Lobby</div>
      <div class="lobby-topline">
        <div>
          <div class="seat-label">Room Code</div>
          <div class="room-code">{room.room_id}</div>
        </div>
        <button class="seat-btn alt" type="button" onclick={onCopyInvite}>Copy Invite Link</button>
      </div>

      <label class="name-field spaced">
        <span>Display name</span>
        <input type="text" bind:value={displayName} maxlength="24" oninput={(event) => saveDisplayName((event.currentTarget as HTMLInputElement).value)} />
      </label>

      {#if isCodewords}
        <div class="lobby-note">Code Words needs exactly 4 players: 2 teams, each with 1 clue giver and 1 guesser.</div>
      {/if}

      <div class="seat-grid">
        {#each seatNumbers as seatNumber}
          {@const seat = room.seats[String(seatNumber)]}
          {@const mine = room.my_seat === seatNumber}
          <article class:mine class:filled={!!seat} class="seat-card">
            <div class="seat-label">Player {seatNumber}</div>
            <div class="seat-name">{seat ? seat.name : 'Open Seat'}</div>
            <div class="seat-status">{seat ? (mine ? 'You are here' : 'Taken') : 'Available'}</div>

            {#if isCodewords && seat}
              {#if mine}
                <div class="seat-cw-block">
                  <div class="seat-cw-label">Team</div>
                  <div class="seat-cw-row">
                    <button class:selected={seat.meta.team === 'A'} class="seat-cw-btn team-a" type="button" disabled={seatMetaPending} onclick={() => onSeatMeta({ team: 'A' })}>Red</button>
                    <button class:selected={seat.meta.team === 'B'} class="seat-cw-btn team-b" type="button" disabled={seatMetaPending} onclick={() => onSeatMeta({ team: 'B' })}>Yellow</button>
                  </div>
                  <div class="seat-cw-label">Role</div>
                  <div class="seat-cw-row">
                    <button class:selected={seat.meta.role === 'spymaster'} class="seat-cw-btn" type="button" disabled={seatMetaPending} onclick={() => onSeatMeta({ role: 'spymaster' })}>Clue Giver</button>
                    <button class:selected={seat.meta.role === 'guesser'} class="seat-cw-btn" type="button" disabled={seatMetaPending} onclick={() => onSeatMeta({ role: 'guesser' })}>Guesser</button>
                  </div>
                </div>
              {:else}
                <div class="seat-cw-summary">{codewordsSummary(seat.meta)}</div>
              {/if}
            {/if}

            {#if seat}
              {#if mine}
                <button class="seat-btn alt" type="button" onclick={onLeaveSeat}>Leave Seat</button>
              {/if}
            {:else}
              <button class="seat-btn" type="button" onclick={() => onClaimSeat(seatNumber)}>Take Seat</button>
            {/if}
          </article>
        {/each}
      </div>

      <div class="lobby-topline">
        <div class="lobby-note">
          {#if isCodewords}
            {codewordsStatus.ready ? 'Ready! Host can start the game.' : codewordsStatus.reason}
          {:else}
            {room.filled_seat_count} player{room.filled_seat_count === 1 ? '' : 's'} seated. Host can start with any {room.min_players}-{room.max_players}.
          {/if}
        </div>
        {#if room.is_host}
          <button class="lobby-btn" type="button" disabled={!canStart || isLoading} onclick={onStart}>
            {isLoading ? 'Starting...' : 'Start Game'}
          </button>
        {/if}
      </div>
    {:else}
      <div class="lobby-sub">Loading lobby...</div>
    {/if}

    {#if errorMessage}
      <div class="lobby-error">{errorMessage}</div>
    {/if}
  </section>
</section>

<style>
  .lobby-page {
    max-width: 980px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    background: var(--red);
    border: 3px solid var(--border);
    box-shadow: 5px 5px 0 var(--border);
    padding: 16px 20px;
    margin-bottom: 18px;
  }

  .back-link {
    color: var(--yellow);
    text-decoration: none;
    border: 2px solid var(--yellow);
    padding: 8px 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    box-shadow: 2px 2px 0 var(--border);
    font-weight: 800;
  }

  .page-header h2,
  .lobby-title,
  .room-code,
  .seat-name {
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 3px;
  }

  .page-header h2,
  .lobby-title {
    margin: 0;
    color: var(--yellow);
  }

  .lobby-sub,
  .seat-status,
  .lobby-note,
  .seat-cw-summary,
  .lobby-error {
    color: var(--text-dim);
  }

  .lobby-card {
    background: var(--surface);
    border: 3px solid var(--border);
    box-shadow: 6px 6px 0 var(--border);
    padding: 24px;
  }

  .lobby-title {
    font-size: 1.9rem;
    margin-bottom: 8px;
  }

  .lobby-sub {
    margin-bottom: 20px;
  }

  .lobby-topline {
    display: flex;
    gap: 14px;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .seat-label,
  .seat-cw-label,
  .name-field span {
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .room-code {
    font-size: 1.5rem;
    color: var(--teal-bright);
  }

  .name-field {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }

  .name-field.spaced {
    margin-top: 16px;
  }

  .name-field input {
    background: var(--surface-2);
    color: var(--text);
    border: 2px solid var(--border-dim);
    padding: 10px 12px;
    font: inherit;
  }

  .lobby-btn,
  .seat-btn {
    background: var(--yellow);
    color: var(--text-dark);
    border: 3px solid var(--border);
    box-shadow: 4px 4px 0 var(--border);
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    text-transform: uppercase;
    cursor: pointer;
  }

  .lobby-btn {
    padding: 12px 18px;
    font-size: 1.2rem;
  }

  .seat-btn {
    padding: 9px 12px;
    font-size: 0.95rem;
  }

  .seat-btn.alt {
    background: var(--surface-3);
    color: var(--text);
  }

  .seat-grid {
    display: grid;
    gap: 14px;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    margin: 20px 0;
  }

  .seat-card {
    background: var(--surface-2);
    border: 2px solid var(--border-dim);
    padding: 16px;
    min-height: 150px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .seat-card.mine {
    border-color: var(--yellow);
  }

  .seat-card.filled {
    background: rgba(245, 199, 0, 0.06);
  }

  .seat-name {
    font-size: 1.35rem;
  }

  .seat-cw-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .seat-cw-row {
    display: flex;
    gap: 6px;
  }

  .seat-cw-btn {
    flex: 1;
    background: var(--surface-3);
    color: var(--text);
    border: 2px solid var(--border-dim);
    padding: 6px 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 800;
    cursor: pointer;
  }

  .seat-cw-btn.selected {
    background: var(--yellow);
    color: var(--text-dark);
    border-color: var(--border);
  }

  .seat-cw-btn.team-a.selected {
    background: var(--red);
    color: #fff;
  }

  .lobby-error {
    margin-top: 12px;
    min-height: 20px;
  }

  @media (max-width: 640px) {
    .page-header,
    .lobby-topline {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
