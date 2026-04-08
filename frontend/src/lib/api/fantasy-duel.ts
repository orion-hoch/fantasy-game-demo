import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

export type FantasyDuelPick = {
  player: string;
  pos: string;
  ppr: number;
  season: number;
  team: string;
  bonusMultiplier?: number;
};

export type FantasyDuelPlayer = {
  name: string;
  token: string | null;
  roster: Record<string, FantasyDuelPick | null>;
};

export type FantasyDuelState = {
  game_id: string;
  players: FantasyDuelPlayer[];
  currentPlayer: number;
  currentTeam: string | null;
  bonus: { pos: string; decade: number };
  pickedPlayers: string[];
  skipsUsed: number[];
  done: boolean;
  winner: { totals: number[]; winner_indices: number[]; winner_names: string[] } | null;
};

type StartResponse = { game_id: string; state: FantasyDuelState };
type StateResponse = { state: FantasyDuelState };
type SearchResponse = { results: string[] };
type YearsResponse = { years: number[] };
type PickResponse = { ok: boolean; state: FantasyDuelState | null; msg: string };

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

function sportUrl(sport: Sport, path: string): string {
  return `${apiBaseUrl}/fantasy-duel/${sport}${path}`;
}

export async function startFantasyDuelGame(sport: Sport, playerNames: string[], playerTokens?: string[]) {
  return jsonFetch<StartResponse>(sportUrl(sport, '/start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_names: playerNames, player_tokens: playerTokens })
  });
}

export async function fetchFantasyDuelState(sport: Sport, gameId: string) {
  return jsonFetch<StateResponse>(`${sportUrl(sport, '/state')}?game_id=${encodeURIComponent(gameId)}`);
}

export async function searchFantasyDuelPlayers(sport: Sport, gameId: string, query: string) {
  return jsonFetch<SearchResponse>(`${sportUrl(sport, '/search')}?game_id=${encodeURIComponent(gameId)}&q=${encodeURIComponent(query)}`);
}

export async function fetchFantasyDuelYears(sport: Sport, gameId: string, player: string) {
  return jsonFetch<YearsResponse>(`${sportUrl(sport, '/years')}?game_id=${encodeURIComponent(gameId)}&player=${encodeURIComponent(player)}`);
}

export async function submitFantasyDuelPick(sport: Sport, payload: { gameId: string; playerName: string; season: number; token?: string | null }) {
  return jsonFetch<PickResponse>(sportUrl(sport, '/pick'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: payload.gameId, player_name: payload.playerName, season: payload.season, token: payload.token ?? null })
  });
}

export async function passFantasyDuelTurn(sport: Sport, gameId: string, token?: string | null) {
  return jsonFetch<PickResponse>(sportUrl(sport, '/pass'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, token: token ?? null })
  });
}
