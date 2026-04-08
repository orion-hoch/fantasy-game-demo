import { fetchSupportedGames } from '$lib/api/lobbies';

export const ssr = false;

export const load = async ({ params }) => {
  const { games } = await fetchSupportedGames();
  return {
    gameType: params.gameType,
    supportedGames: games
  };
};
