/* ── SFX: Web Audio API sound manager ─────────────────────────────
   Usage: SFX.play('correct')  |  SFX.toggleMute()
   Sounds are synthesized — no audio files required.
   ──────────────────────────────────────────────────────────────── */
window.SFX = (function () {
  var ctx = null;
  var muted = localStorage.getItem('sfx_muted') === '1';

  function getCtx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  var SOUNDS = {
    correct:     { freq: 523,  freq2: 784,  wave: 'sine',     dur: 0.25, vol: 0.18 },
    wrong:       { freq: 220,  freq2: 140,  wave: 'square',   dur: 0.28, vol: 0.14 },
    click:       { freq: 440,               wave: 'sine',     dur: 0.07, vol: 0.09 },
    card_play:   { freq: 330,  freq2: 500,  wave: 'triangle', dur: 0.14, vol: 0.14 },
    card_sel:    { freq: 520,               wave: 'sine',     dur: 0.05, vol: 0.07 },
    discard:     { freq: 280,  freq2: 170,  wave: 'square',   dur: 0.11, vol: 0.09 },
    score_tick:  { freq: 680,               wave: 'sine',     dur: 0.04, vol: 0.06 },
    win:         { freq: 523,  freq2: 1046, wave: 'sine',     dur: 0.55, vol: 0.22 },
    lose:        { freq: 200,  freq2: 90,   wave: 'sawtooth', dur: 0.5,  vol: 0.18 },
    buy:         { freq: 600,  freq2: 820,  wave: 'sine',     dur: 0.18, vol: 0.14 },
    reward:      { freq: 740,  freq2: 988,  wave: 'sine',     dur: 0.32, vol: 0.18 },
    explosion:   { freq: 120,  freq2: 40,   wave: 'sawtooth', dur: 0.75, vol: 0.28 },
    defuse:      { freq: 880,  freq2: 1175, wave: 'sine',     dur: 0.45, vol: 0.22 },
    hint:        { freq: 360,  freq2: 430,  wave: 'sine',     dur: 0.14, vol: 0.09 },
    dungeon_hit: { freq: 320,  freq2: 240,  wave: 'square',   dur: 0.18, vol: 0.16 },
    dungeon_dmg: { freq: 180,  freq2: 120,  wave: 'sawtooth', dur: 0.22, vol: 0.18 },
    level_up:    { freq: 523,  freq2: 1046, wave: 'sine',     dur: 0.65, vol: 0.22 },
    draft_pick:  { freq: 440,  freq2: 660,  wave: 'sine',     dur: 0.18, vol: 0.14 },
    confetti:    { freq: 880,  freq2: 1760, wave: 'sine',     dur: 0.75, vol: 0.18 },
  };

  function _doPlay(c, cfg) {
    try {
      var osc = c.createOscillator();
      var gain = c.createGain();
      osc.connect(gain);
      gain.connect(c.destination);
      osc.type = cfg.wave || 'sine';
      osc.frequency.setValueAtTime(cfg.freq, c.currentTime);
      if (cfg.freq2) osc.frequency.linearRampToValueAtTime(cfg.freq2, c.currentTime + cfg.dur);
      gain.gain.setValueAtTime(cfg.vol || 0.12, c.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + cfg.dur);
      osc.start(c.currentTime);
      osc.stop(c.currentTime + cfg.dur);
    } catch (e) { /* ignore */ }
  }

  function play(type) {
    if (muted) return;
    var cfg = SOUNDS[type];
    if (!cfg) return;
    try {
      var c = getCtx();
      if (c.state === 'suspended') {
        c.resume().then(function () { _doPlay(c, cfg); });
      } else {
        _doPlay(c, cfg);
      }
    } catch (e) { /* ignore audio errors */ }
  }

  function toggleMute() {
    muted = !muted;
    localStorage.setItem('sfx_muted', muted ? '1' : '0');
    document.querySelectorAll('.sfx-mute-btn').forEach(function (btn) {
      btn.textContent = muted ? '\uD83D\uDD07' : '\uD83D\uDD0A';
      btn.title = muted ? 'Unmute sounds' : 'Mute sounds';
    });
  }

  function isMuted() { return muted; }

  // Set initial button state once DOM is ready
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.sfx-mute-btn').forEach(function (btn) {
      btn.textContent = muted ? '\uD83D\uDD07' : '\uD83D\uDD0A';
      btn.title = muted ? 'Unmute sounds' : 'Mute sounds';
    });
  });

  return { play: play, toggleMute: toggleMute, isMuted: isMuted };
})();
