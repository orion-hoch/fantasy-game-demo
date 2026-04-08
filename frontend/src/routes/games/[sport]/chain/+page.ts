import { error } from '@sveltejs/kit';

export const load = async ({ params, url }) => {
  const sport = params.sport;
  if (sport !== 'nfl' && sport !== 'nba') {
    throw error(404, 'Chain is only available for NFL and NBA');
  }

  return {
    sport,
    roomId: url.searchParams.get('room_id')
  };
};
