class PromptService:
    def get_action_extraction_prompt(
        self,
        email_text: str,
        links: list[str],
        sender: str | None,
        subject: str | None,
    ) -> str:
        """
        Generiert einen Prompt, der eine E-Mail klassifiziert und eine direkt
        ausführbare Handlung extrahiert, als striktes JSON-Objekt.
        """
        links_block = (
            "\n".join(f"[{i}] {link}" for i, link in enumerate(links))
            if links
            else "(keine Links gefunden)"
        )
        return (
            "Du analysierst eine eingehende E-Mail und entscheidest, ob sie eine konkrete "
            "Handlung vom Empfänger erfordert oder nicht.\n\n"
            "Antworte AUSSCHLIESSLICH mit einem validen JSON-Objekt, ohne Markdown-Codeblock, "
            "ohne Kommentare, exakt in diesem Format:\n"
            "{\n"
            '  "category": "action" | "info" | "thanks" | "newsletter",\n'
            '  "actionType": "meeting" | "confirm_link" | "reply_needed" | "document" | '
            '"other" | null,\n'
            '  "actionSummary": string | null,\n'
            '  "linkIndex": number | null,\n'
            '  "meeting": { "subject": string | null, "proposedTime": string | null, '
            '"attendees": string[] } | null\n'
            "}\n\n"
            "REGELN:\n"
            '1. "category"="action" NUR wenn der Empfänger aktiv etwas tun muss (Termin, '
            "Antwort, Link bestätigen, Dokument liefern). Reine Infos, Danksagungen, Feedback "
            'und Newsletter sind "info", "thanks" bzw. "newsletter".\n'
            '2. "actionSummary" ist EIN kurzer, konkreter Satz auf Deutsch, der die Handlung so '
            "beschreibt, dass man sie ausführen kann, OHNE die Mail zu öffnen "
            '(z. B. "Termin mit Herrn Schmidt vereinbaren: Vorschlag Do 14 Uhr").\n'
            '3. "linkIndex" NUR setzen, wenn "actionType"="confirm_link": wähle den Index aus '
            "der Link-Liste unten, der zur Handlung passt. ERFINDE NIEMALS eine URL, nutze "
            "ausschließlich die Indizes aus der Liste. Ist kein passender Link vorhanden, "
            'setze "linkIndex" auf null.\n'
            '4. "meeting" NUR befüllen, wenn "actionType"="meeting", mit den in der Mail '
            "genannten Details. Fehlende Angaben bleiben null bzw. leere Liste.\n\n"
            f"ABSENDER: {sender or 'unbekannt'}\n"
            f"BETREFF: {subject or 'unbekannt'}\n\n"
            f"LINKS IN DER MAIL:\n{links_block}\n\n"
            f"E-MAIL-TEXT:\n{email_text.strip()}\n\n"
            "JSON:"
        )

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
