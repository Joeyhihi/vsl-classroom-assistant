// Push-to-talk audio → the WAV the backend accepts: 16 kHz, mono, 16-bit PCM, ≤ 30 s.

export const STT_SAMPLE_RATE = 16_000;
export const MAX_RECORDING_S = 30;

export function concatChunks(chunks: readonly Float32Array[]): Float32Array {
  const out = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

/** Linear-interpolation resampling (speech only needs < 8 kHz of bandwidth). */
export function resampleLinear(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate || input.length === 0) return input;
  const length = Math.max(1, Math.round((input.length * toRate) / fromRate));
  const out = new Float32Array(length);
  const step = fromRate / toRate;
  for (let i = 0; i < length; i++) {
    const pos = i * step;
    const j = Math.floor(pos);
    const a = input[Math.min(j, input.length - 1)] ?? 0;
    const b = input[Math.min(j + 1, input.length - 1)] ?? 0;
    out[i] = a + (b - a) * (pos - j);
  }
  return out;
}

export function encodeWav(samples: Float32Array, sampleRate: number = STT_SAMPLE_RATE): ArrayBuffer {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const text = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i] ?? 0));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

/** Captured chunks at the device rate → a WAV blob for /stt/transcriptions. */
export function toUploadWav(chunks: readonly Float32Array[], deviceRate: number): Blob {
  const audio = resampleLinear(concatChunks(chunks), deviceRate, STT_SAMPLE_RATE);
  const capped = audio.subarray(0, MAX_RECORDING_S * STT_SAMPLE_RATE);
  return new Blob([encodeWav(capped)], { type: "audio/wav" });
}
