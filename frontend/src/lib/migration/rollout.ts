export type SurfaceStatus = 'legacy' | 'scaffolded' | 'in_migration' | 'cutover_ready' | 'cutover_done';

export type Surface = {
  name: string;
  sport: 'shared' | 'nfl' | 'nba';
  legacyRoute: string;
  targetRoute: string;
  status: SurfaceStatus;
  notes: string;
};

export const rolloutOrder = [
  'Home shell and shared navigation',
  'Multiplayer lobby',
  'Bullseye NFL/NBA',
  'Fantasy Duel NFL/NBA',
  'Chain NFL/NBA',
  'Code Words NFL/NBA',
  'TTB NFL/NBA',
  'Dungeon Adventure NFL/NBA',
  'Balatro NFL/NBA',
  'Final Flask retirement'
];

export const surfaces: Surface[] = [
  { name: 'Home', sport: 'shared', legacyRoute: '/', targetRoute: '/', status: 'cutover_done', notes: 'Flask now redirects into the Svelte home.' },
  { name: 'Lobby', sport: 'shared', legacyRoute: '/multiplayer/<game_type>', targetRoute: '/multiplayer/nfl_bullseye', status: 'cutover_done', notes: 'Flask lobby pages now redirect into the migrated Svelte lobby.' },
  { name: 'NFL Bullseye', sport: 'nfl', legacyRoute: '/nfl_bullseye', targetRoute: '/games/nfl/bullseye?solo=1', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Bullseye.' },
  { name: 'NBA Bullseye', sport: 'nba', legacyRoute: '/nba_bullseye', targetRoute: '/games/nba/bullseye?solo=1', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Bullseye.' },
  { name: 'NFL Fantasy Duel', sport: 'nfl', legacyRoute: '/starting6', targetRoute: '/games/nfl/fantasy-duel', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Fantasy Duel.' },
  { name: 'NBA Fantasy Duel', sport: 'nba', legacyRoute: '/nba_starting5', targetRoute: '/games/nba/fantasy-duel', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Fantasy Duel.' },
  { name: 'NFL Chain', sport: 'nfl', legacyRoute: '/chain', targetRoute: '/games/nfl/chain', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Chain.' },
  { name: 'NBA Chain', sport: 'nba', legacyRoute: '/nba_chain', targetRoute: '/games/nba/chain', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Chain.' },
  { name: 'NFL Code Words', sport: 'nfl', legacyRoute: '/nfl_codewords', targetRoute: '/games/nfl/codewords', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Code Words.' },
  { name: 'NBA Code Words', sport: 'nba', legacyRoute: '/nba_codewords', targetRoute: '/games/nba/codewords', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Code Words.' },
  { name: 'NFL TTB', sport: 'nfl', legacyRoute: '/ttb', targetRoute: '/games/nfl/ttb', status: 'cutover_done', notes: 'Flask page route now redirects into migrated TTB.' },
  { name: 'NBA TTB', sport: 'nba', legacyRoute: '/nba_ttb', targetRoute: '/games/nba/ttb', status: 'cutover_done', notes: 'Flask page route now redirects into migrated TTB.' },
  { name: 'NFL Dungeon', sport: 'nfl', legacyRoute: '/dungeon_adventure', targetRoute: '/games/nfl/dungeon', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Dungeon Adventure.' },
  { name: 'NBA Dungeon', sport: 'nba', legacyRoute: '/nba_dungeon_adventure', targetRoute: '/games/nba/dungeon', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Dungeon Adventure.' },
  { name: 'NFL Balatro', sport: 'nfl', legacyRoute: '/nfl_balatro', targetRoute: '/games/nfl/balatro', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Balatro.' },
  { name: 'NBA Balatro', sport: 'nba', legacyRoute: '/nba_balatro', targetRoute: '/games/nba/balatro', status: 'cutover_done', notes: 'Flask page route now redirects into migrated Balatro.' }
];
