class PromptService:
    def get_reply_prompt(self, email_text: str) -> str:
        """
        Generiert einen Prompt, um eine perfekt formatierte E-Mail-Antwort zu erhalten.
        """
        return (
            "Du bist ein professioneller E-Mail-Assistent. Deine Aufgabe ist es, "
            "eine Antwort auf die folgende E-Mail zu verfassen.\n\n"
            "REGELN FÜR DIE FORMATIERUNG:\n"
            "1. Nutze eine höfliche Anrede (z. B. 'Sehr geehrte Damen und Herren,' "
            "oder 'Hallo [Name],').\n"
            "2. Strukturiere den Text in kurze, klare Absätze.\n"
            "3. Nutze Zeilenumbrüche zwischen den Absätzen für bessere Lesbarkeit.\n"
            "4. Schließe mit einer passenden Grußformel (z. B. 'Mit freundlichen Grüßen').\n"
            "5. Gib NUR den fertigen Antworttext zurück, ohne Kommentare oder Metadaten.\n\n"
            f"EINGEGANGENE E-MAIL:\n{email_text.strip()}\n\n"
            "ANTWORT:"
        )
