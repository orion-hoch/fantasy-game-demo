/* ── SFX: Web Audio API sound manager ─────────────────────────────
   Usage: SFX.play('correct')  |  SFX.toggleMute()
   Sounds are synthesized — no audio files required.
   ──────────────────────────────────────────────────────────────── */
window.SFX = (function () {
  var ctx = null;
  var muted = localStorage.getItem('sfx_muted') === '1';
  var _tickInterval = null;

  var ICON_ON  = '/static/img/sound-on.svg';
  var ICON_OFF = '/static/img/sound-off.svg';

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
    bomb_tick:   { freq: 900,  freq2: 600,  wave: 'square',   dur: 0.05, vol: 0.10 },
    // noise-based sounds (handled by _doPlayNoise)
    card_sel:    { noise: true, bandpass: 2800, bandQ: 1.8, dur: 0.07, vol: 0.22 },
    rustle:      { noise: true, bandpass: 700,  bandQ: 1.2, dur: 0.14, vol: 0.16 },
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

  function _doPlayNoise(c, cfg) {
    try {
      var sampleRate = c.sampleRate;
      var frameCount = Math.ceil(sampleRate * cfg.dur);
      var buf = c.createBuffer(1, frameCount, sampleRate);
      var data = buf.getChannelData(0);
      for (var i = 0; i < frameCount; i++) {
        data[i] = Math.random() * 2 - 1;
      }
      var src = c.createBufferSource();
      src.buffer = buf;

      var filter = c.createBiquadFilter();
      filter.type = 'bandpass';
      filter.frequency.value = cfg.bandpass || 2000;
      filter.Q.value = cfg.bandQ || 1.5;

      var gain = c.createGain();
      gain.gain.setValueAtTime(cfg.vol || 0.15, c.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + cfg.dur);

      src.connect(filter);
      filter.connect(gain);
      gain.connect(c.destination);
      src.start(c.currentTime);
      src.stop(c.currentTime + cfg.dur);
    } catch (e) { /* ignore */ }
  }

  function _dispatch(c, cfg) {
    if (cfg.noise) {
      _doPlayNoise(c, cfg);
    } else {
      _doPlay(c, cfg);
    }
  }

  function play(type) {
    if (muted) return;
    var cfg = SOUNDS[type];
    if (!cfg) return;
    try {
      var c = getCtx();
      if (c.state === 'suspended') {
        c.resume().then(function () { _dispatch(c, cfg); });
      } else {
        _dispatch(c, cfg);
      }
    } catch (e) { /* ignore audio errors */ }
  }

  function startTicking(intervalMs) {
    stopTicking();
    if (muted) return;
    _tickInterval = setInterval(function () { play('bomb_tick'); }, intervalMs || 1000);
  }

  function stopTicking() {
    if (_tickInterval !== null) {
      clearInterval(_tickInterval);
      _tickInterval = null;
    }
  }

  function _updateButtons() {
    document.querySelectorAll('.sfx-mute-btn').forEach(function (btn) {
      var img = btn.querySelector('img');
      if (img) {
        img.src = muted ? ICON_OFF : ICON_ON;
        img.alt = muted ? 'Unmute' : 'Mute';
      }
      btn.title = muted ? 'Unmute sounds' : 'Mute sounds';
      if (muted) {
        btn.classList.add('muted');
      } else {
        btn.classList.remove('muted');
      }
    });
  }

  function toggleMute() {
    muted = !muted;
    localStorage.setItem('sfx_muted', muted ? '1' : '0');
    if (muted) stopTicking();
    _updateButtons();
  }

  function isMuted() { return muted; }

  // Set initial button state once DOM is ready
  document.addEventListener('DOMContentLoaded', function () {
    _updateButtons();
  });

  return { play: play, toggleMute: toggleMute, isMuted: isMuted, startTicking: startTicking, stopTicking: stopTicking };
})();
