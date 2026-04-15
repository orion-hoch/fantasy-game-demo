<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/stores';

  type Tab = 'about' | 'nfl' | 'nba' | 'multiplayer';

  let activeTab = $state<Tab>('about');
  let joinCode = $state('');
  let joinError = $state('');

  if (browser) {
    const param = new URLSearchParams(window.location.search).get('tab');
    if (param === 'nfl' || param === 'nba' || param === 'multiplayer') activeTab = param;
  }

  function switchTab(tab: Tab) {
    activeTab = tab;
    if (browser) {
      const url = tab === 'about' ? '/' : `/?tab=${tab}`;
      history.replaceState(null, '', url);
    }
  }

  function joinLobby() {
    const code = joinCode.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (!code) { joinError = 'Enter a lobby code.'; return; }
    joinError = '';
    window.location.href = `/lobbies/${encodeURIComponent(code)}`;
  }

  type GameDef = { name: string; desc: string; href: string; accent: 'yellow' | 'red' };

  const nflGames: GameDef[] = [
    { name: 'Chain Game', desc: 'Build a chain of clues — name players that fit every link', href: '/games/nfl/chain', accent: 'yellow' },
    { name: 'Ticking Time Bomb', desc: '5 clues, 5 guesses — identify the mystery player before the bomb explodes', href: '/games/nfl/ttb', accent: 'red' },
    { name: 'Fantasy Duel', desc: 'Draw a random team each round and draft your best lineup vs a friend', href: '/games/nfl/fantasy-duel', accent: 'yellow' },
    { name: 'Dungeon Adventure', desc: 'Roguelike trivia — pick a class, collect relics that filter your answers, defeat 6 dungeon floors', href: '/games/nfl/dungeon', accent: 'red' },
    { name: 'Balatro', desc: 'Roguelike card game — draft player-season cards, build combos, beat 8 rounds to win the Super Bowl', href: '/games/nfl/balatro', accent: 'yellow' },
    { name: 'Bullseye', desc: 'Each player names someone who fits 5 prompts, closest total to the target score wins', href: '/games/nfl/bullseye', accent: 'red' },
    { name: 'Selected Quizzes', desc: 'Sporcle-style timed quizzes — type as many answers as you can before the clock runs out', href: '/games/nfl/selected-quizzes', accent: 'yellow' }
  ];

  const nbaGames: GameDef[] = [
    { name: 'Chain Game', desc: 'Build a chain of NBA clues — name players that fit every link', href: '/games/nba/chain', accent: 'yellow' },
    { name: 'Ticking Time Bomb', desc: '5 clues, 5 guesses — identify the mystery NBA player before the bomb explodes', href: '/games/nba/ttb', accent: 'red' },
    { name: 'Fantasy Duel', desc: 'Draw a random NBA team each round and draft your best lineup vs a friend', href: '/games/nba/fantasy-duel', accent: 'yellow' },
    { name: 'Dungeon Adventure', desc: 'Roguelike trivia — pick a class, collect relics that filter your answers, defeat 6 NBA dungeon floors', href: '/games/nba/dungeon', accent: 'red' },
    { name: 'Balatro', desc: 'Draft hands of NBA player-season cards — build combos and beat the shot clock!', href: '/games/nba/balatro', accent: 'yellow' },
    { name: 'Bullseye', desc: 'Each player names someone who fits 5 prompts, closest total to the target score wins', href: '/games/nba/bullseye', accent: 'red' },
    { name: 'Selected Quizzes', desc: 'Sporcle-style timed quizzes — type as many answers as you can before the clock runs out', href: '/games/nba/selected-quizzes', accent: 'yellow' }
  ];

  type MpDef = { name: string; desc: string; links: { label: string; href: string }[] };

  const mpGames: MpDef[] = [
    { name: 'Chain Game Co-op', desc: 'Share one chain, alternate turns, and work together with 3 lives to score as many points as possible.', links: [
      { label: 'NFL Chain Co-op Lobby', href: '/multiplayer/chain_coop' },
      { label: 'NBA Chain Co-op Lobby', href: '/multiplayer/nba_chain_coop' }
    ]},
    { name: 'Chain Game Comp', desc: 'Each player gets their own chain, 2 lives, and the match ends once both players are out twice. Highest score wins.', links: [
      { label: 'NFL Chain Comp Lobby', href: '/multiplayer/chain_comp' },
      { label: 'NBA Chain Comp Lobby', href: '/multiplayer/nba_chain_comp' }
    ]},
    { name: 'Bullseye', desc: 'Choose a sport, make a lobby, and take turns chasing the target score.', links: [
      { label: 'NFL Bullseye Lobby', href: '/multiplayer/nfl_bullseye' },
      { label: 'NBA Bullseye Lobby', href: '/multiplayer/nba_bullseye' }
    ]},
    { name: 'Fantasy Duel', desc: 'Choose a sport, make a lobby, and draft live against the other players in seat order.', links: [
      { label: 'NFL Fantasy Duel Lobby', href: '/multiplayer/starting6' },
      { label: 'NBA Fantasy Duel Lobby', href: '/multiplayer/nba_starting5' }
    ]},
    { name: 'Code Words', desc: '4 players, 2 teams. Each team\'s clue giver hints at HOF players on a 5x5 board for their guesser to find. First team to clear their 7 wins.', links: [
      { label: 'NFL Code Words Lobby', href: '/multiplayer/nfl_codewords' },
      { label: 'NBA Code Words Lobby', href: '/multiplayer/nba_codewords' }
    ]}
  ];
</script>

<section class="home">
  <!-- Tab bar -->
  <div class="tab-bar">
    <button class="tab-btn" class:active={activeTab === 'about'} onclick={() => switchTab('about')}>About</button>
    <button class="tab-btn" class:active={activeTab === 'nfl'} onclick={() => switchTab('nfl')}>NFL Games</button>
    <button class="tab-btn" class:active={activeTab === 'nba'} onclick={() => switchTab('nba')}>NBA Games</button>
    <button class="tab-btn" class:active={activeTab === 'multiplayer'} onclick={() => switchTab('multiplayer')}>Multiplayer</button>
  </div>

  <!-- About -->
  {#if activeTab === 'about'}
    <div class="tab-panel">
      <div class="about-intro">
        <h2>Welcome</h2>
        <p>Hey, my name is Orion, I am a student at Cornell and I make sports trivia games in my free time. I like to store them here so random people can get a chance to play them! I hope to add a wide catalogue of a lot of fun stuff. A big thank you to all my friends at WVBR 93.5 for giving me the motivation to finally commit to storing some of these games. If it wasn't for them theres zero chance I would have had as much fun making these.</p>
      </div>

      <div class="blog-label">General Updates</div>
      <div class="blog-list">
        <div class="blog-post">
          <div class="blog-post-date">Mar 2026</div>
          <div class="blog-post-title">Multiplayer Lobby Update</div>
          <p>The site now has a dedicated Multiplayer tab with room-based lobbies for Bullseye, Fantasy Duel, and Chain Game. You can create a lobby, claim Player 1-4 seats, and start once at least two players are in.</p>
          <p>These online modes are polling-based for now, so they are meant for simple shared sessions and turn-based play rather than ultra-fast real-time action.</p>
        </div>
        <div class="blog-post">
          <div class="blog-post-date">Mar 2026</div>
          <div class="blog-post-title">Chain Multiplayer Added</div>
          <p>Chain Game now has a multiplayer version where everyone gets the same live chain. Correct answers are banned globally for the rest of the game, and turns rotate through the seated players.</p>
          <p>This mode keeps the same core chain logic, but moves state to the server so the whole room stays synced.</p>
        </div>
        <div class="blog-post">
          <div class="blog-post-date">Mar 2026</div>
          <div class="blog-post-title">Turn Lock Fixes</div>
          <p>Online Fantasy Duel and Bullseye now use session-based player identity, which fixes the issue where two browser tabs could look like the same active player.</p>
          <p>Play Again in multiplayer now returns everyone to the same lobby so the host can quickly run another match with the same group.</p>
        </div>
      </div>
    </div>
  {/if}

  <!-- NFL Games -->
  {#if activeTab === 'nfl'}
    <div class="tab-panel">
      <img src="/img/football_logo_nobg.png" alt="NFL" class="tab-banner" />
      <div id="question-list">
        {#each nflGames as game}
          <a href={game.href} class="q-btn">
            <div class="q-btn-accent accent-{game.accent}"></div>
            <div class="q-card-body">
              <strong>{game.name}</strong>
              <small>{game.desc}</small>
            </div>
          </a>
        {/each}
      </div>
    </div>
  {/if}

  <!-- NBA Games -->
  {#if activeTab === 'nba'}
    <div class="tab-panel">
      <img src="/img/basketball_logo_nobg.png" alt="NBA" class="tab-banner" />
      <div id="question-list">
        {#each nbaGames as game}
          <a href={game.href} class="q-btn">
            <div class="q-btn-accent accent-{game.accent}"></div>
            <div class="q-card-body">
              <strong>{game.name}</strong>
              <small>{game.desc}</small>
            </div>
          </a>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Multiplayer -->
  {#if activeTab === 'multiplayer'}
    <div class="tab-panel">
      <div class="about-intro">
        <h2>Online Multiplayer</h2>
        <p>Create a lobby, claim Player 1-4 seats, and start with any 2-4 players. Online play supports Chain Game, Bullseye, Fantasy Duel, and Code Words.</p>
      </div>
      <div class="mp-grid">
        {#each mpGames as mp}
          <div class="mp-card">
            <h3>{mp.name}</h3>
            <p>{mp.desc}</p>
            <div class="mp-actions">
              {#each mp.links as link}
                <a class="mp-link" href={link.href}>{link.label}</a>
              {/each}
            </div>
          </div>
        {/each}
        <div class="mp-card mp-join-card">
          <h3>Join Lobby</h3>
          <p>Already have a room code? Enter it here and jump straight into the lobby.</p>
          <div class="mp-join-row">
            <input
              class="mp-join-input"
              type="text"
              maxlength={6}
              placeholder="ABC123"
              bind:value={joinCode}
              onkeydown={(e) => { if (e.key === 'Enter') joinLobby(); }}
            />
            <button class="mp-join-btn" type="button" onclick={joinLobby}>Join</button>
          </div>
          {#if joinError}
            <div class="mp-join-error">{joinError}</div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</section>

<style>
  .home { min-width: 0; }

  .tab-bar {
    display: flex;
    padding: 16px 24px 0;
    gap: 0;
  }
  .tab-btn {
    flex: 1;
    padding: 11px 16px;
    background: var(--surface);
    border: 3px solid var(--border);
    color: var(--text-muted);
    font-size: 0.82rem;
    font-weight: 800;
    cursor: pointer;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-family: 'Barlow Condensed', sans-serif;
    box-shadow: 3px 3px 0 var(--border);
    transition: background 0.12s, color 0.12s;
    margin-right: -3px;
    position: relative;
    z-index: 0;
  }
  .tab-btn:last-child { margin-right: 0; }
  .tab-btn:hover { background: var(--surface-2); color: var(--text); }
  .tab-btn.active { background: var(--yellow); color: var(--text-dark); z-index: 1; }

  .tab-panel { padding: 20px 24px 40px; }

  .tab-banner {
    width: 100%;
    height: 160px;
    object-fit: cover;
    object-position: center;
    display: block;
    margin-bottom: 16px;
    border: 3px solid var(--border);
    box-shadow: 4px 4px 0 var(--border);
  }

  /* About */
  .about-intro {
    background: var(--surface);
    border: 3px solid var(--border);
    border-left: 6px solid var(--yellow);
    box-shadow: 4px 4px 0 var(--border);
    padding: 20px 22px;
    margin-bottom: 20px;
  }
  .about-intro h2 {
    font-family: 'Bebas Neue', sans-serif;
    color: var(--yellow);
    font-size: 1.6rem;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin: 0 0 10px;
  }
  .about-intro p {
    color: var(--text-dim);
    font-size: 0.95rem;
    line-height: 1.55;
    margin: 0;
  }

  .blog-label {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 4px;
    color: var(--text-muted);
    font-weight: 800;
    margin-bottom: 12px;
  }
  .blog-list { display: flex; flex-direction: column; gap: 8px; }
  .blog-post {
    background: var(--surface);
    border: 3px solid var(--border);
    border-left: 6px solid var(--red);
    box-shadow: 4px 4px 0 var(--border);
    padding: 16px 18px;
  }
  .blog-post-date {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-muted);
    font-weight: 800;
    margin-bottom: 8px;
  }
  .blog-post-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.05rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text);
    margin-bottom: 6px;
  }
  .blog-post p {
    color: var(--text-dim);
    font-size: 0.9rem;
    line-height: 1.5;
    margin: 0;
  }
  .blog-post p + p { margin-top: 8px; }

  /* Game list uses global .q-btn styling — first card gets a top border too */
  :global(#question-list .q-btn:first-child) { border-top: 3px solid var(--border); }

  /* Multiplayer */
  .mp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
  }
  .mp-card {
    background: var(--surface);
    border: 3px solid var(--border);
    box-shadow: 4px 4px 0 var(--border);
    padding: 20px;
  }
  .mp-card h3 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.55rem;
    letter-spacing: 3px;
    color: var(--yellow);
    margin: 0 0 8px;
  }
  .mp-card p {
    color: var(--text-dim);
    font-size: 0.95rem;
    line-height: 1.45;
    margin: 0 0 14px;
  }
  .mp-actions { display: flex; flex-direction: column; gap: 10px; }
  .mp-link {
    display: block;
    text-decoration: none;
    background: var(--surface-2);
    border: 2px solid var(--border-dim);
    color: var(--text);
    padding: 12px 14px;
    font-size: 0.9rem;
    font-weight: 800;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }
  .mp-link:hover { background: rgba(245,199,0,0.1); border-color: var(--yellow); }

  .mp-join-card { grid-column: span 2; }
  .mp-join-card h3 { color: var(--text); }
  .mp-join-row { display: flex; gap: 8px; }
  .mp-join-input {
    flex: 1;
    min-width: 0;
    background: var(--surface-2);
    border: 2px solid var(--border-dim);
    color: var(--text);
    padding: 12px;
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    font-size: 1rem;
    text-transform: uppercase;
  }
  .mp-join-btn {
    border: 2px solid var(--border);
    background: var(--yellow);
    color: var(--text-dark);
    padding: 0 16px;
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    font-size: 1rem;
    cursor: pointer;
  }
  .mp-join-error { color: var(--red-bright); font-size: 0.92rem; margin-top: 10px; }

  @media (max-width: 600px) {
    .tab-btn { font-size: 0.74rem; letter-spacing: 1px; padding: 10px; }
    .tab-panel { padding: 16px 0 32px; }
    .mp-join-card { grid-column: span 1; }
  }
</style>
