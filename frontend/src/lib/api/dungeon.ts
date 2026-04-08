import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

export type DungeonItem = {
  id: string;
  name: string;
  description: string;
  rarity: string;
  icon?: string;
  [key: string]: unknown;
};

export type DungeonQuestion = {
  id: string;
  text: string;
  category: string;
  difficulty: string;
  answer_type: string;
  [key: string]: unknown;
};

export type DungeonEncounter = {
  theme?: { name: string; prompt: string };
  enemy: {
    name: string;
    hp: number;
    attack: number;
    damage?: number;
    is_boss?: boolean;
    phase_goal?: number;
    icon?: string;
    [key: string]: unknown;
  };
  question: DungeonQuestion;
};

export type DungeonAnswerResult = {
  correct: boolean;
  answer: string;
  damage?: number;
  enemy_damage?: number;
  message?: string;
  [key: string]: unknown;
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

function sportUrl(sport: Sport, path: string) {
  return `${apiBaseUrl}/dungeon/${sport}${path}`;
}

export async function fetchDungeonRewards(sport: Sport, floor: number, items: DungeonItem[]) {
  return jsonFetch<{ rewards: DungeonItem[] }>(sportUrl(sport, '/rewards'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ floor, items })
  });
}

export async function fetchDungeonEncounter(sport: Sport, floor: number, items: DungeonItem[], usedQuestions: string[]) {
  return jsonFetch<DungeonEncounter>(sportUrl(sport, '/encounter'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ floor, items, used_questions: usedQuestions })
  });
}

export async function submitDungeonAnswer(sport: Sport, question: DungeonQuestion, items: DungeonItem[], answer: string) {
  return jsonFetch<DungeonAnswerResult>(sportUrl(sport, '/answer'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, items, answer })
  });
}

export async function searchDungeonPlayers(sport: Sport, query: string, items: DungeonItem[], question: DungeonQuestion | null) {
  return jsonFetch<{ results: string[] }>(sportUrl(sport, '/search'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, items, question })
  });
}
