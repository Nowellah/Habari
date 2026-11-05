class LanguageService:
    """Manages supported languages and fallback notices."""

    SUPPORTED_LANGUAGES: dict[str, str] = {
        "en": "English",
        "lg": "Luganda",
        "sw": "Swahili",
        "rn": "Runyankore",
    }

    _FALLBACK_NOTICES: dict[str, str] = {
        "lg": (
            "Luganda has limited support at this time. "
            "Some responses may be in English. "
            "A fully translated version is coming soon."
        ),
        "sw": (
            "Swahili has limited support at this time. "
            "Some responses may be in English. "
            "A fully translated version is coming soon."
        ),
        "rn": (
            "Runyankore has limited support at this time. "
            "Some responses may be in English. "
            "A fully translated version is coming soon."
        ),
    }

    def get_language_name(self, code: str) -> str:
        return self.SUPPORTED_LANGUAGES.get(code, code)

    def is_fully_supported(self, code: str) -> bool:
        """Only English is fully supported currently."""
        return code == "en"

    def get_fallback_notice(self, code: str) -> str:
        return self._FALLBACK_NOTICES.get(
            code,
            f"Language '{self.get_language_name(code)}' has limited support. "
            "Responses may default to English.",
        )


# Module-level singleton
language_service = LanguageService()
