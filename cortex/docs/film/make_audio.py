"""Voice-over (Kokoro-82M, Apache-2.0, runs on CPU) + a synthesised ambient score for the X-Ray film.

Usage: python docs/film/make_audio.py [--voice af_heart] [--out docs/film/xray-audio.wav]
Needs: pip install kokoro soundfile numpy. Each line is placed at its scene time and sped up (max 1.2x) if it would overrun.
Then mux: ffmpeg -i app/static/xray-film.mp4 -i docs/film/xray-audio.wav -c:v copy -c:a aac -b:a 192k -shortest out.mp4
"""
import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

SR, DUR = 24000, 94.0
# (start seconds, must end by, line) — aligned with the scene timings in xray-film.html
LINES = [
    (0.9, 6.6, "This is Cortex X-Ray: a look inside a GraphRAG system built on FalkorDB."),
    (8.0, 20.4, "Six layers. A browser app, free hosting on Hugging Face, FastAPI guardrails, and LangChain for the AI. At the core, one engine: FalkorDB."),
    (21.8, 32.6, "Seventy-three bank documents are split into chunks, embedded locally, and mapped into entities and relationships. Text, vectors and links, in one engine."),
    (33.8, 46.4, "Inside FalkorDB, every relationship type is a sparse matrix. Following a link becomes matrix multiplication. That's why multi-hop questions answer in milliseconds."),
    (47.9, 50.0, "A question arrives."),
    (50.1, 52.6, "Restricted documents are sealed off."),
    (52.7, 55.4, "Vector search finds the closest text."),
    (55.5, 57.8, "Their entities become seeds."),
    (57.9, 61.4, "The graph expands two hops, to the findings."),
    (61.5, 65.8, "Only connected facts reach the model, with sources and cost."),
    (67.0, 77.6, "The same engine goes beyond RAG. Across more than a million records, it finds all sixty fraud rings, in under two seconds."),
    (78.8, 87.6, "Measured on thirty-four questions: ninety-seven percent recall, versus seventy for vector RAG, at the same cost per correct answer."),
    (88.8, 93.6, "Cortex. Why FalkorDB, for AI engagements, and more."),
]


def voice_track(voice):
    from kokoro import KPipeline
    tts = KPipeline(lang_code="a")
    out = np.zeros(int(DUR * SR), np.float32)
    active = np.zeros_like(out)
    for start, end, text in LINES:
        speed = 1.0
        while True:
            a = np.concatenate([r.audio.numpy() for r in tts(text, voice=voice, speed=speed)])
            if len(a) / SR <= end - start or speed >= 1.2:
                break
            speed = round(speed + 0.05, 2)
        i = int(start * SR); a = a[: len(out) - i]
        out[i:i + len(a)] += a; active[i:i + len(a)] = 1
        print(f"{start:5.1f}s  {len(a) / SR:4.1f}s of {end - start:4.1f}s  x{speed}  {text[:60]}")
    return out, active


def lowpass(x, cutoff):
    f = np.fft.rfft(x); fr = np.fft.rfftfreq(len(x), 1 / SR)
    f *= 1 / (1 + (fr / cutoff) ** 4)
    return np.fft.irfft(f, len(x))


def reverb(x, secs=3.5, mix=.35):
    n = int(secs * SR); rng = np.random.default_rng(7)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n)); ir /= np.abs(ir).sum() / 8
    m = len(x) + n; y = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)]
    return (1 - mix) * x + mix * y


def score():
    t = np.arange(int(DUR * SR)) / SR
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    chords = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]  # Am F C G
    bar = 6.0; pad = np.zeros_like(t)
    for k in range(int(DUR / bar) + 1):
        ch, s = chords[k % 4], k * bar
        seg = (t >= s - 1) & (t < s + bar + 1.5); tt = t[seg] - s
        env = np.clip((tt + 1) / 2.5, 0, 1) * np.clip((bar + 1.5 - tt) / 2.5, 0, 1)
        for m in ch:
            for det in (-.1, .1):
                ph = 2 * np.pi * hz(m) * (1 + det / 100) * t[seg]
                pad[seg] += env * (np.sin(ph) + .3 * np.sin(2 * ph) + .12 * np.sin(3 * ph)) / 8
        seg2 = (t >= s) & (t < s + bar); tb = t[seg2] - s
        pad[seg2] += .35 * np.sin(2 * np.pi * hz(ch[0] - 24) * t[seg2]) * np.clip(tb / .5, 0, 1) * np.exp(-tb * .25)
    arp = np.zeros_like(t); step = .375
    for k in range(int(DUR / step)):
        s = k * step; ch = chords[int(s / bar) % 4]; m = ch[k % 4] + 12
        seg = (t >= s) & (t < s + 1.2); tt = t[seg] - s
        arp[seg] += np.sin(2 * np.pi * hz(m) * t[seg]) * np.exp(-tt * 5) * .12
    lift = np.clip((t - 7) / 3, 0, 1) * np.clip((93 - t) / 4, 0, 1)                     # arp enters with the stack scene
    swell = 1 + .35 * np.exp(-((t - 72) / 4) ** 2) + .35 * np.exp(-((t - 83) / 4) ** 2)  # fraud + results
    mix = lowpass(pad, 1400) + lowpass(arp, 3500) * lift
    mix = reverb(mix) * swell
    mix *= np.clip(t / 2, 0, 1) * np.clip((DUR - t) / 2.5, 0, 1)
    return mix / np.abs(mix).max() * .5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--out", default=str(Path(__file__).parent / "xray-audio.wav"))
    a = ap.parse_args()
    vo, active = voice_track(a.voice)
    duck = np.convolve(active, np.ones(int(.4 * SR)) / int(.4 * SR), "same")     # smooth side-chain
    music = score() * (1 - .6 * np.clip(duck, 0, 1))
    vo = vo / (np.abs(vo).max() + 1e-9) * .9
    out = np.clip(vo + music * .55, -1, 1)
    sf.write(a.out, np.stack([out, out], 1), SR)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
