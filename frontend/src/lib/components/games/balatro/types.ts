export type Sport = 'nfl' | 'nba';

export type Card = {
  id: string;
  player: string;
  team: string;
  pos: string;
  season: number;
  pts: number;
  fantasy_pts?: number;
  pfr_id?: string;
  headshot_url?: string;
  division?: string;
  allstar_count?: number;
  draft_pick?: number;
  college?: string;
  boss_disabled?: boolean;
  _stickerCls?: string;
  _stickerLabel?: string;
  [key: string]: unknown;
};

export type CardStats = {
  pts_pg?: number;
  trb_pg?: number;
  ast_pg?: number;
  games?: number;
  team?: string;
  pos?: string;
};

export type PlayResult = {
  hand_name?: string;
  score?: number;
  base_pts?: number;
  total_mult?: number;
  coins_earned?: number;
  broken_cards?: string[];
  card_contributions?: { id: string; contribution: number }[];
  scoring_card_ids?: string[];
  joker_mult?: number;
  joker_add_ids?: string[];
  mult_factor?: number;
  xmult_joker_ids?: string[];
};

export type Joker = {
  id: string;
  name: string;
  description: string;
  rarity: string;
  sell_value?: number;
  [key: string]: unknown;
};

export type ShopItem = {
  shop_id: string;
  item_type: string;
  name: string;
  description: string;
  cost: number;
  [key: string]: unknown;
};

export type ShopPack = {
  pack_id: string;
  name: string;
  description: string;
  cost: number;
  [key: string]: unknown;
};

export type GameState = {
  game_id: string;
  hand: Card[];
  jokers: Joker[];
  mode: string;
  floor: number;
  round: number;
  fight: number;
  boss_effect: string | null;
  level_name: string;
  target_score: number;
  current_score?: number;
  cumulative_score?: number;
  hands_remaining: number;
  discards_remaining: number;
  status: string;
  coins: number;
  skill_levels: Record<string, number>;
  combo_boosts: Record<string, number>;
  card_effects: Record<string, string[]>;
  shop_items: ShopItem[];
  shop_packs: ShopPack[];
  max_hand_size: number;
  base_discards: number;
  max_jokers: number;
  joker_state: Record<string, unknown>;
  joker_enhancements: Record<string, unknown>;
  held_cards: Card[];
  deck_cards: Card[];
  fight_discards: Card[];
  fight_played: Card[];
  reward_options?: Joker[];
  reward_coins?: number;
  next_fight?: number;
  next_boss_effect?: string | null;
  // Play hand response fields
  hand_name?: string;
  score?: number;
  base_pts?: number;
  total_mult?: number;
  coins_earned?: number;
  broken_cards?: string[];
  error?: string;
  [key: string]: unknown;
};

export type Screen = 'start' | 'playing' | 'reward' | 'shop' | 'gameover';
