"""Translations. English is the source and default language; other languages are dictionaries below.

Adding a language: copy the PL dictionary, translate the values, add it to CATALOGS and LANGUAGES,
and add plural forms to PLURALS (see plural_index()).
"""

import os

LANG = "en"

LANGUAGES = {"auto": "Automatic (system language)", "en": "English", "pl": "Polski"}


def detect():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val:
            code = val.split(":")[0].split("_")[0].split(".")[0].lower()
            return code if code in CATALOGS else "en"
    return "en"


def set_language(code):
    global LANG
    LANG = detect() if code in (None, "", "auto") else (code if code in CATALOGS else "en")
    return LANG


def tr(text, **kw):
    s = CATALOGS.get(LANG, {}).get(text, text)
    return s.format(**kw) if kw else s


def plural_index(n):
    if LANG == "pl":
        if n == 1:
            return 0
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return 1
        return 2
    return 0 if n == 1 else 1


def n_(n, key):
    """Number with a correctly inflected noun, e.g. n_(3, "program") → "3 programs" / "3 programy"."""
    forms = PLURALS[key].get(LANG) or PLURALS[key]["en"]
    return f"{n} {forms[min(plural_index(n), len(forms) - 1)]}"


PLURALS = {
    "program": {"en": ("program", "programs"), "pl": ("program", "programy", "programów")},
    "package": {"en": ("package", "packages"), "pl": ("pakiet", "pakiety", "pakietów")},
    "file": {"en": ("file", "files"), "pl": ("plik", "pliki", "plików")},
    "item": {"en": ("item", "items"), "pl": ("element", "elementy", "elementów")},
    "leftover": {"en": ("leftover", "leftovers"), "pl": ("pozostałość", "pozostałości", "pozostałości")},
    "orphan": {"en": ("orphaned package", "orphaned packages"),
               "pl": ("osierocony pakiet", "osierocone pakiety", "osieroconych pakietów")},
    "rcconf": {"en": ("leftover configuration", "leftover configurations"),
               "pl": ("pozostała konfiguracja", "pozostałe konfiguracje", "pozostałych konfiguracji")},
    "debfile": {"en": ("downloaded .deb file", "downloaded .deb files"),
                "pl": ("pobrany plik .deb", "pobrane pliki .deb", "pobranych plików .deb")},
    "conffile": {"en": ("configuration file", "configuration files"),
                 "pl": ("plik konfiguracyjny", "pliki konfiguracyjne", "plików konfiguracyjnych")},
}

PL = {
    # ── language names / settings
    "Automatic (system language)": "Automatycznie (język systemu)",
    "Language": "Język",
    "Language of the interface. The change takes effect after a restart.":
        "Język interfejsu. Zmiana działa po ponownym uruchomieniu.",
    "Restart now to switch the language?": "Uruchomić program ponownie, aby zmienić język?",

    # ── source kinds
    "APT package (.deb)": "Pakiet APT (.deb)",
    "Manually in /opt": "Ręcznie w /opt",
    "Program installed manually in /opt": "Program zainstalowany ręcznie w /opt",
    "AppImage program": "Program AppImage",

    # ── leftover locations
    "Hidden file in home folder": "Ukryty plik w katalogu domowym",
    "Configuration": "Konfiguracja",
    "Application data": "Dane aplikacji",
    "Application state": "Stan aplikacji",
    "Cache": "Pamięć podręczna",
    "Flatpak data": "Dane Flatpak",
    "Autostart": "Autostart",
    "Menu entry": "Skrót w menu",
    "User systemd service": "Usługa systemd użytkownika",
    "Executable": "Plik wykonywalny",
    "System configuration": "Konfiguracja systemowa",
    "System data": "Dane systemowe",
    "System cache": "Pamięć podręczna systemu",
    "Logs": "Logi",
    "Program in /opt": "Program w /opt",
    "Data in /usr/local": "Dane w /usr/local",
    "Libraries in /usr/local": "Biblioteki w /usr/local",
    "Executable (/usr/local)": "Plik wykonywalny (/usr/local)",
    "APT repository": "Repozytorium APT",
    "Repository key": "Klucz repozytorium",
    "systemd service": "Usługa systemd",
    "System autostart": "Autostart systemowy",
    "Menu entry (system)": "Skrót w menu (systemowy)",
    "Menu entry (/usr/local)": "Skrót w menu (/usr/local)",

    # ── backups
    "A snapper snapshot will be created before uninstalling — the whole system can be restored.":
        "Przed usunięciem zostanie utworzony snapshot snappera — cały system da się przywrócić.",
    "A btrfs snapshot will be created in /.snapshots before uninstalling — the whole system can be restored.":
        "Przed usunięciem zostanie utworzony snapshot btrfs w /.snapshots — cały system da się przywrócić.",
    "A Timeshift restore point will be created before uninstalling.":
        "Przed usunięciem zostanie utworzony punkt przywracania Timeshift.",
    "Before uninstalling, the package list and their configuration files from /etc are saved in {dir} — "
    "together with a restore.sh script that installs them back.":
        "Przed usunięciem zapiszę listę pakietów i ich pliki konfiguracyjne z /etc w {dir} — "
        "razem ze skryptem restore.sh, który zainstaluje je z powrotem.",
    " A full system snapshot is possible on btrfs or with Timeshift installed.":
        " Pełny snapshot całego systemu jest możliwy na btrfs albo z zainstalowanym Timeshiftem.",
    " Timeshift must be configured first (running it once is enough).":
        " Timeshift musi być wcześniej skonfigurowany (wystarczy raz go uruchomić).",

    # ── core messages / log
    "Skipped (unsafe path): {p}": "Pominięto (niebezpieczna ścieżka): {p}",
    "Error: {p}: {e}": "Błąd: {p}: {e}",
    "LEFTOVER → Trash: {p}": "RESZTKI → Kosz: {p}",
    "LEFTOVER deleted: {p}": "RESZTKI usunięto: {p}",
    "LEFTOVER deleted (system): {p}": "RESZTKI usunięto (system): {p}",
    "System files were not deleted: password entry was cancelled.":
        "Nie usunięto plików systemowych: anulowano podawanie hasła.",
    "System files were not deleted: {e}": "Nie usunięto plików systemowych: {e}",
    "UNINSTALLED [{kind}] {name} ({ident})": "ODINSTALOWANO [{kind}] {name} ({ident})",
    "FAILED [{kind}] {name} ({ident})": "NIEUDANE [{kind}] {name} ({ident})",
    "CLEANUP {what} — {result}": "SPRZĄTANIE {what} — {result}",
    "error": "błąd",

    # ── helper
    "!! Rejected: {msg}": "!! Odrzucono: {msg}",
    "invalid name ({what}): {v}": "niepoprawna nazwa ({what}): {v}",
    "package": "pakiet",
    "invalid Flatpak installation: {v}": "niepoprawna instalacja flatpak: {v}",
    "not a folder in /opt: {p}": "to nie jest katalog w /opt: {p}",
    "menu entry not allowed: {p}": "niedozwolony plik skrótu: {p}",
    "paths belong to packages: {p}": "ścieżki należą do pakietów: {p}",
    "unsafe path: {p}": "niebezpieczna ścieżka: {p}",
    "» Configuration backup → {d}": "» Kopia zapasowa konfiguracji → {d}",
    "  saved {packages} and {files}": "  zapisano {packages} i {files}",
    "✓ Backup ready.": "✓ Kopia gotowa.",
    "» Creating a snapper snapshot…": "» Tworzenie snapshotu snappera…",
    "✓ Snapshot ready.": "✓ Snapshot gotowy.",
    "» Creating a btrfs snapshot…": "» Tworzenie snapshotu btrfs…",
    "» Creating a Timeshift restore point (this may take a few minutes)…":
        "» Tworzenie punktu przywracania Timeshift (może potrwać kilka minut)…",
    "✓ Restore point ready.": "✓ Punkt przywracania gotowy.",
    "!! The full backup failed — saving at least the package configuration.":
        "!! Pełna kopia się nie udała — zapisuję przynajmniej konfigurację pakietów.",
    "!! Backup failed: {e} — continuing.": "!! Nie udało się zrobić kopii: {e} — kontynuuję.",
    "» Uninstalling APT packages…": "» Odinstalowywanie pakietów APT…",
    "» Removing snap {s}…": "» Usuwanie snapa {s}…",
    "» Removing Flatpak {s}…": "» Usuwanie Flatpaka {s}…",
    "» Removing {p}…": "» Usuwanie {p}…",
    "» Removing orphaned dependencies…": "» Usuwanie osieroconych zależności…",
    "» Purging leftover configuration…": "» Czyszczenie pozostałej konfiguracji…",
    "» Cleaning the APT cache…": "» Czyszczenie pamięci podręcznej APT…",

    # ── main window: navigation and headers
    "All programs": "Wszystkie programy",
    "Recently installed": "Ostatnio zainstalowane",
    "Largest programs": "Największe programy",
    "APT packages": "Pakiety APT",
    "Programs": "Programy",
    "Sources": "Źródła",
    "Tools": "Narzędzia",
    "Cleanup": "Sprzątanie",
    "Activity log": "Dziennik",
    "Settings": "Ustawienia",
    "About": "O programie",
    "clean uninstalling": "czyste odinstalowywanie",
    "Loading…": "Wczytywanie…",
    "Sort: name": "Sortuj: nazwa",
    "Sort: size": "Sortuj: rozmiar",
    "Sort: install date": "Sortuj: data instalacji",
    "Reload the list (F5)": "Odśwież listę (F5)",
    "Search programs by name, package or description…   (Ctrl+F)":
        "Szukaj programu po nazwie, pakiecie lub opisie…   (Ctrl+F)",
    "installed programs": "zainstalowanych programów",
    "used on disk": "zajmują na dysku",
    "can be freed — click to clean up": "do odzyskania — kliknij, aby posprzątać",
    "Nothing found": "Nic nie znaleziono",
    "Try another name or turn on showing libraries in Settings.":
        "Spróbuj innej nazwy albo włącz w Ustawieniach pokazywanie bibliotek.",
    "Collecting the list of programs…": "Zbieram listę programów…",
    "Untick all": "Odznacz wszystko",
    "  Uninstall selected": "  Odinstaluj zaznaczone",
    "  Uninstall selected ({n})": "  Odinstaluj zaznaczone ({n})",
    "Leftovers: {name}": "Pozostałości: {name}",
    "Leftovers of: {names}": "Pozostałości po: {names}",
    "Loading failed: {e}": "Błąd wczytywania: {e}",
    "Search results for “{q}”: {sub}": "Wyniki wyszukiwania „{q}”: {sub}",
    "The 100 programs taking the most space · {size}": "100 programów zajmujących najwięcej miejsca · {size}",
    "✓  Selected {programs} · {size}": "✓  Zaznaczono {programs} · {size}",
    "Uninstall": "Odinstaluj",
    "Untick": "Odznacz",
    "Tick": "Zaznacz",
    "Find leftovers (without uninstalling)": "Szukaj resztek (bez odinstalowania)",
    "Details": "Szczegóły",
    "Package files": "Pliki pakietu",
    "Files of package {p}": "Pliki pakietu {p}",
    "Open location": "Otwórz lokalizację",
    "Copy identifier": "Kopiuj identyfikator",
    "No information.": "Brak informacji.",
    "Dependency check failed: {e}": "Błąd sprawdzania zależności: {e}",
    "apt does not allow removing these packages:\n\n{err}": "apt nie pozwala usunąć tych pakietów:\n\n{err}",
    "Uninstalling programs": "Odinstalowywanie programów",
    "Uninstalling": "Odinstalowywanie",
    "Removing {name} (Flatpak)": "Usuwanie {name} (Flatpak)",
    "Removing {name}": "Usuwanie {name}",
    "→ Trash: {p}": "→ Kosz: {p}",
    "no permission for {p}": "brak uprawnień do {p}",
    "✓  Uninstalled: {names}": "✓  Odinstalowano: {names}",
    "Could not uninstall:\n{names}": "Nie udało się odinstalować:\n{names}",
    "🔍  Looking for leftovers…": "🔍  Szukam pozostałości…",
    "Scan failed: {e}": "Błąd skanowania: {e}",
    "✨  No leftovers found — all clean!": "✨  Nie znaleziono żadnych pozostałości — czysto!",

    # ── cleanup page
    "System cleanup": "Sprzątanie systemu",
    "Remove what no program needs any more.": "Usuń to, czego żaden program już nie potrzebuje.",
    "Checking…": "Sprawdzam…",
    "Analysing packages and caches": "Analiza pakietów i pamięci podręcznej",
    "Check again": "Sprawdź ponownie",
    "  Clean up everything": "  Wyczyść wszystko",
    "Orphaned dependencies": "Osierocone zależności",
    "Packages installed automatically for programs that are gone.":
        "Pakiety zainstalowane automatycznie dla programów, których już nie ma.",
    "Remove": "Usuń",
    "Leftover configuration": "Pozostała konfiguracja",
    "Settings files in /etc left by packages removed without purge (“rc” state).":
        "Pliki ustawień w /etc po pakietach usuniętych bez opcji purge (stan „rc”).",
    "Clean": "Wyczyść",
    "Downloaded APT packages": "Pobrane pakiety APT",
    ".deb files in /var/cache/apt/archives — not needed after installation.":
        "Pliki .deb w /var/cache/apt/archives — po instalacji nie są już potrzebne.",
    "Leftovers of programs removed earlier": "Resztki po programach usuniętych dawniej",
    "Type the name of a program you removed in the past (e.g. spotify, zoom, discord) — I will find its files "
    "in configuration, caches, autostart and APT repositories.":
        "Wpisz nazwę programu, który kiedyś usunąłeś (np. spotify, zoom, discord) — znajdę jego pliki "
        "w konfiguracji, pamięci podręcznej, autostarcie i repozytoriach APT.",
    "Program name…": "Nazwa programu…",
    "  Search": "  Szukaj",
    "Show list": "Pokaż listę",
    "Hide list": "Ukryj listę",
    "None — all clean ✨": "Brak — wszystko czyste ✨",
    "Error": "Błąd",
    "You can free {size}": "Możesz odzyskać {size}",
    "All clean ✨": "Wszystko czyste ✨",
    "{orphans} · {rc} · {debs}": "{orphans} · {rc} · {debs}",
    "{packages} · {size}": "{packages} · {size}",
    "{files} · {size}": "{files} · {size}",
    "{n} orphaned packages will be removed. Review the list in the “Orphaned dependencies” card if you are "
    "not sure.\n\nContinue?":
        "Zostanie usuniętych {n} osieroconych pakietów. Przejrzyj listę w karcie „Osierocone zależności”, "
        "jeśli nie masz pewności.\n\nKontynuować?",
    "✨  All cleaned up!": "✨  Posprzątane!",
    "This name is too short or too generic to search for leftovers safely.":
        "Ta nazwa jest zbyt krótka albo zbyt ogólna, żeby bezpiecznie szukać po niej resztek.",

    # ── log page
    "History of uninstalled programs and deleted files.": "Historia odinstalowanych programów i usuniętych plików.",
    "Reload": "Odśwież",
    "Open folder": "Otwórz folder",
    "Clear log": "Wyczyść dziennik",
    "The log is empty.": "Dziennik jest pusty.",
    "Clear the whole log?": "Wyczyścić cały dziennik?",

    # ── settings page
    "Changes are saved immediately.": "Zmiany zapisują się od razu.",
    "Backup before uninstalling": "Kopia zapasowa przed odinstalowaniem",
    "Checking the file system…": "Sprawdzam system plików…",
    "Find leftovers after uninstalling": "Szukaj pozostałości po odinstalowaniu",
    "After every uninstall, show the files the program left in the system.":
        "Po każdym odinstalowaniu pokaż pliki, które program zostawił w systemie.",
    "Move files to the Trash": "Przenoś pliki do Kosza",
    "Leftovers from your home folder go to the Trash, where you can restore them in Dolphin.":
        "Pozostałości z katalogu domowego trafiają do Kosza, skąd można je przywrócić w Dolphinie.",
    "Show libraries and system packages": "Pokazuj biblioteki i pakiety systemowe",
    "By default the list shows only programs and tools. Turn on to see every APT package (advanced).":
        "Domyślnie lista zawiera tylko programy i narzędzia. Włącz, aby widzieć wszystkie pakiety APT "
        "(dla zaawansowanych).",

    # ── command line
    "{app} {ver} — uninstall programs together with their leftovers.\nUsage: linux-software-uninstaller [--version]":
        "{app} {ver} — odinstalowywanie programów razem z pozostałościami.\n"
        "Użycie: linux-software-uninstaller [--version]",
    "Run Linux Software Uninstaller as a normal user (without sudo).\n"
    "It will ask for the administrator password itself when needed.":
        "Uruchom Linux Software Uninstaller jako zwykły użytkownik (bez sudo).\n"
        "O hasło administratora zapyta sam, kiedy będzie potrzebne.",

    # ── widgets
    "Essential system package — cannot be removed.": "Pakiet niezbędny dla systemu — nie można go usunąć.",
    "Pick a program from the list\nto see its details": "Wybierz program z listy,\naby zobaczyć szczegóły",
    "Click the checkbox or double-click\nto select several programs at once.":
        "Kliknij kwadracik lub kliknij dwukrotnie,\naby zaznaczyć wiele programów naraz.",
    "🔒 Essential system package — it cannot be uninstalled.":
        "🔒 Pakiet niezbędny dla systemu — nie można go odinstalować.",
    "  Uninstall": "  Odinstaluj",
    " Find leftovers": " Szukaj resztek",
    "Show the files this program left in the system (without uninstalling)":
        "Pokaż pliki, które ten program zostawił w systemie (bez odinstalowania)",
    " Details": " Szczegóły",
    " Location": " Lokalizacja",
    "Version": "Wersja",
    "Size": "Rozmiar",
    "Installed": "Zainstalowano",
    "Identifier": "Identyfikator",
    "Installation": "Instalacja",
    "per-user": "użytkownika",
    "system-wide": "systemowa",
    "manual": "ręczna",
    "as a dependency": "jako zależność",

    # ── dialogs
    "Preparing…": "Przygotowywanie…",
    "Show details": "Pokaż szczegóły",
    "Hide details": "Ukryj szczegóły",
    "Close": "Zamknij",
    "Error: {e}\n": "Błąd: {e}\n",
    "Waiting for the administrator password…": "Czekam na hasło administratora…",
    "Cannot start: {p}\n": "Nie można uruchomić: {p}\n",
    "\n✗ Password entry cancelled or permission denied.\n": "\n✗ Anulowano podawanie hasła albo brak uprawnień.\n",
    "\n✗ Finished with an error (code {code}).\n": "\n✗ Zakończono z błędem (kod {code}).\n",
    "\n✓ Done.\n": "\n✓ Gotowe.\n",
    "Done!": "Gotowe!",
    "All operations completed successfully.": "Wszystkie operacje zakończyły się pomyślnie.",
    "Not everything worked": "Nie wszystko się udało",
    "Some operations failed — see the details below.": "Część operacji zakończyła się błędem — szczegóły poniżej.",
    "Confirm uninstall": "Potwierdź odinstalowanie",
    "Uninstall {programs}?": "Odinstalować {programs}?",
    "You will free about {size}. The programs' configuration and data will be removed with them.":
        "Zwolnisz około {size}. Konfiguracja i dane programów zostaną usunięte razem z nimi.",
    "<b>apt will also remove</b> (they depend on the removed ones):<br>{list}":
        "<b>Razem z nimi apt usunie też</b> (zależą od usuwanych):<br>{list}",
    "⚠ <b>Warning:</b> the removal includes packages important for the system: <b>{list}</b>. "
    "This may break the system or the KDE desktop.":
        "⚠ <b>Uwaga:</b> wśród usuwanych są pakiety ważne dla systemu: <b>{list}</b>. "
        "Może to uszkodzić system albo pulpit KDE.",
    "I understand the risk and want to continue": "Rozumiem ryzyko i chcę kontynuować",
    "Cancel": "Anuluj",
    "  Uninstall ({n})": "  Odinstaluj ({n})",
    "Found {leftovers} ({size})": "Znaleziono {leftovers} ({size})",
    "{sure} confirmed matches are selected. Check items marked “possible” before deleting them.":
        "Zaznaczyłem {sure} pewnych trafień. Elementy oznaczone jako „możliwe” sprawdź przed usunięciem.",
    "Path": "Ścieżka",
    "Type": "Rodzaj",
    "Certainty": "Pewność",
    "Your files — go to the Trash": "Twoje pliki — trafią do Kosza",
    "System files — need a password, deleted permanently": "Pliki systemowe — wymagają hasła, usuwane na stałe",
    "confirmed": "pewne",
    "possible": "możliwe",
    "Select confirmed": "Zaznacz pewne",
    "Select all": "Zaznacz wszystko",
    "Select none": "Odznacz",
    "Move your files to the Trash": "Twoje pliki przenoś do Kosza",
    "  Delete selected": "  Usuń zaznaczone",
    "Copy path": "Kopiuj ścieżkę",
    "Nothing selected.": "Nic nie zaznaczono.",
    "Delete {items} ({size})?": "Usunąć {items} ({size})?",
    "\n\n{n} of them are system files — you will be asked for a password.":
        "\n\n{n} z nich to pliki systemowe — zostaniesz poproszony o hasło.",
    "Delete leftovers": "Usuń pozostałości",
    "Deleting…": "Usuwanie…",
    "Error: {e}": "Błąd: {e}",
    "✓ Deleted: {n}.": "✓ Usunięto: {n}.",
    " Problems: ": " Problemy: ",
    "About {app}": "O programie {app}",
    "Version {v}": "Wersja {v}",
    "Uninstalls programs from APT, Flatpak, Snap, AppImage and /opt — together with their configuration "
    "and leftovers. An IObit Uninstaller–style tool for Debian and KDE Plasma.":
        "Odinstalowuje programy z APT, Flatpaka, Snapa, AppImage i /opt — razem z ich konfiguracją "
        "i pozostałościami. Odpowiednik IObit Uninstaller dla Debiana i KDE Plasma.",
}

CATALOGS = {"en": {}, "pl": PL}
