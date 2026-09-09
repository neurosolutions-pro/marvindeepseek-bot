"""Voice message transcription (OGG/WAV via pydub + speech_recognition)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

log = logging.getLogger("marvindeepseek.audio")


def transcribe_voice(file_path: str, language: str = "ru-RU") -> str:
    """
    Convert voice file to WAV if needed and recognize speech.

    Uses Google Web Speech API through SpeechRecognition (free, rate-limited).
    """
    try:
        import speech_recognition as sr
        from pydub import AudioSegment
    except ImportError as exc:
        raise RuntimeError(
            "Для голосовых сообщений нужны пакеты speech_recognition и pydub"
        ) from exc

    src = Path(file_path)
    recognizer = sr.Recognizer()

    with tempfile.TemporaryDirectory(prefix="voice_") as tmp:
        wav_path = Path(tmp) / "audio.wav"
        try:
            audio = AudioSegment.from_file(src)
            audio.export(wav_path, format="wav")
        except Exception as exc:
            log.exception("audio convert failed")
            raise RuntimeError(f"Не удалось конвертировать аудио: {exc}") from exc

        with sr.AudioFile(str(wav_path)) as source:
            audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data, language=language)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            raise RuntimeError(f"Сервис распознавания речи недоступен: {exc}") from exc
    return (text or "").strip()
