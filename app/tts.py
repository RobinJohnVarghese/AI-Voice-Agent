"""Narrator: Piper neural TTS with espeak-ng fallback, punctuation-aware pauses."""
import io
import subprocess
from collections import OrderedDict

import numpy as np
import soundfile as sf
from piper import PiperVoice, SynthesisConfig

from . import config, lang, prosody

SR = 22050


def _resample(x: np.ndarray, src: int, dst: int = SR) -> np.ndarray:
    if src == dst or len(x) == 0:
        return x
    n = int(len(x) * dst / src)
    return np.interp(np.linspace(0, len(x), n, endpoint=False), np.arange(len(x)), x).astype(np.float32)


class TTS:
    def __init__(self):
        self.voices: OrderedDict[str, PiperVoice] = OrderedDict()
        self.available = {p.name.split("_")[0]: p for p in sorted(config.PIPER_DIR.glob("*.onnx"))}

    def _voice(self, code: str) -> PiperVoice | None:
        if code not in self.available:
            return None
        if code not in self.voices:
            self.voices[code] = PiperVoice.load(self.available[code])
            while len(self.voices) > config.MAX_LOADED_VOICES:  # keep RAM bounded
                self.voices.popitem(last=False)
        self.voices.move_to_end(code)
        return self.voices[code]

    def _piper(self, voice: PiperVoice, text: str, slow: bool) -> np.ndarray:
        cfg = SynthesisConfig(length_scale=1.35 if slow else 1.0)
        chunks = [_resample(c.audio_float_array, c.sample_rate) for c in voice.synthesize(text, cfg)]
        return np.concatenate(chunks) if chunks else np.zeros(0, np.float32)

    def _espeak(self, code: str, text: str, slow: bool) -> np.ndarray:
        wav = subprocess.run(["espeak-ng", "-v", lang.espeak_voice(code), "-s", "120" if slow else "160",
                              "--stdout", text], capture_output=True, check=True).stdout
        data, sr = sf.read(io.BytesIO(wav), dtype="float32")
        return _resample(data, sr)

    def synthesize(self, text: str, code: str, slow: bool = False) -> bytes:
        voice = self._voice(code)
        out = []
        for seg in prosody.segment(text):
            audio = self._piper(voice, seg.text, slow) if voice else self._espeak(code, seg.text, slow)
            out += [audio, np.zeros(int(SR * seg.pause * (1.3 if slow else 1.0)), np.float32)]
        audio = np.concatenate(out) if out else np.zeros(SR // 2, np.float32)
        buf = io.BytesIO()
        sf.write(buf, audio, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue()
