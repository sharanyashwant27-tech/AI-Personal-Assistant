"""User input layer — captures speech from microphone and converts to text."""

import speech_recognition as sr


class VoiceInputError(Exception):
    """Raised when voice capture or transcription fails."""


class VoiceInput:
    """Listens via microphone and returns transcribed text."""

    def __init__(
        self,
        language: str = "en-US",
        listen_timeout: int = 5,
        phrase_limit: int = 15,
    ) -> None:
        self._recognizer = sr.Recognizer()
        self._language = language
        self._listen_timeout = listen_timeout
        self._phrase_limit = phrase_limit

    def listen(self) -> str:
        """Capture speech from the default microphone and return transcribed text."""
        try:
            microphone = sr.Microphone()
        except OSError as e:
            raise VoiceInputError(
                "No microphone found. Check your audio device."
            ) from e

        with microphone as source:
            print("Listening... (speak now)")
            self._recognizer.adjust_for_ambient_noise(source, duration=0.5)

            try:
                audio = self._recognizer.listen(
                    source,
                    timeout=self._listen_timeout,
                    phrase_time_limit=self._phrase_limit,
                )
            except sr.WaitTimeoutError as e:
                raise VoiceInputError(
                    "No speech detected within the timeout. Try again."
                ) from e

        try:
            text = self._recognizer.recognize_google(
                audio, language=self._language
            )
        except sr.UnknownValueError as e:
            raise VoiceInputError("Could not understand the audio.") from e
        except sr.RequestError as e:
            raise VoiceInputError(
                f"Speech recognition service unavailable: {e}"
            ) from e

        text = text.strip()
        if not text:
            raise VoiceInputError("Transcription was empty.")

        return text
