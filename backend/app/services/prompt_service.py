class PromptService:
    def get_reply_prompt(self, email_text: str) -> str:
        """
        Generiert einen Prompt, um eine einzelne, professionelle E-Mail-Antwort zu erhalten.
        """
        return (
            "Verfasse eine professionelle und vollständige E-Mail-Antwort auf "
            "die folgende eingegangene Nachricht.\n"
            "Gehe dabei auf den Inhalt ein und gib ausschließlich den fertigen "
            "Antworttext zurück.\n\n"
            f"E-Mail-Text:\n{email_text.strip()}"
        )
