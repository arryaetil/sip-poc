"""Server messages in the user's language.

Routes raise errors in English (that is what logs and tests read). The browser sends
the interface language in `X-SIP-Language`; `translate` turns a known English message
into Dutch or German just before it is sent. An unknown message stays English rather
than becoming a wrong translation.
"""

from __future__ import annotations

import re

LANGUAGES = ("en", "nl", "de")

# English -> (Dutch, German)
EXACT: dict[str, tuple[str, str]] = {
    "Authentication required": ("Meld je eerst aan.", "Bitte melde dich zuerst an."),
    "Your role does not have access to this action.": ("Je rol heeft geen toegang tot deze actie.", "Deine Rolle hat keinen Zugriff auf diese Aktion."),
    "Authentication is not configured": ("Aanmelden is niet ingesteld.", "Die Anmeldung ist nicht eingerichtet."),
    "Incorrect email or password": ("Onjuist e-mailadres of wachtwoord.", "E-Mail-Adresse oder Passwort ist falsch."),
    "A user with this email already exists.": ("Er bestaat al een gebruiker met dit e-mailadres.", "Es gibt bereits einen Benutzer mit dieser E-Mail-Adresse."),
    "User not found": ("Gebruiker niet gevonden.", "Benutzer nicht gefunden."),
    "You cannot delete your own account.": ("Je kunt je eigen account niet verwijderen.", "Du kannst dein eigenes Konto nicht löschen."),
    "Not found": ("Niet gevonden.", "Nicht gefunden."),
    "Conversation not found": ("Gesprek niet gevonden.", "Gespräch nicht gefunden."),
    "Context conversation not found": ("Gesprek niet gevonden.", "Gespräch nicht gefunden."),
    "Knowledge conversation not found": ("Gesprek niet gevonden.", "Gespräch nicht gefunden."),
    "Product Owner conversation not found": ("Gesprek niet gevonden.", "Gespräch nicht gefunden."),
    "Lead conversation not found": ("Gesprek niet gevonden.", "Gespräch nicht gefunden."),
    "Update conversation not found": ("Gesprek niet gevonden.", "Gespräch nicht gefunden."),
    "Business Context not found": ("Business Context niet gevonden.", "Business Context nicht gefunden."),
    "Approved Business Context not found": ("Goedgekeurde Business Context niet gevonden.", "Genehmigter Business Context nicht gefunden."),
    "The Business Context being updated no longer exists": ("De Business Context die je bijwerkt bestaat niet meer.", "Der Business Context, den du aktualisierst, existiert nicht mehr."),
    "Your role cannot change this Business Context": ("Je rol mag deze Business Context niet wijzigen.", "Deine Rolle darf diesen Business Context nicht ändern."),
    "Version not found": ("Versie niet gevonden.", "Version nicht gefunden."),
    "This conversation updates an existing context; review the changes instead": (
        "Dit gesprek werkt een bestaande context bij; bekijk de wijzigingen.",
        "Dieses Gespräch aktualisiert einen bestehenden Context; prüfe die Änderungen.",
    ),
    "The changes need more information before they can be reviewed.": (
        "Er is meer informatie nodig voordat je de wijzigingen kunt bekijken.",
        "Es werden mehr Informationen benötigt, bevor du die Änderungen prüfen kannst.",
    ),
    "Preparing the changes failed; please try again.": ("Het voorbereiden van de wijzigingen is mislukt; probeer het opnieuw.", "Die Vorbereitung der Änderungen ist fehlgeschlagen; bitte versuche es erneut."),
    "The Business Context needs more information before it can be saved.": (
        "De Business Context heeft meer informatie nodig voordat je hem kunt opslaan.",
        "Der Business Context braucht mehr Informationen, bevor er gespeichert werden kann.",
    ),
    "The model did not return a Business Context": ("Het model gaf geen Business Context terug.", "Das Modell hat keinen Business Context geliefert."),
    "Website source not found": ("Websitebron niet gevonden.", "Website-Quelle nicht gefunden."),
    "Website service or solution not found": ("Dienst of oplossing van de website niet gevonden.", "Dienst oder Lösung der Website nicht gefunden."),
    "Upload not found": ("Bestand niet gevonden.", "Datei nicht gefunden."),
    "Extracted document text is unavailable": ("De tekst van dit document is niet beschikbaar.", "Der Text dieses Dokuments ist nicht verfügbar."),
    "Could not remove upload from the knowledge index": ("Het bestand kon niet uit de kennisbank worden verwijderd.", "Die Datei konnte nicht aus der Wissensbasis entfernt werden."),
    "Could not remove Business Context from the knowledge index": ("De Business Context kon niet uit de kennisbank worden verwijderd.", "Der Business Context konnte nicht aus der Wissensbasis entfernt werden."),
    "Context evidence not found": ("Onderbouwing niet gevonden.", "Nachweis nicht gefunden."),
    "Context evidence must be linked to a conversation or context.": ("Onderbouwing moet bij een gesprek of context horen.", "Ein Nachweis muss zu einem Gespräch oder Context gehören."),
    "Story proposal not found": ("Storyvoorstel niet gevonden.", "Story-Vorschlag nicht gefunden."),
    "Change proposal not found": ("Wijzigingsvoorstel niet gevonden.", "Änderungsvorschlag nicht gefunden."),
    "Your account cannot create stories in Azure DevOps.": ("Je account mag geen stories aanmaken in Azure DevOps.", "Dein Konto darf keine Stories in Azure DevOps anlegen."),
    "Your account cannot change stories in Azure DevOps.": ("Je account mag geen stories wijzigen in Azure DevOps.", "Dein Konto darf keine Stories in Azure DevOps ändern."),
    "This story is being created right now.": ("Deze story wordt op dit moment aangemaakt.", "Diese Story wird gerade angelegt."),
    "This change was already applied.": ("Deze wijziging is al doorgevoerd.", "Diese Änderung wurde bereits übernommen."),
    "This change is being applied right now.": ("Deze wijziging wordt op dit moment doorgevoerd.", "Diese Änderung wird gerade übernommen."),
    "This proposal is being created or was created already; it can no longer be changed.": (
        "Dit voorstel wordt aangemaakt of is al aangemaakt; je kunt het niet meer wijzigen.",
        "Dieser Vorschlag wird angelegt oder wurde bereits angelegt; er kann nicht mehr geändert werden.",
    ),
    "The proposal changed or is already being created. Reload it first.": (
        "Het voorstel is gewijzigd of wordt al aangemaakt. Laad het eerst opnieuw.",
        "Der Vorschlag hat sich geändert oder wird bereits angelegt. Lade ihn zuerst neu.",
    ),
    "The proposal changed or is already being applied. Reload it first.": (
        "Het voorstel is gewijzigd of wordt al doorgevoerd. Laad het eerst opnieuw.",
        "Der Vorschlag hat sich geändert oder wird bereits übernommen. Lade ihn zuerst neu.",
    ),
    "The proposal changed in the meantime. Reload it and make your change again.": (
        "Het voorstel is intussen gewijzigd. Laad het opnieuw en breng je wijziging opnieuw aan.",
        "Der Vorschlag hat sich inzwischen geändert. Lade ihn neu und nimm deine Änderung erneut vor.",
    ),
    "The proposal changed after you confirmed it. Review the new version and confirm again.": (
        "Het voorstel is gewijzigd nadat je het bevestigde. Bekijk de nieuwe versie en bevestig opnieuw.",
        "Der Vorschlag hat sich nach deiner Bestätigung geändert. Prüfe die neue Version und bestätige erneut.",
    ),
    "The proposal changed after you confirmed it. Review it and confirm again.": (
        "Het voorstel is gewijzigd nadat je het bevestigde. Bekijk het en bevestig opnieuw.",
        "Der Vorschlag hat sich nach deiner Bestätigung geändert. Prüfe ihn und bestätige erneut.",
    ),
    "It is not yet known whether the earlier attempt created this story. Check Azure DevOps first.": (
        "Het is nog niet bekend of de vorige poging deze story heeft aangemaakt. Controleer eerst Azure DevOps.",
        "Es ist noch nicht bekannt, ob der vorige Versuch diese Story angelegt hat. Prüfe zuerst Azure DevOps.",
    ),
    "It is not yet known whether the earlier attempt changed this story. Check first.": (
        "Het is nog niet bekend of de vorige poging deze story heeft gewijzigd. Controleer dat eerst.",
        "Es ist noch nicht bekannt, ob der vorige Versuch diese Story geändert hat. Prüfe das zuerst.",
    ),
    "The Product Owner gave an answer SIP could not read. Your draft is unchanged; please try again.": (
        "De Product Owner gaf een antwoord dat SIP niet kon lezen. Je concept is ongewijzigd; probeer het opnieuw.",
        "Der Product Owner gab eine Antwort, die SIP nicht lesen konnte. Dein Entwurf ist unverändert; bitte versuche es erneut.",
    ),
    "The Product Owner could not be reached. Your draft is unchanged; please try again.": (
        "De Product Owner is niet bereikbaar. Je concept is ongewijzigd; probeer het opnieuw.",
        "Der Product Owner ist nicht erreichbar. Dein Entwurf ist unverändert; bitte versuche es erneut.",
    ),
    "The Product Owner assistant is not available yet.": ("De Product Owner-assistent is nog niet beschikbaar.", "Der Product-Owner-Assistent ist noch nicht verfügbar."),
    "Lead list not found": ("Leadlijst niet gevonden.", "Lead-Liste nicht gefunden."),
    "Lead conversation has no Business Context": ("Dit gesprek hoort bij geen Business Context.", "Dieses Gespräch gehört zu keinem Business Context."),
    "Choose an approved Business Context first": ("Kies eerst waarvoor je leads zoekt.", "Wähle zuerst, wofür du Leads suchst."),
    "Say how many leads you want first": ("Zeg eerst hoeveel leads je wilt.", "Sag zuerst, wie viele Leads du möchtest."),
    "The search brief is not complete yet; finish the conversation first": (
        "De zoekopdracht is nog niet compleet; maak eerst het gesprek af.",
        "Der Suchauftrag ist noch nicht vollständig; beende zuerst das Gespräch.",
    ),
    "Web search is not configured (SERPER_API_KEY).": ("Webzoeken is nog niet ingesteld (SERPER_API_KEY).", "Die Websuche ist noch nicht eingerichtet (SERPER_API_KEY)."),
    "The Lead finder assistant is not available yet.": ("De Lead finder-assistent is nog niet beschikbaar.", "Der Lead-finder-Assistent ist noch nicht verfügbar."),
    "The Lead finder is not available yet.": ("De Lead finder is nog niet beschikbaar.", "Der Lead finder ist noch nicht verfügbar."),
    "The Lead finder gave an answer SIP could not read. Please try again.": (
        "De Lead finder gaf een antwoord dat SIP niet kon lezen. Probeer het opnieuw.",
        "Der Lead finder gab eine Antwort, die SIP nicht lesen konnte. Bitte versuche es erneut.",
    ),
    "The Lead finder could not be reached. Please try again.": ("De Lead finder is niet bereikbaar. Probeer het opnieuw.", "Der Lead finder ist nicht erreichbar. Bitte versuche es erneut."),
    "Dify is busy: the free plan's request limit was reached. Try again in a minute.": (
        "Dify is druk: de limiet van het gratis abonnement is bereikt. Probeer het over een minuut opnieuw.",
        "Dify ist ausgelastet: Das Limit des kostenlosen Tarifs ist erreicht. Versuche es in einer Minute erneut.",
    ),
    "Some information is missing or not valid.": ("Er ontbreekt informatie of iets is niet geldig.", "Es fehlen Angaben oder etwas ist ungültig."),
}

# Messages with a variable part: English pattern -> (Dutch, German), with \1 for the part.
PATTERNS: list[tuple[re.Pattern, tuple[str, str]]] = [
    (re.compile(r"^Model request failed: (.*)$", re.S), ("Het model gaf een fout: \\1", "Das Modell meldete einen Fehler: \\1")),
    (re.compile(r"^Context preparation failed: (.*)$", re.S), ("Het voorbereiden van de context is mislukt: \\1", "Die Vorbereitung des Context ist fehlgeschlagen: \\1")),
    (re.compile(r"^Knowledge assistant request failed: (.*)$", re.S), ("De kennisassistent gaf een fout: \\1", "Der Wissensassistent meldete einen Fehler: \\1")),
    (re.compile(r"^Document discussion failed: (.*)$", re.S), ("Het bespreken van het document is mislukt: \\1", "Die Besprechung des Dokuments ist fehlgeschlagen: \\1")),
    (re.compile(r"^The marketing studio could not be prepared: (.*)$", re.S), ("De Marketing studio kon niet worden voorbereid: \\1", "Das Marketing studio konnte nicht vorbereitet werden: \\1")),
    (re.compile(r"^This story was already created in Azure DevOps as #(\d+)\.$"), ("Deze story is al aangemaakt in Azure DevOps als #\\1.", "Diese Story wurde bereits in Azure DevOps als #\\1 angelegt.")),
    (re.compile(r"^The proposal is not complete yet: (.*)\.$", re.S), ("Het voorstel is nog niet compleet: \\1.", "Der Vorschlag ist noch nicht vollständig: \\1.")),
]


def language_of(header: str | None) -> str:
    """The interface language SIP sent, or English."""
    value = (header or "").strip().casefold()[:2]
    return value if value in LANGUAGES else "en"


def translate(message, language: str):
    """A known English message in Dutch or German; anything else unchanged."""
    if language == "en" or not isinstance(message, str):
        return message
    index = 0 if language == "nl" else 1
    if message in EXACT:
        return EXACT[message][index]
    for pattern, targets in PATTERNS:
        if pattern.match(message):
            return pattern.sub(targets[index], message)
    return message
