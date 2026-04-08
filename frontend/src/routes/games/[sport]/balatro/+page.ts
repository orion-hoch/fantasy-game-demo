import { error } from '@sveltejs/kit';

export const load = async ({ params }) => {
  const sport = params.sport;
  if (sport !== 'nfl' && sport !== 'nba') {
    throw error(404, 'Balatro is only available for NFL and NBA');
  }

  return {
    sport
  };
};
