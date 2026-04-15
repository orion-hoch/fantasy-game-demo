import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

export type QuizSummary = {
  id: string;
  title: string;
  prompt: string;
  time_limit_seconds: number;
  total_answers: number;
};

export type QuizListResponse = {
  quizzes: QuizSummary[];
};

export type QuizSlot = {
  hints: Record<string, string> | null;
};

export type QuizStartResponse = {
  game_id: string;
  quiz_id: string;
  title: string;
  prompt: string;
  time_limit_seconds: number;
  total_answers: number;
  deadline_ms: number;
  slots: QuizSlot[];
  default_order_hint_key: string | null;
  default_order_direction: 'low' | 'high';
};

export type QuizGuessResponse = {
  matched: string | null;
  matched_index: number | null;
  duplicate: boolean;
  found_count: number;
  total_answers: number;
  time_left_seconds: number;
  finished: boolean;
};

export type QuizAnswerStatus = {
  canonical: string;
  found: boolean;
  hints: Record<string, string> | null;
};

export type QuizFinishResponse = {
  quiz_id: string;
  title: string;
  prompt: string;
  answers: QuizAnswerStatus[];
  found_count: number;
  total_answers: number;
  elapsed_seconds: number;
  time_limit_seconds: number;
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
        : 'Request failed';
    throw new Error(message);
  }
  return data as T;
}

function quizUrl(sport: Sport, path = '') {
  return `${apiBaseUrl}/selected-quizzes/${sport}${path}`;
}

export async function listQuizzes(sport: Sport): Promise<QuizListResponse> {
  return jsonFetch<QuizListResponse>(quizUrl(sport));
}

export async function startQuiz(sport: Sport, quizId: string): Promise<QuizStartResponse> {
  return jsonFetch<QuizStartResponse>(quizUrl(sport, `/${encodeURIComponent(quizId)}/start`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}'
  });
}

export async function guessQuiz(
  sport: Sport,
  quizId: string,
  payload: { gameId: string; guess: string }
): Promise<QuizGuessResponse> {
  return jsonFetch<QuizGuessResponse>(quizUrl(sport, `/${encodeURIComponent(quizId)}/guess`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: payload.gameId, guess: payload.guess })
  });
}

export async function finishQuiz(sport: Sport, quizId: string, gameId: string): Promise<QuizFinishResponse> {
  return jsonFetch<QuizFinishResponse>(quizUrl(sport, `/${encodeURIComponent(quizId)}/finish`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, guess: '' })
  });
}
