import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

export type TTBClue = {
  icon: string;
  label: string;
  text: string;
};

export type TTBHint = {
  icon: string;
  label: string;
  text: string;
};

export type TTBStartResponse = {
  game_id: string;
  clues: TTBClue[];
  hints: TTBHint[];
};

export type TTBGuessResponse = {
  error?: string;
  correct?: boolean;
  player?: string;
  exploded?: boolean;
  new_clue?: TTBClue | null;
  wrong?: number;
  skipped?: boolean;
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
  return `${apiBaseUrl}/ttb/${sport}${path}`;
}

export async function startTTBGame(
  sport: Sport,
  payload: { mode: 'classic' | 'vintage'; includeDefense?: boolean; hardMode?: boolean; minDraftYear?: number | null }
) {
  return jsonFetch<TTBStartResponse>(sportUrl(sport, '/start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: payload.mode,
      include_defense: payload.includeDefense ?? false,
      hard_mode: payload.hardMode ?? false,
      min_draft_year: payload.minDraftYear ?? null
    })
  });
}

export async function guessTTB(
  sport: Sport,
  payload: { gameId: string; guess?: string; reveal?: boolean; skip?: boolean }
) {
  return jsonFetch<TTBGuessResponse>(sportUrl(sport, '/guess'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_id: payload.gameId,
      guess: payload.guess ?? '',
      reveal: payload.reveal ?? false,
      skip: payload.skip ?? false
    })
  });
}

export async function searchTTBPlayers(sport: Sport, query: string) {
  return jsonFetch<{ results: Array<{ name: string }> }>(`${sportUrl(sport, '/search')}?q=${encodeURIComponent(query)}`);
}
