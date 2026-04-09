import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

export type ChainCategory = {
  id: string;
  label: string;
  value?: string;
  valid_count?: number;
};

export type ChainFeedback = {
  type: 'correct' | 'wrong';
  message: string;
  examples?: string[];
  link_results?: Array<{ label: string; passed: boolean }>;
};

export type ChainPlayer = {
  name: string;
  token: string | null;
  score: number;
  lives_left?: number;
  eliminated?: boolean;
  chain?: ChainCategory[];
  validCount?: number;
  chainGuesses?: Array<{ player: string; pts: number; by?: string }>;
};

export type ChainState = {
  game_id: string;
  sport: Sport;
  mode: 'coop' | 'comp';
  started?: boolean;
  players: ChainPlayer[];
  currentPlayer: number;
  lives_left?: number;
  chain?: ChainCategory[];
  validCount?: number;
  usedPlayers: string[];
  chainGuesses?: Array<{ player: string; pts: number; by?: string }>;
  feedback?: ChainFeedback | null;
  done: boolean;
  winner?: { scores: number[]; winner_indices: number[]; winner_names: string[] } | null;
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

function sportUrl(sport: Sport, path: string) {
  return `${apiBaseUrl}/chain/${sport}${path}`;
}

export async function startChain(sport: Sport) {
  return jsonFetch<{ category: ChainCategory; valid_count: number }>(sportUrl(sport, '/start'), { method: 'POST' });
}

export async function teammateStartChain(sport: Sport, player: string) {
  return jsonFetch<{ category: ChainCategory; valid_count: number }>(sportUrl(sport, '/teammate_start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player })
  });
}

export async function guessChain(
  sport: Sport,
  payload: { player: string; gameId?: string | null; token?: string | null; chain?: ChainCategory[]; usedPlayers?: string[] }
) {
  return jsonFetch<Record<string, unknown>>(sportUrl(sport, '/guess'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_id: payload.gameId ?? '',
      player: payload.player,
      token: payload.token ?? null,
      chain: payload.chain ?? [],
      used_players: payload.usedPlayers ?? []
    })
  });
}

export async function searchChainPlayers(sport: Sport, query: string, gameId?: string | null) {
  const suffix = gameId ? `&game_id=${encodeURIComponent(gameId)}` : '';
  return jsonFetch<{ results: Array<{ name: string }> }>(`${sportUrl(sport, '/search')}?q=${encodeURIComponent(query)}${suffix}`);
}

export async function fetchChainState(sport: Sport, gameId: string) {
  return jsonFetch<{ state: ChainState }>(`${sportUrl(sport, '/state')}?game_id=${encodeURIComponent(gameId)}`);
}

export async function startLobbyChainMatch(roomId: string, token: string) {
  return jsonFetch<{ room: Record<string, unknown>; state: ChainState | null }>(
    `${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/chain/start`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token })
    }
  );
}
