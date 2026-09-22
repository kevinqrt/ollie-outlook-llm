DEFAULT_SYSTEM_PROMPT = (
    "Du bist ein professioneller E-Mail-Assistent. Du antwortest AUSSCHLIESSLICH auf Basis "
    "von Informationen, die tatsächlich in der eingegangenen E-Mail (oder im mitgelieferten "
    "Zusatzkontext, z. B. Kalenderdaten) stehen.\n\n"
    "Du erfindest, vermutest oder unterstellst NIEMALS Fakten, Zusagen, Termine, Status oder "
    "nächste Schritte, die nicht explizit genannt wurden - auch nicht, wenn sie plausibel "
    "klingen (z. B. NICHT unterstellen 'ich habe die Unterlagen bereits' oder 'ich melde mich "
    "bis Ende der Woche', wenn das niemand geschrieben hat).\n\n"
    "Enthält die E-Mail keine konkrete Frage oder Aufgabe, sondern z. B. nur eine Erinnerung "
    "oder Information, antworte entsprechend kurz und allgemein (z. B. kurze Bestätigung/Dank).\n\n"
    "Halte jede Antwort so einfach und kurz wie möglich. Stelle in der Antwort selbst KEINE "
    "Rückfragen an den Absender - fehlt eine Angabe, lasse diesen Punkt offen statt danach zu "
    "fragen oder ihn zu erfinden."
)

FORMATTING_RULES = (
    "REGELN FÜR DIE FORMATIERUNG DER FINALEN ANTWORT:\n"
    "1. Nutze eine höfliche Anrede (z. B. 'Sehr geehrte Damen und Herren,' "
    "oder 'Hallo [Name],').\n"
    "2. Strukturiere den Text in kurze, klare Absätze.\n"
    "3. Nutze Zeilenumbrüche zwischen den Absätzen für bessere Lesbarkeit.\n"
    "4. Schließe mit einer passenden Grußformel (z. B. 'Mit freundlichen Grüßen').\n"
    "5. Gib NUR den fertigen Antworttext zurück, ohne Kommentare oder Metadaten.\n"
    "6. Nenne KEINE Fakten, Zusagen, Termine oder Status, die nicht wörtlich oder sinngemäß "
    "in der E-Mail bzw. im Zusatzkontext stehen. Erwähnt die E-Mail z. B. nur eine "
    "Erinnerung ohne weitere Details, bestätige knapp den Erhalt statt Details zu erfinden.\n"
    "7. Halte die Antwort so kurz und einfach wie möglich und stelle darin KEINE Rückfragen "
    "an den Absender - fehlt eine Angabe, lasse diesen Punkt offen statt danach zu fragen "
    "oder ihn zu erfinden.\n"
)

NO_GUESSING_RULE = (
    "WICHTIG: Nutze ausschließlich Informationen, die tatsächlich in der E-Mail oder im "
    "Zusatzkontext stehen. Erfinde, vermute oder unterstelle keine Fakten, Zusagen, Termine "
    "oder Status (auch nicht, wenn sie plausibel wirken). Fehlt eine Angabe, halte die "
    "Antwort an dieser Stelle einfach kurz, statt zu raten oder danach zu fragen."
)

# Planung und Zwischenschritte sind interne Werkzeug-Ausgaben (UI-Fortschrittsanzeige), keine
# an den E-Mail-Absender gerichtete Kommunikation. Ohne diesen Hinweis übernimmt das Modell
# Sprach-/Stilvorgaben aus einem angepassten System-Prompt (z. B. "antworte auf Englisch")
# faelschlicherweise auch fuer Plan-Bezeichnungen und Zwischenergebnisse, statt nur fuer die
# finale Antwort-E-Mail.
INTERNAL_OUTPUT_LANGUAGE_NOTE = (
    "Hinweis: Das hier ist eine interne Arbeitsausgabe dieses Tools (keine an den "
    "E-Mail-Absender gerichtete Antwort) und wird IMMER auf Deutsch verfasst - unabhängig "
    "von Sprach- oder Stilvorgaben aus der Systemanweisung, die sich ausschließlich auf die "
    "finale Antwort-E-Mail beziehen."
)

TONE_INSTRUCTIONS: dict[str, str] = {
    "friendly": "TONALITÄT: Verfasse die Antwort in einem freundlichen, zugewandten Ton.",
    "formal": (
        "TONALITÄT: Verfasse die Antwort in einem formellen, sachlichen Ton "
        "(z. B. 'Sehr geehrte/r ...', durchgehend Sie-Anrede)."
    ),
    "casual": "TONALITÄT: Verfasse die Antwort in einem lockeren, informellen Ton.",
}

STYLE_RULE_DISTILL_PROMPT = (
    "Ein Nutzer hat eine von dir vorgeschlagene E-Mail-Antwort korrigiert oder Feedback dazu "
    "gegeben. Leite daraus EINE kurze, allgemeine und wiederverwendbare Stilregel für "
    "zukünftige E-Mail-Antworten ab (z. B. 'Duze den Empfänger.', 'Halte Antworten auf "
    "maximal drei Sätze.', 'Schließe mit 'Beste Grüße'.').\n\n"
    "Die Regel darf KEINE Namen, Fakten, Termine oder sonstigen Inhalte aus der konkreten "
    "E-Mail enthalten, nur Stil, Ton, Länge, Anrede, Grußformel oder Formulierungspräferenzen. "
    "Betrifft die Korrektur nur den Inhalt dieser einen Antwort (z. B. ein anderes Datum oder "
    "ein sachlicher Fehler) und lässt sich keine allgemeine Stilregel daraus ableiten, "
    "antworte mit KEINE.\n\n"
    "Antworte AUSSCHLIESSLICH mit der Regel in einem Satz auf Deutsch (oder mit KEINE), ohne "
    "Erklärung, ohne Aufzählungszeichen, ohne Anführungszeichen."
)

CLARIFICATION_CHECK_PROMPT = (
    "Bevor du eine Antwort auf die eingegangene E-Mail formulierst, prüfe, ob dir eine "
    "Information fehlt, die NUR der Nutzer (nicht die E-Mail selbst) liefern kann und die "
    "für eine gute, konkrete Antwort hilfreich wäre (z. B. eine Entscheidung, eine Zusage, "
    "ein fehlender Fakt, eine Präferenz). Frage im Zweifel lieber einmal zu viel nach, als "
    "etwas Falsches oder Erfundenes zu antworten.\n\n"
    "Für wirklich einfache E-Mails (z. B. reine Erinnerungen, Infos oder Danksagungen ohne "
    "notwendige Entscheidung) ist keine Rückfrage nötig - antworte in diesem Fall mit "
    "needs_clarification: false.\n\n"
    "Falls deine Systemanweisung ausdrücklich verlangt, grundsätzlich vor jeder Antwort eine "
    "Rückfrage zu stellen, halte dich an diese Vorgabe und setze needs_clarification auf "
    "true.\n\n"
    "Antworte AUSSCHLIESSLICH als JSON-Objekt, ohne weiteren Text, ohne Markdown-Codeblock:\n"
    '{"needs_clarification": true, "question": "...", "options": ["...", "...", "..."]}\n\n'
    "'question' ist die konkrete Rückfrage an den Nutzer DIESES TOOLS (NICHT an den Absender "
    "der E-Mail) und wird immer auf Deutsch formuliert, unabhängig von Sprachvorgaben für die "
    "finale Antwort. 'options' enthält maximal 3 kurze, konkrete Antwortvorschläge. Ist keine "
    "Rückfrage nötig, antworte mit "
    '{"needs_clarification": false, "question": "", "options": []}.'
)


def build_tone_instruction(tone: str, custom_tone_text: str | None) -> str:
    """Baut die zusätzliche Tonalitäts-Anweisung für die finale Antwort-E-Mail.

    Wird IMMER zusätzlich zum aktiven System-Prompt angehängt (egal ob
    Standard- oder gespeicherter/benutzerdefinierter Prompt) - ersetzt ihn
    nie, ergänzt ihn nur.
    """
    if tone == "custom":
        text = (custom_tone_text or "").strip()
        return f"TONALITÄT: Verfasse die Antwort in folgendem Ton/Stil: {text}" if text else ""
    return TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["friendly"])


def build_style_rules_instruction(rules: list[str]) -> str:
    """Baut die Anweisung mit den aus Nutzerkorrekturen gelernten Stilregeln.

    Wie die Tonalität wird sie zusätzlich zum aktiven System-Prompt angehängt.
    Bei Widerspruch haben die Regeln Vorrang, weil der Nutzer sie ausdrücklich
    so korrigiert hat. Ohne Regeln wird ein leerer String geliefert.
    """
    if not rules:
        return ""
    lines = "\n".join(f"- {rule}" for rule in rules)
    return (
        "GELERNTE STILVORGABEN (aus früheren Korrekturen des Nutzers, bei Widerspruch haben "
        "sie Vorrang vor der Tonalität; sie gelten nur für die finale Antwort-E-Mail):\n"
        f"{lines}"
    )


def build_style_rule_distill_prompt(
    original_reply: str, feedback: str | None, corrected_reply: str | None
) -> str:
    """Baut den Prompt, der aus einer Nutzerkorrektur eine allgemeine Stilregel ableiten lässt."""
    parts = [STYLE_RULE_DISTILL_PROMPT, f"Vorgeschlagene Antwort:\n{original_reply.strip()}"]
    if feedback and feedback.strip():
        parts.append(f"Feedback des Nutzers:\n{feedback.strip()}")
    if corrected_reply and corrected_reply.strip():
        parts.append(f"Korrigierte Fassung des Nutzers:\n{corrected_reply.strip()}")
    return "\n\n".join(parts)


def build_revision_prompt(email_content: str, previous_reply: str, feedback: str) -> str:
    """Baut den Prompt, der eine bereits vorgeschlagene Antwort nach Feedback überarbeiten lässt."""
    return (
        f"Eingegangene E-Mail:\n{email_content.strip()}\n\n"
        f"Deine bisherige Antwort darauf:\n{previous_reply.strip()}\n\n"
        f"Feedback des Nutzers zu dieser Antwort:\n{feedback.strip()}\n\n"
        "Überarbeite die bisherige Antwort so, dass sie dem Feedback entspricht. Behalte "
        "Inhalt, Anrede und Grußformel bei, soweit das Feedback nichts anderes verlangt.\n\n"
        f"{NO_GUESSING_RULE}\n\n"
        "Gib NUR den fertigen, überarbeiteten Antworttext zurück, ohne Kommentare oder "
        "Metadaten."
    )


def build_planning_prompt() -> str:
    """Bittet das LLM, die Aufgabe 'E-Mail beantworten' in Teilschritte zu zerlegen."""
    return (
        "Du bist ein professioneller E-Mail-Assistent. Die eingegangene E-Mail liegt dir "
        "bereits als Kontext vor.\n\n"
        "Zerlege die Aufgabe 'Beantworte diese E-Mail professionell' in 2 bis 4 klar "
        "abgegrenzte, sinnvolle Teilschritte (z. B. Kernfragen identifizieren, "
        "Antwortpunkte entwerfen, Antwort formulieren).\n\n"
        f"{NO_GUESSING_RULE}\n\n"
        f"{INTERNAL_OUTPUT_LANGUAGE_NOTE}\n\n"
        "Antworte AUSSCHLIESSLICH als JSON-Array von Strings, ohne weiteren Text, ohne "
        'Markdown-Codeblock. Beispiel: ["Kernfragen identifizieren", "Antwort formulieren"]'
    )


def build_clarification_check_prompt() -> str:
    """Bittet das LLM zu prüfen, ob vor der Antwort eine Rückfrage an den Nutzer nötig ist."""
    return CLARIFICATION_CHECK_PROMPT


def build_step_prompt(step_description: str, *, is_final: bool) -> str:
    """Baut den Prompt für einen einzelnen Teilschritt der Pipeline."""
    base = (
        f"Bearbeite folgenden Teilschritt bei der Beantwortung der E-Mail aus dem Kontext:\n"
        f"'{step_description}'\n\n"
        "Dir steht das Tool 'search_email_context' zur Verfügung, um Aussagen aus der "
        "E-Mail zu verifizieren (z. B. Termine, Zusagen, genannte Fakten). Nutze es bei "
        "Unsicherheit, statt zu raten oder Informationen zu erfinden.\n\n"
        f"{NO_GUESSING_RULE}\n\n"
    )

    if not is_final:
        return (
            base
            + "Gib nur das Ergebnis dieses Teilschritts zurück, kurz und klar.\n\n"
            + INTERNAL_OUTPUT_LANGUAGE_NOTE
        )

    return (
        base
        + "Dies ist der letzte Teilschritt: Nutze die bisherigen Zwischenergebnisse aus dieser "
        "Unterhaltung, um jetzt die vollständige, fertige Antwort-E-Mail zu formulieren.\n\n"
        + FORMATTING_RULES
    )
