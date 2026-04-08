import { apiBaseUrl } from '$lib/api/config';

export type SupportedGame = {
  game_type: string;
  label: string;
  route: string;
  min_players: number;
  max_players: number;
};

export type LobbySeat = {
  name: string;
  meta: Record<string, string | null>;
};

export type LobbyRoom = {
  room_id: string;
  game_type: string;
  game_label: string;
  status: 'lobby' | 'in_game';
  created_at: number;
  updated_at: number;
  game_id: string | null;
  redirect_url: string | null;
  min_players: number;
  max_players: number;
  my_seat: number | null;
  is_host: boolean;
  filled_seat_count: number;
  seats: Record<string, LobbySeat | null>;
};

export type LobbyResponse = {
  room: LobbyRoom;
  room_url?: string | null;
};

export type LobbyGameStateResponse = {
  room: LobbyRoom;
  state: Record<string, unknown> | null;
};

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const text = await response.text();
  let data: unknown = {};
  if (text) data = JSON.parse(text);
  if (!response.ok) {
    const message = typeof data === 'object' && data && 'detail' in data ? String((data as { detail: unknown }).detail) : 'Request failed';
    throw new Error(message);
  }
  return data as T;
}

export async function fetchSupportedGames() {
  return jsonFetch<{ games: SupportedGame[] }>(`${apiBaseUrl}/lobbies/games`);
}

export async function createLobby(gameType: string, playerName: string, token: string) {
  return jsonFetch<LobbyResponse>(`${apiBaseUrl}/lobbies/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_type: gameType, player_name: playerName, token })
  });
}

export async function fetchLobby(roomId: string, token: string) {
  return jsonFetch<LobbyResponse>(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}?token=${encodeURIComponent(token)}`);
}

export async function claimSeat(roomId: string, seatNumber: number, playerName: string, token: string) {
  return jsonFetch<LobbyResponse>(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/claim-seat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, player_name: playerName, seat_number: seatNumber })
  });
}

export async function leaveSeat(roomId: string, token: string) {
  return jsonFetch<LobbyResponse>(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/leave-seat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
}

export async function updateSeatMeta(roomId: string, token: string, meta: Record<string, string | null>) {
  return jsonFetch<LobbyResponse>(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/seat-meta`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, meta })
  });
}

export async function startLobby(roomId: string, token: string) {
  return jsonFetch<LobbyResponse>(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
}

export async function rematchLobby(roomId: string, token: string) {
  return jsonFetch<LobbyResponse>(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/rematch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });
}

export async function fetchLobbyGameState(roomId: string, token: string) {
  return jsonFetch<LobbyGameStateResponse>(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/game-state?token=${encodeURIComponent(token)}`);
}
