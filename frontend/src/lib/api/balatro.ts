import { apiBaseUrl } from '$lib/api/config';

export type Sport = 'nfl' | 'nba';

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
  return `${apiBaseUrl}/balatro/${sport}${path}`;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type GameState = Record<string, any>;

export async function startBalatroGame(sport: Sport, mode: string = 'normal') {
  return jsonFetch<GameState>(sportUrl(sport, '/start'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode })
  });
}

export async function playBalatroHand(sport: Sport, gameId: string, cardIds: string[]) {
  return jsonFetch<GameState>(sportUrl(sport, '/play_hand'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, card_ids: cardIds })
  });
}

export async function discardBalatroCards(sport: Sport, gameId: string, cardIds: string[]) {
  return jsonFetch<GameState>(sportUrl(sport, '/discard'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, card_ids: cardIds })
  });
}

export async function selectBalatroJoker(sport: Sport, gameId: string, jokerId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/select_joker'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, joker_id: jokerId })
  });
}

export async function previewBalatroHand(sport: Sport, gameId: string, cardIds: string[]) {
  return jsonFetch<GameState>(sportUrl(sport, '/preview'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, card_ids: cardIds })
  });
}

export async function leaveBalatroShop(sport: Sport, gameId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/leave_shop'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId })
  });
}

export async function buyBalatroItem(
  sport: Sport,
  gameId: string,
  shopId: string,
  itemType: string,
  opts?: { targetCardId?: string; targetYear?: number; newPos?: string }
) {
  return jsonFetch<GameState>(sportUrl(sport, '/buy_item'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_id: gameId,
      shop_id: shopId,
      item_type: itemType,
      target_card_id: opts?.targetCardId ?? null,
      target_year: opts?.targetYear ?? null,
      new_pos: opts?.newPos ?? null
    })
  });
}

export async function useBalatroHeldItem(
  sport: Sport,
  gameId: string,
  heldId: string,
  opts?: { targetCardId?: string; targetYear?: number; discardOnly?: boolean; newPos?: string }
) {
  return jsonFetch<GameState>(sportUrl(sport, '/use_held_item'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_id: gameId,
      held_id: heldId,
      target_card_id: opts?.targetCardId ?? null,
      target_year: opts?.targetYear ?? null,
      discard_only: opts?.discardOnly ?? false,
      new_pos: opts?.newPos ?? null
    })
  });
}

export async function getBalatroPool(sport: Sport, gameId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/get_pool'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId })
  });
}

export async function getBalatroPlayerSeasons(sport: Sport, gameId: string, cardId: string) {
  return jsonFetch<GameState>(
    `${sportUrl(sport, '/player_seasons')}?game_id=${encodeURIComponent(gameId)}&card_id=${encodeURIComponent(cardId)}`
  );
}

export async function getBalatroCardStats(sport: Sport, player: string, season: string) {
  return jsonFetch<GameState>(
    `${sportUrl(sport, '/card_stats')}?player=${encodeURIComponent(player)}&season=${encodeURIComponent(season)}`
  );
}

export async function sellBalatroJoker(sport: Sport, gameId: string, jokerId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/sell_joker'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, joker_id: jokerId })
  });
}

export async function restockBalatroShop(sport: Sport, gameId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/restock_shop'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId })
  });
}

export async function openBalatroPack(sport: Sport, gameId: string, packId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/open_pack'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, pack_id: packId })
  });
}

export async function confirmBalatroPackPicks(sport: Sport, gameId: string, selectedIds: string[]) {
  return jsonFetch<GameState>(sportUrl(sport, '/confirm_pack_picks'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, selected_ids: selectedIds })
  });
}

export async function advanceBalatroFight(sport: Sport, gameId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/advance_fight'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId })
  });
}

export async function claimBalatroReward(sport: Sport, gameId: string, choice: string, jokerId?: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/claim_reward'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, choice, joker_id: jokerId ?? null })
  });
}

export async function applyBalatroDivisionSticker(sport: Sport, gameId: string, cardId: string, newDivision: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/apply_division_sticker'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, card_id: cardId, new_division: newDivision })
  });
}

export async function startBalatroInfinity(sport: Sport, gameId: string) {
  return jsonFetch<GameState>(sportUrl(sport, '/start_infinity'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId })
  });
}
