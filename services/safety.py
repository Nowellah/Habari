from typing import Any


class SafetyService:
    """Keyword-based urgency detection for child safety."""

    URGENT_KEYWORDS: list[str] = [
        # Self-harm / suicide
        "kill myself",
        "hurt myself",
        "want to die",
        "suicidal",
        "end my life",
        "harm myself",
        # Sexual exploitation
        "naked pictures",
        "send nudes",
        "grooming",
        "exploitation",
        "nude photo",
        "nude image",
        # Physical danger
        "hitting me",
        "beating me",
        "hurting me",
        "in danger",
        "being hit",
        "being beaten",
        # Threats
        "threatens",
        "blackmail",
        "will hurt",
        "going to hurt",
        "threatened me",
    ]

    _HARM_MAP: dict[str, str] = {
        "kill myself": "self_harm",
        "hurt myself": "self_harm",
        "want to die": "self_harm",
        "suicidal": "self_harm",
        "end my life": "self_harm",
        "harm myself": "self_harm",
        "naked pictures": "sexual_exploitation",
        "send nudes": "sexual_exploitation",
        "grooming": "sexual_exploitation",
        "exploitation": "sexual_exploitation",
        "nude photo": "sexual_exploitation",
        "nude image": "sexual_exploitation",
        "hitting me": "physical_danger",
        "beating me": "physical_danger",
        "hurting me": "physical_danger",
        "in danger": "physical_danger",
        "being hit": "physical_danger",
        "being beaten": "physical_danger",
        "threatens": "threat",
        "blackmail": "threat",
        "will hurt": "threat",
        "going to hurt": "threat",
        "threatened me": "threat",
    }

    _EMERGENCY_MESSAGES: dict[str, str] = {
        "en": (
            "⚠️ It sounds like you may be in immediate danger. "
            "Please call the Child Helpline on 116 right now. "
            "If you cannot call, find a trusted adult. You are not alone."
        ),
        "lg": (
            "⚠️ Kiboneka nti oba oli mu kabi kya mangu. "
            "Saba obuyambi nga oyita ku 116 kati."
        ),
        "sw": (
            "⚠️ Inaonekana unaweza kuwa katika hatari ya haraka. "
            "Tafadhali piga simu ya Msaada wa Watoto kwa 116 sasa hivi."
        ),
        "rn": (
            "⚠️ Bigaragara ngu ushobora kuba mu kabi. "
            "Mwetegereze obufasha ku 116 hano."
        ),
    }

    def check_urgency(self, text: str) -> dict[str, Any]:
        """
        Analyse text for urgent safety keywords.

        Returns a dict with:
          urgent   (bool)
          harm_type (str)
          severity  (str): "low" | "medium" | "high" | "critical"
        """
        if not text:
            return {"urgent": False, "harm_type": "none", "severity": "low"}

        lower = text.lower()
        for keyword in self.URGENT_KEYWORDS:
            if keyword in lower:
                harm_type = self._HARM_MAP.get(keyword, "general")
                return {"urgent": True, "harm_type": harm_type, "severity": "critical"}

        return {"urgent": False, "harm_type": "none", "severity": "low"}

    def get_emergency_guidance(self, language: str = "en") -> dict[str, str]:
        """Return localized emergency guidance."""
        message = self._EMERGENCY_MESSAGES.get(language, self._EMERGENCY_MESSAGES["en"])
        return {
            "helpline": "116",
            "message": message,
            "language": language,
        }


# Module-level singleton
safety_service = SafetyService()
