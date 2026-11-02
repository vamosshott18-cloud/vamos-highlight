'use strict';
/* Render satu momen di HP: kanvas (video + bumper Enerjik + watermark + fade) direkam real-time dengan MediaRecorder.
   Urutan sama dengan versi Mac: 0,3 dtk frame pertama ditahan (tertutup bumper), bumper 1,5 dtk,
   watermark muncul di 1,65 dtk, suara clip masuk pelan setelah 0,3 dtk, fade-out 0,3 dtk di akhir. */

const BUMP = { cover: 0.3, dur: 1.5, fps: 30, frames: 45 };
const _bumpCache = {};

function pilihFormatRekam() {
  const opsi = ['video/mp4;codecs="avc1.640028,mp4a.40.2"', 'video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4',
                'video/webm;codecs=vp9,opus', 'video/webm'];
  return opsi.find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
}

async function muatBumper(label, orient, actx) {
  const key = `${label}_${orient}`;
  if (_bumpCache[key]) return _bumpCache[key];
  const frames = await Promise.all(Array.from({ length: BUMP.frames }, (_, i) => new Promise((ok, no) => {
    const im = new Image(); im.decoding = 'async';
    im.onload = () => ok(im); im.onerror = () => no(new Error('bumper ' + key));
    im.src = `aset/${key}/${String(i + 1).padStart(2, '0')}.webp`;
  })));
  for (const im of frames) { try { await im.decode(); } catch (e) { /* sudah dimuat */ } }
  const sfx = await actx.decodeAudioData(await (await fetch(`aset/sfx_${key}.m4a`)).arrayBuffer());
  const bug = await new Promise((ok, no) => { const im = new Image(); im.onload = () => ok(im); im.onerror = no; im.src = `aset/bug_${orient}.png`; });
  return (_bumpCache[key] = { frames, sfx, bug });
}

/** Gambar video ke kanvas: potong kalau orientasinya sama, kalau beda isi latar dengan versi buram. */
function gambarVideo(ctx, v, W, H, blurCv) {
  const sw = v.videoWidth, sh = v.videoHeight;
  if (!sw || !sh) return;
  if ((sh >= sw) === (H >= W)) {
    const s = Math.max(W / sw, H / sh), dw = sw * s, dh = sh * s;
    ctx.drawImage(v, (W - dw) / 2, (H - dh) / 2, dw, dh);
    return;
  }
  const bctx = blurCv.getContext('2d');
  const bs = Math.max(blurCv.width / sw, blurCv.height / sh);
  bctx.drawImage(v, (blurCv.width - sw * bs) / 2, (blurCv.height - sh * bs) / 2, sw * bs, sh * bs);
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(blurCv, 0, 0, W, H);
  ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.fillRect(0, 0, W, H);
  const s = Math.min(W / sw, H / sh), dw = sw * s, dh = sh * s;
  ctx.drawImage(v, (W - dw) / 2, (H - dh) / 2, dw, dh);
}

/**
 * @returns {Promise<{blob: Blob, ext: string}>}
 * opts: {file, url, momen:{start,end,label}, orient:'P'|'L', actx: AudioContext, kanvas: HTMLCanvasElement (pratinjau), onProg}
 */
async function renderMomen(opts) {
  const { url, momen, orient, actx, onProg } = opts;
  const W = orient === 'P' ? 1080 : 1920, H = orient === 'P' ? 1920 : 1080;
  const mime = pilihFormatRekam();
  if (!mime) throw new Error('Browser ini belum bisa merekam video. Pakai Safari (iPhone/iPad) atau Chrome terbaru.');
  const bump = await muatBumper(momen.label, orient, actx);

  const cv = opts.kanvas; cv.width = W; cv.height = H;
  const ctx = cv.getContext('2d');
  const blurCv = document.createElement('canvas'); blurCv.width = Math.round(W / 24); blurCv.height = Math.round(H / 24);

  const v = videoEl(url, false);
  await once(v, 'loadedmetadata');
  await seekTo(v, momen.start);
  const dur = Math.max(1, momen.end - momen.start), total = BUMP.cover + dur;

  // suara: clip (masuk pelan) + sfx bumper → kompresor ringan → fade-out → rekaman
  const dest = actx.createMediaStreamDestination();
  const master = actx.createGain(); master.connect(dest);
  const comp = actx.createDynamicsCompressor();
  comp.threshold.value = -20; comp.knee.value = 10; comp.ratio.value = 4; comp.attack.value = 0.005; comp.release.value = 0.25;
  const makeup = actx.createGain(); makeup.gain.value = 1.6;
  comp.connect(makeup); makeup.connect(master);
  const gClip = actx.createGain(); gClip.gain.value = 0; gClip.connect(comp);
  const src = actx.createMediaElementSource(v); src.connect(gClip);
  const sfx = actx.createBufferSource(); sfx.buffer = bump.sfx; sfx.connect(master);

  const stream = new MediaStream([...cv.captureStream(30).getVideoTracks(), ...dest.stream.getAudioTracks()]);
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: orient === 'P' ? 9e6 : 10e6, audioBitsPerSecond: 192000 });
  const chunks = [];
  rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
  const selesai = new Promise(ok => { rec.onstop = ok; });

  if (actx.state !== 'running') await actx.resume();
  const t0 = actx.currentTime + 0.05;
  gClip.gain.setValueAtTime(0, t0 + BUMP.cover);
  gClip.gain.linearRampToValueAtTime(1, t0 + BUMP.cover + 0.25);
  master.gain.setValueAtTime(1, t0 + total - 0.3);
  master.gain.linearRampToValueAtTime(0, t0 + total);
  sfx.start(t0);

  let main = false;
  const gambar = () => {
    const t = actx.currentTime - t0;
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    gambarVideo(ctx, v, W, H, blurCv);
    const bugA = Math.min(1, Math.max(0, (t - (BUMP.dur + 0.15)) / 0.35));
    if (bugA > 0) { ctx.globalAlpha = bugA; ctx.drawImage(bump.bug, 0, 0, W, H); ctx.globalAlpha = 1; }
    const fi = Math.floor(Math.max(0, t) * BUMP.fps);
    if (fi < BUMP.frames) ctx.drawImage(bump.frames[fi], 0, 0, W, H);
    const fade = (t - (total - 0.3)) / 0.3;
    if (fade > 0) { ctx.fillStyle = `rgba(0,0,0,${Math.min(1, fade)})`; ctx.fillRect(0, 0, W, H); }
    return t;
  };

  gambar();
  rec.start(1000);
  await new Promise((ok, no) => {
    const tick = () => {
      const t = gambar();
      if (!main && t >= BUMP.cover) { main = true; v.play().catch(no); }
      if (onProg) onProg(Math.min(1, t / total));
      if (t >= total) { ok(); return; }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  v.pause();
  rec.stop();
  await selesai;
  try { src.disconnect(); master.disconnect(); } catch (e) { /* sudah lepas */ }
  stream.getTracks().forEach(t => t.stop());
  v.removeAttribute('src'); v.load();
  return { blob: new Blob(chunks, { type: mime.split(';')[0] }), ext: mime.startsWith('video/mp4') ? 'mp4' : 'webm' };
}
