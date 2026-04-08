export const load = async ({ params }) => {
  return {
    sport: params.sport,
    slug: params.slug
  };
};
