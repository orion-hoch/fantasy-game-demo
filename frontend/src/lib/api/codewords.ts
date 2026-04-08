import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

export type CodewordsCard = {
  index: number;
  name: string;
  headshot_url: string;
  team: string | null;
  revealed: boolean;
};

export type CodewordsPlayer = {
  name: string;
  team: string;
  role: string;
};

export type CodewordsClue = {
  text: string;
  number: number;
  remaining: number;
  guesses_made: number;
};

export type CodewordsHistoryEntry = {
  team: string;
  clue: string;
  number: number;
  guesses: Array<{ result: string }>;
};

export type CodewordsState = {
  game_id: string;
  sport: string;
  mode: string;
  board: CodewordsCard[];
  players: CodewordsPlayer[];
  starting_team: string;
  current_team: string;
  current_phase: string;
  current_clue: CodewordsClue | null;
  history: CodewordsHistoryEntry[];
  winner: string | null;
  done: boolean;
  team_a_total: number;
  team_b_total: number;
  team_a_revealed: number;
  team_b_revealed: number;
  team_a_remaining: number;
  team_b_remaining: number;
  you: { team: string; role: string; name: string } | null;
  can_see_full_key: boolean;
};

export type CodewordsActionResult = {
  state: CodewordsState | null;
  error: string | null;
};

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const text = await response.text();
  let data: unknown = {};
  if (text) data = JSON.parse(text);
  if (!response.ok) {
    const message =
      typeof data === 'object' && data && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : typeof data === 'object' && data && 'error' in data
          ? String((data as { error: unknown }).error)
          : 'Request failed';
    throw new Error(message);
  }
  return data as T;
}

export async function fetchCodewordsState(gameId: string, token: string) {
  return jsonFetch<{ state: CodewordsState }>(
    `${apiBaseUrl}/codewords/state?game_id=${encodeURIComponent(gameId)}&token=${encodeURIComponent(token)}`
  );
}

export async function submitCodewordsClue(gameId: string, token: string, clue: string, number: number) {
  return jsonFetch<CodewordsActionResult>(`${apiBaseUrl}/codewords/clue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, token, clue, number })
  });
}

export async function submitCodewordsGuess(gameId: string, token: string, index: number) {
  return jsonFetch<CodewordsActionResult>(`${apiBaseUrl}/codewords/guess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, token, index })
  });
}

export async function endCodewordsTurn(gameId: string, token: string) {
  return jsonFetch<CodewordsActionResult>(`${apiBaseUrl}/codewords/end_turn`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, token })
  });
}
