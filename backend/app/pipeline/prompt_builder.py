FORMATTING_RULES = (
    "REGELN FÜR DIE FORMATIERUNG DER FINALEN ANTWORT:\n"
    "1. Nutze eine höfliche Anrede (z. B. 'Sehr geehrte Damen und Herren,' "
    "oder 'Hallo [Name],').\n"
    "2. Strukturiere den Text in kurze, klare Absätze.\n"
    "3. Nutze Zeilenumbrüche zwischen den Absätzen für bessere Lesbarkeit.\n"
    "4. Schließe mit einer passenden Grußformel (z. B. 'Mit freundlichen Grüßen').\n"
    "5. Gib NUR den fertigen Antworttext zurück, ohne Kommentare oder Metadaten.\n"
)


def build_planning_prompt() -> str:
    """Bittet das LLM, die Aufgabe 'E-Mail beantworten' in Teilschritte zu zerlegen."""
    return (
        "Du bist ein professioneller E-Mail-Assistent. Die eingegangene E-Mail liegt dir "
        "bereits als Kontext vor.\n\n"
        "Zerlege die Aufgabe 'Beantworte diese E-Mail professionell' in 2 bis 4 klar "
        "abgegrenzte, sinnvolle Teilschritte (z. B. Kernfragen identifizieren, "
        "Antwortpunkte entwerfen, Antwort formulieren).\n\n"
        "Antworte AUSSCHLIESSLICH als JSON-Array von Strings, ohne weiteren Text, ohne "
        'Markdown-Codeblock. Beispiel: ["Kernfragen identifizieren", "Antwort formulieren"]'
    )


def build_step_prompt(step_description: str, *, is_final: bool) -> str:
    """Baut den Prompt für einen einzelnen Teilschritt der Pipeline."""
    base = (
        f"Bearbeite folgenden Teilschritt bei der Beantwortung der E-Mail aus dem Kontext:\n"
        f"'{step_description}'\n\n"
        "Dir steht das Tool 'search_email_context' zur Verfügung, um Aussagen aus der "
        "E-Mail zu verifizieren (z. B. Termine, Zusagen, genannte Fakten). Nutze es bei "
        "Unsicherheit, statt zu raten oder Informationen zu erfinden.\n\n"
    )

    if not is_final:
        return base + "Gib nur das Ergebnis dieses Teilschritts zurück, kurz und klar."

    return (
        base
        + "Dies ist der letzte Teilschritt: Nutze die bisherigen Zwischenergebnisse aus dieser "
        "Unterhaltung, um jetzt die vollständige, fertige Antwort-E-Mail zu formulieren.\n\n"
        + FORMATTING_RULES
    )
