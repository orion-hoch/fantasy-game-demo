import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

export type BullseyePrompt = {
  team_filter?: string | null;
  team_filter_label?: string | null;
  year_min: number;
  year_max: number;
  accolade?: string | null;
};

export type BullseyePick = {
  player: string;
  season: number;
  team: string;
  stat_val: number;
};

export type BullseyeWinner = {
  totals: number[];
  diffs: number[];
  winner_indices: number[];
  winner_names: string[];
};

export type BullseyeState = {
  game_id: string;
  stat: string;
  target: number;
  players: string[];
  player_tokens: (string | null)[];
  prompts: BullseyePrompt[];
  picks: (BullseyePick | null)[][];
  used_pairs: [string, number][];
  done: boolean;
  winner: BullseyeWinner | null;
};

export type BullseyeSeason = {
  player: string;
  season: number;
  team: string;
  stat_val: number;
};

type StartResponse = { game_id: string; state: BullseyeState };
type SearchResponse = { results: Array<{ player: string; season: number | null; team: string | null; stat_val: number }> };
type StateResponse = { state: BullseyeState };
type YearsResponse = { years: number[]; error?: string };
type SeasonsResponse = { seasons: BullseyeSeason[] };
type PickResponse = { ok: boolean; state: BullseyeState | null; msg: string };

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const text = await response.text();
  let data: unknown = {};
  if (text) {
    data = JSON.parse(text);
  }
  if (!response.ok) {
    const message = typeof data === 'object' && data && 'detail' in data ? String((data as { detail: unknown }).detail) : 'Request failed';
    throw new Error(message);
  }
  return data as T;
}

function sportUrl(sport: Sport, path: string): string {
  return `${apiBaseUrl}/bullseye/${sport}${path}`;
}

export async function startBullseyeGame(sport: Sport, playerNames: string[], playerTokens?: string[]) {
  return jsonFetch<StartResponse>(sportUrl(sport, '/start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_names: playerNames, player_tokens: playerTokens })
  });
}

export async function fetchBullseyeState(sport: Sport, gameId: string) {
  return jsonFetch<StateResponse>(`${sportUrl(sport, '/state')}?game_id=${encodeURIComponent(gameId)}`);
}

export async function searchBullseyePlayers(sport: Sport, gameId: string, promptIdx: number, query: string) {
  return jsonFetch<SearchResponse>(
    `${sportUrl(sport, '/search')}?game_id=${encodeURIComponent(gameId)}&prompt_idx=${promptIdx}&q=${encodeURIComponent(query)}`
  );
}

export async function fetchBullseyeSeasons(sport: Sport, gameId: string, promptIdx: number, playerName: string) {
  return jsonFetch<SeasonsResponse>(
    `${sportUrl(sport, '/seasons')}?game_id=${encodeURIComponent(gameId)}&prompt_idx=${promptIdx}&player=${encodeURIComponent(playerName)}`
  );
}

export async function fetchBullseyeYears(sport: Sport, gameId: string, promptIdx: number, playerName: string) {
  return jsonFetch<YearsResponse>(
    `${sportUrl(sport, '/years')}?game_id=${encodeURIComponent(gameId)}&prompt_idx=${promptIdx}&player=${encodeURIComponent(playerName)}`
  );
}

export async function submitBullseyePick(
  sport: Sport,
  payload: { gameId: string; playerName: string; season: number; promptIdx: number; playerIdx: number; token?: string | null }
) {
  return jsonFetch<PickResponse>(sportUrl(sport, '/pick'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_id: payload.gameId,
      player_name: payload.playerName,
      season: payload.season,
      prompt_idx: payload.promptIdx,
      player_idx: payload.playerIdx,
      token: payload.token ?? null
    })
  });
}
