/* SFX: Web Audio API sound manager (ported from Flask audio.js)
   Usage: SFX.play('correct')  |  SFX.toggleMute()
   Sounds are synthesized — no audio files required. */

type SoundConfig = {
  freq: number;
  freq2?: number;
  wave: OscillatorType;
  dur: number;
  vol: number;
};

type NoiseConfig = {
  lowpass?: number;
  highpass?: number;
  dur: number;
  vol: number;
};

const SOUNDS: Record<string, SoundConfig> = {
  correct:     { freq: 523,  freq2: 784,  wave: 'sine',     dur: 0.25, vol: 0.18 },
  wrong:       { freq: 220,  freq2: 140,  wave: 'square',   dur: 0.28, vol: 0.14 },
  click:       { freq: 440,               wave: 'sine',     dur: 0.07, vol: 0.09 },
  card_play:   { freq: 330,  freq2: 500,  wave: 'triangle', dur: 0.14, vol: 0.14 },
  discard:     { freq: 280,  freq2: 170,  wave: 'square',   dur: 0.11, vol: 0.09 },
  score_tick:  { freq: 680,               wave: 'sine',     dur: 0.04, vol: 0.06 },
  lose:        { freq: 200,  freq2: 90,   wave: 'sawtooth', dur: 0.5,  vol: 0.18 },
  buy:         { freq: 600,  freq2: 820,  wave: 'sine',     dur: 0.18, vol: 0.14 },
  reward:      { freq: 740,  freq2: 988,  wave: 'sine',     dur: 0.32, vol: 0.18 },
  level_up:    { freq: 523,  freq2: 1046, wave: 'sine',     dur: 0.65, vol: 0.22 },
  confetti:    { freq: 880,  freq2: 1760, wave: 'sine',     dur: 0.75, vol: 0.18 },
};

const NOISE_SOUNDS: Record<string, NoiseConfig> = {
  card_sel: { highpass: 400, dur: 0.09, vol: 0.07 },
  rustle:   { lowpass: 1800, dur: 0.18, vol: 0.35 },
};

let ctx: AudioContext | null = null;
let muted = false;

function getCtx(): AudioContext {
  if (!ctx) ctx = new AudioContext();
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

function doPlay(c: AudioContext, cfg: SoundConfig) {
  try {
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.connect(gain);
    gain.connect(c.destination);
    osc.type = cfg.wave;
    osc.frequency.setValueAtTime(cfg.freq, c.currentTime);
    if (cfg.freq2) osc.frequency.linearRampToValueAtTime(cfg.freq2, c.currentTime + cfg.dur);
    gain.gain.setValueAtTime(cfg.vol, c.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + cfg.dur);
    osc.start(c.currentTime);
    osc.stop(c.currentTime + cfg.dur);
  } catch { /* ignore */ }
}

function doPlayNoise(c: AudioContext, cfg: NoiseConfig) {
  try {
    const sampleRate = c.sampleRate;
    const frameCount = Math.ceil(sampleRate * cfg.dur);
    const buf = c.createBuffer(1, frameCount, sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < frameCount; i++) data[i] = Math.random() * 2 - 1;
    const src = c.createBufferSource();
    src.buffer = buf;
    const filter = c.createBiquadFilter();
    if (cfg.highpass !== undefined) {
      filter.type = 'highpass';
      filter.frequency.value = cfg.highpass;
    } else {
      filter.type = 'lowpass';
      filter.frequency.value = cfg.lowpass || 1500;
    }
    filter.Q.value = 0.5;
    const gain = c.createGain();
    gain.gain.setValueAtTime(cfg.vol, c.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + cfg.dur);
    src.connect(filter);
    filter.connect(gain);
    gain.connect(c.destination);
    src.start(c.currentTime);
    src.stop(c.currentTime + cfg.dur);
  } catch { /* ignore */ }
}

function playFanfare(c: AudioContext) {
  try {
    const t = c.currentTime;
    const notes = [262, 330, 392, 523, 659];
    const delays = [0, 0.12, 0.24, 0.36, 0.42];
    const durs = [0.22, 0.22, 0.22, 0.45, 0.55];
    const vols = [0.18, 0.18, 0.18, 0.22, 0.26];
    notes.forEach((freq, i) => {
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.connect(gain);
      gain.connect(c.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, t + delays[i]);
      gain.gain.setValueAtTime(0.001, t + delays[i]);
      gain.gain.linearRampToValueAtTime(vols[i], t + delays[i] + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, t + delays[i] + durs[i]);
      osc.start(t + delays[i]);
      osc.stop(t + delays[i] + durs[i] + 0.05);
    });
  } catch { /* ignore */ }
}

if (typeof localStorage !== 'undefined') {
  muted = localStorage.getItem('sfx_muted') === '1';
}

export const SFX = {
  play(type: string) {
    if (muted) return;
    if (type === 'win') {
      try {
        const c = getCtx();
        if (c.state === 'suspended') c.resume().then(() => playFanfare(c));
        else playFanfare(c);
      } catch { /* ignore */ }
      return;
    }
    const noiseCfg = NOISE_SOUNDS[type];
    if (noiseCfg) {
      try {
        const c = getCtx();
        if (c.state === 'suspended') c.resume().then(() => doPlayNoise(c, noiseCfg));
        else doPlayNoise(c, noiseCfg);
      } catch { /* ignore */ }
      return;
    }
    const cfg = SOUNDS[type];
    if (!cfg) return;
    try {
      const c = getCtx();
      if (c.state === 'suspended') c.resume().then(() => doPlay(c, cfg));
      else doPlay(c, cfg);
    } catch { /* ignore */ }
  },

  toggleMute() {
    muted = !muted;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('sfx_muted', muted ? '1' : '0');
    }
  },

  isMuted() {
    return muted;
  },
};
