import { apiBaseUrl } from '$lib/api/config';
import { rolloutOrder, surfaces, type Surface } from '$lib/migration/rollout';

type InventorySurface = {
  name: string;
  legacy_route: string;
  target_route: string;
  status: Surface['status'];
  notes: string;
};

type InventoryResponse = {
  strategy: string;
  next_slice: string[];
  surfaces: InventorySurface[];
};

export type MigrationPageData = {
  strategy: string;
  nextSlice: string[];
  rolloutOrder: string[];
  surfaces: Surface[];
  source: 'backend' | 'fallback';
};

function normalizeSurface(surface: InventorySurface): Surface {
  const existing = surfaces.find((candidate) => candidate.name === surface.name);
  return {
    name: surface.name,
    sport: existing?.sport ?? 'shared',
    legacyRoute: surface.legacy_route,
    targetRoute: surface.target_route,
    status: surface.status,
    notes: surface.notes
  };
}

export async function loadMigrationData(fetchFn: typeof fetch): Promise<MigrationPageData> {
  try {
    const response = await fetchFn(`${apiBaseUrl}/migration/inventory`);
    if (!response.ok) {
      throw new Error(`inventory request failed: ${response.status}`);
    }
    const inventory = (await response.json()) as InventoryResponse;
    return {
      strategy: inventory.strategy,
      nextSlice: inventory.next_slice,
      rolloutOrder,
      surfaces: inventory.surfaces.map(normalizeSurface),
      source: 'backend'
    };
  } catch {
    return {
      strategy: 'strangler',
      nextSlice: [
        'health and migration inventory endpoints',
        'SvelteKit shell and migration dashboard',
        'multiplayer lobby API extraction',
        'Bullseye NFL/NBA as first migrated game family'
      ],
      rolloutOrder,
      surfaces,
      source: 'fallback'
    };
  }
}
