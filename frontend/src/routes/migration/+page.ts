import { loadMigrationData } from '$lib/api/migration';

export const load = async ({ fetch }) => {
  return loadMigrationData(fetch);
};
