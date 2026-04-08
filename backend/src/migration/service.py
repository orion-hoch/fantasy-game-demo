"""Static migration inventory for the strangler rollout."""

from src.migration.schemas import MigrationInventory, SurfaceSummary


def get_inventory() -> MigrationInventory:
    return MigrationInventory(
        strategy="strangler",
        next_slice=[
            "remove remaining Flask page rendering",
            "replace compatibility bridges with native Svelte screens where worth the cost",
            "unify deployment so the Svelte frontend is served directly",
            "retire duplicated legacy APIs after traffic verification",
        ],
        surfaces=[
            SurfaceSummary(name="Home", legacy_route="/", target_route="/", status="cutover_done", notes="Flask now redirects into the Svelte home."),
            SurfaceSummary(name="Lobby", legacy_route="/multiplayer/<game_type>", target_route="/multiplayer/nfl_bullseye", status="cutover_done", notes="Flask lobby pages now redirect into the migrated Svelte lobby."),
            SurfaceSummary(name="NFL Bullseye", legacy_route="/nfl_bullseye", target_route="/games/nfl/bullseye?solo=1", status="cutover_done", notes="Flask page route now redirects into migrated Bullseye."),
            SurfaceSummary(name="NBA Bullseye", legacy_route="/nba_bullseye", target_route="/games/nba/bullseye?solo=1", status="cutover_done", notes="Flask page route now redirects into migrated Bullseye."),
            SurfaceSummary(name="NFL Fantasy Duel", legacy_route="/starting6", target_route="/games/nfl/fantasy-duel", status="cutover_done", notes="Flask page route now redirects into migrated Fantasy Duel."),
            SurfaceSummary(name="NBA Fantasy Duel", legacy_route="/nba_starting5", target_route="/games/nba/fantasy-duel", status="cutover_done", notes="Flask page route now redirects into migrated Fantasy Duel."),
            SurfaceSummary(name="NFL Chain", legacy_route="/chain", target_route="/games/nfl/chain", status="cutover_done", notes="Flask page route now redirects into migrated Chain."),
            SurfaceSummary(name="NBA Chain", legacy_route="/nba_chain", target_route="/games/nba/chain", status="cutover_done", notes="Flask page route now redirects into migrated Chain."),
            SurfaceSummary(name="NFL Code Words", legacy_route="/nfl_codewords", target_route="/games/nfl/codewords", status="cutover_done", notes="Flask page route now redirects into migrated Code Words."),
            SurfaceSummary(name="NBA Code Words", legacy_route="/nba_codewords", target_route="/games/nba/codewords", status="cutover_done", notes="Flask page route now redirects into migrated Code Words."),
            SurfaceSummary(name="NFL TTB", legacy_route="/ttb", target_route="/games/nfl/ttb", status="cutover_done", notes="Flask page route now redirects into migrated TTB."),
            SurfaceSummary(name="NBA TTB", legacy_route="/nba_ttb", target_route="/games/nba/ttb", status="cutover_done", notes="Flask page route now redirects into migrated TTB."),
            SurfaceSummary(name="NFL Dungeon", legacy_route="/dungeon_adventure", target_route="/games/nfl/dungeon", status="cutover_done", notes="Flask page route now redirects into migrated Dungeon Adventure."),
            SurfaceSummary(name="NBA Dungeon", legacy_route="/nba_dungeon_adventure", target_route="/games/nba/dungeon", status="cutover_done", notes="Flask page route now redirects into migrated Dungeon Adventure."),
            SurfaceSummary(name="NFL Balatro", legacy_route="/nfl_balatro", target_route="/games/nfl/balatro", status="cutover_done", notes="Flask page route now redirects into migrated Balatro."),
            SurfaceSummary(name="NBA Balatro", legacy_route="/nba_balatro", target_route="/games/nba/balatro", status="cutover_done", notes="Flask page route now redirects into migrated Balatro."),
        ],
    )
