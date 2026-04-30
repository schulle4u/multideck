# MultiDeck Audio Player

MultiDeck Audio Player ist eine App, mit der sich mehrere Audiodateien oder Internet-Streams gleichzeitig abspielen lassen. Der Player kann verwendet werden, um mehrere Audioquellen gleichzeitig zu überwachen oder komplexe Klanglandschaften zu erstellen. 

[![Hauptfenster des Programms](./multideck-screenshot.png)](./multideck-screenshot.png)

# Inhalt

[TOC]

## Funktionen im Überblick

* **Unabhängige Audio-Decks**
    * Lokale Audiodateien laden (MP3, OGG, WAV, FLAC)
    * Streamen von Internetquellen (Icecast/Shoutcast)
    * Abhören aller Soundkarteneingänge (Mikrofon, Line-in).
    * Für die Wiedergabe sollte FFmpeg auf dem System vorhanden sein.
    * **Individuelle Steuerung für Wiedergabe/Pause, Lautstärke, Balance, Stummschaltung und Loop**
    * Globale Steuerung für Wiedergabe/Pause für alle Decks
    * Benutzerdefinierte Deck-Bezeichnungen
    * Decks auf separaten Soundkarten wiedergeben (nur Multiroom-Modus)
* **Vier Betriebsmodi**
    * **Mixer-Modus**: Alle Decks werden gleichzeitig überlappend abgespielt
    * **Solo-Modus**: Es ist jeweils nur ein Deck zu hören.
    * **Automatikmodus**: Automatisches Umschalten zwischen Decks, unterstützt Crossfade
    * **Multiroom-Modus**: Wiedergabe jedes Decks auf einer eigenen Soundkarte
* **Projektverwaltung**
    * Speichern und Laden kompletter Deck-Konfigurationen (.mdap-Dateien)
    * M3U-Dateien importieren und exportieren
* **Master-Ausgangsrekorder**
    * Aufzeichnen der Audioausgabe als WAV-, MP3-, OGG- oder FLAC-Dateien
    * Echtzeitaufzeichnung mit Statusanzeige und optionalem Pre-Roll-Puffer
* **Kommandozeileninterface**
    * Lädt Projektdateien und spielt sie in Serverumgebungen oder auf eingebetteten Systemen ab.
    * Optionaler Silent-Modus für die Verwendung in Skripten.

## Installation

**Hinweis**: Diese Anleitung befasst sich nur mit der fertig kompilierten Programmversion. Die Installation und Ausführung des Quellcodes ist ausführlich in der Dokumentation des Projekt-Repositories beschrieben. 

### Systemvoraussetzungen

Erstellt und getestet wurde MultiDeck Audio Player unter Windows 11 sowie Debian Linux 13. Die Funktion auf älteren Betriebssystemen kann nicht garantiert werden. 

### Einrichtung

Der Player kann ohne besondere Installation durch Aufrufen der MultiDeck-Programmdatei im Hauptverzeichnis gestartet werden (`MultiDeck.exe` für Windows, `./MultiDeck` unter Linux). Im Programmpaket wird die Datei `config.ini.example` mitgeliefert, welche eine Beispielkonfiguration enthält. Um MultiDeck vollständig portabel zu machen, kann diese Datei als `config.ini` im Programmverzeichnis gespeichert werden. Andernfalls wird die Konfiguration in den Anwendungsdaten des aktuellen Benutzers hinterlegt, z. B. `%APPDATA%\MultiDeckAudioPlayer\` unter Windows. 

### Installation von FFmpeg

Für die Unterstützung weiterer Audioformate muss auf dem System eine FFmpeg-Installation vorhanden sein, da der Player sonst nur WAV-Dateien verarbeiten kann. 

#### Windows:

Sofern WinGet auf dem System vorhanden ist, genügt folgender Befehl in der Eingabeaufforderung: 

```
winget install Gyan.FFmpeg
```

Um FFmpeg manuell zu installieren: 

1. Download der FFmpeg-Binärdateien, zum Beispiel von https://www.gyan.dev/ffmpeg/builds/ (ausreichend ist ffmpeg-release-essentials.zip).
2. Archiv extrahieren.
3. `ffmpeg.exe` aus dem Bin-Verzeichnis in den Multideck-Ordner kopieren oder den Pfad zum Bin-Verzeichnis in die Path-Umgebungsvariable von Windows aufnehmen.

#### Linux und MacOS:

Hier ist FFmpeg in der Regel über die Paketquellen des Systems erhältlich. 

**Debian/Ubuntu**:

```bash
sudo apt update
sudo apt install ffmpeg;
```

**Fedora**:

```bash
sudo dnf install ffmpeg
```

**macOS**:

```bash
brew install ffmpeg
```

## Aufbau des Players

Das Programmfenster entspricht weitgehend einer Standardansicht, bestehend aus Menüleiste, Arbeitsbereich und Statusleiste. Die Menüleiste enthält alle Funktionen zur Steuerung des Programms. Im Arbeitsbereich befindet sich die Deckliste, die globale Playersteuerung für alle Decks sowie die individuellen Steuerelemente des gerade aktiven Decks. In der Statusleiste lassen sich Informationen zum aktiven Deck, dem Mixermodus und der Lautstärke ablesen. Nachfolgend wird näher auf die einzelnen Programmbereiche eingegangen. 

### Menüleiste

#### Datei

* Neues Projekt (Ctrl+N): Erstellt ein leeres Projekt.
* Projekt öffnen (Ctrl+O): Lädt eine bestehende Projektdatei (`*.mdap`) in den Player.
* Projekt speichern (Ctrl+S): Einstellungen des aktuellen Projekts speichern.
* Projekt speichern unter (Ctrl+Shift+S): Projekt unter einem anderen Namen abspeichern.
* M3U-Playliste importieren (Ctrl+I): Importiert eine M3U-Playliste mit Audiodateien oder URLs und verteilt sie auf die freien Decks. Wenn keine freien Decks mehr zur Verfügung stehen, werden die Einträge der Playliste ignoriert.
* M3U-Playliste exportieren (Ctrl+E): Exportiert die in den Decks geladenen Dateien und URLs als M3U- oder M3U8-Playliste. 
* Letzte Dateien: Enthält eine Liste der zuletzt geöffneten Dateien. Hierbei handelt es sich jedoch um die geladenen Audiodateien, nicht um die Projektdateien. Die Liste kann bei Bedarf auch gelöscht werden.
* Beenden (Alt+F4): Beendet das Programm.

#### Deck

* Datei laden (Ctrl+F): Lädt eine Audiodatei in das gewählte Deck. 
* URL laden (Ctrl+U): Öffnet einen Internetstream im gewählten Deck.
* Soundkarteneingang laden (Ctrl+D): Ermöglicht die Wiedergabe einer an den Computer angeschlossenen Audioquelle (Mikrofon, Line). 
* Introdatei festlegen: Ermöglicht das festlegen einer Intro-Audiodatei, welche beim Umschalten auf das Deck abgespielt wird.
* Introdatei löschen: Entfernt die zuvor festgelegte Intro-Audiodatei aus dem Deck.
* Deck umbenennen (F2): Erlaubt das Hinterlegen eines benutzerdefinierten Decknamens. 
* Deck entladen (Del/Entf): Entfernt die auf dem gewählten Deck geladene Datei.
* Deckaufnahme starten (Ctrl+Shift+R): Ermöglicht eine individuelle Deckaufnahme, unabhängig vom gewählten Betriebsmodus. 

#### Wiedergabe

* Wiedergabe/Pause aller Decks (Ctrl+P): Schaltet die Wiedergabe auf allen geladenen Decks um.
* Alle Decks stoppen (CTRL+Punkt): Beendet die Wiedergabe auf allen geladenen Decks, und setzt die Zeitanzeige zurück.
* Aktives Deck abspielen (CTRL+Shift+P): Spielt nur das in der Deckliste ausgewählte Deck ab. 
* Aktives Deck stoppen (CTRL+Shift+Punkt): Beendet nur die Wiedergabe auf dem in der Deckliste ausgewählten Deck.
* Stummschaltung umschalten (Ctrl+M): Schaltet das aktive Deck lautlos.
* Wiederholung umschalten (Ctrl+L): Schaltet die Loopwiedergabe für lokale Audiodateien ein oder aus.
* Zu Zeitmarke springen (Ctrl+J): Erlaubt das Ansteuern einer bestimmten Zeitmarke im Format `HH:MM:SS`.

#### Ansicht

* Statusleiste (Ctrl+T): Schaltet die Anzeige der Statusleiste um.
* Pegelanzeige: Aktiviert oder deaktiviert die Anzeige des Lautstärkepegels im aktuellen Deck.
* Theme wechseln (Ctrl+Shift+T): Schaltet die Programmoberfläche zwischen hellem und dunklem Theme um.

#### Werkzeuge

* Aufnahme starten/beenden (Ctrl+R): Startet die Live-Aufnahme des Ausgabemixers. Wenn in den Programmoptionen kein Ausgabeverzeichnis festgelegt wurde, fragt das Programm vor dem Starten der Aufnahme nach dem Verzeichnis zum Speichern der Datei. 
* Livestream starten/stoppen (F8): Startet den Livestream, um das Mixersignal an einen Icecast-Server zu senden. Zuvor müssen die Zugangsdaten in den Programmeinstellungen hinterlegt werden. 
* Audioeffekte (Ctrl+Shift+E): Öffnet ein Fenster zum Konfigurieren von Audioeffekten und VST-Plugins. 
* Optionen (Ctrl+Shift+O): Öffnet die Programmeinstellungen.

#### Hilfe

* Dokumentation (F1): Öffnet diese Hilfedatei. Ist keine Hilfe vorhanden, wird stattdessen die Webseite des Programms geladen.
* Webseite öffnen (Ctrl+F1): Öffnet die Webseite des Programms.
* Über: Enthält Kurzinformationen zum Programm.

### Der Arbeitsbereich

Im linken Bereich des Fensters befinden sich die Auswahl des Betriebsmodus, die globale Wiedergabesteuerung sowie die Deckliste. Diese Bereiche entsprechen dem Master-Mix und der Spurliste einer digitalen Audio-Workstation (DAW). Der rechte Bereich enthält die Steuerelemente für das jeweils aktive Deck. 

#### Betriebsmodi

* Mixermodus (F3): Alle geladenen Decks werden gleichzeitig hörbar abgespielt. 
* Solomodus (F4): Es wird nur das gerade aktive Deck wiedergegeben.
* Automatikmodus (F5): Wie im Solomodus wird nur das aktive Deck abgespielt, jedoch schaltet der Player in Zeitintervallen zwischen den geladenen Decks um.
* Multiroom-Modus (F7): Dies ist ein spezieller Mixermodus, der jedem Deck erlaubt seine Ausgabe an eine andere Soundkarte zu senden. Die Ausgabe kann über das Kontextmenü des Decks konfiguriert werden und ist sofort nach dem Umschalten wirksam.

#### Deckliste (F6)

Die Deckliste dient zur Auswahl des aktiven Decks. Um das Deck zu wechseln, muss es lediglich mit den Pfeiltasten oder der Maus ausgewählt werden. Neben dem Decknamen wird der geladene Inhalt angezeigt sowie der Aufnahmestatus und das gewählte Ausgabegerät. Über das Kontextmenü stehen  die Funktionen aus dem Deckmenü sowie zum Ändern des Ausgabegeräts zur Verfügung: 

#### Steuerung für aktives Deck

* Wiedergabesteuerung: Abspielen/Pause und Stopp
* Menü: Öffnet das Kontextmenü des gewählten Decks.
* Lautstärke (Ctrl+Hoch/Runter): Regelt die Lautstärke des aktiven Decks.
* Balance (Ctrl+Links/Rechts): Regelt die Balance des aktiven Decks.
* Stumm (Ctrl+M): Schaltet das Deck lautlos.
* Wiederholen (Ctrl+L): Schaltet die Loopwiedergabe für lokale Audiodateien ein oder aus.
* Position (Alt+Links/Rechts): Ermöglicht das Spulen in lokalen Audiodateien. Mittels Alt+Shift+Links/Rechts kann in 30-Sekunden-Sprüngen navigiert werden.
* Pegel: Enthält eine visuelle Darstellung des Lautstärkepegels sowie die Angabe in dB. 

### Statusleiste

Die Statusleiste ist in 3 Bereiche aufgeteilt: 

* Erster Bereich links: Enthält Informationen zum geladenen Projekt, dem aktiven Deck oder zum Aufnahmestatus, des Weiteren die Lautstärke des aktiven Decks. Je nach ausgeführter Aktion ändert sich die Anzeige. 
* Zweiter Bereich, mittig: Informationen zum ausgewählten Betriebsmodus (Mixer, Solo oder Automatik).
* Dritter Bereich, rechts: Gibt die aktuelle Masterlautstärke an. 

## Programmoptionen

Die Optionen sind über das Menü Werkzeuge oder mittels Ctrl+Shift+O aufrufbar. Über die Kategorieliste können die einzelnen Einstellungsseiten angewählt werden. Die Schaltfläche „OK” speichert sämtliche Einstellungen und schließt den Dialog, während die Übernehmen-Schaltfläche nur die Einstellungen der aktuellen Kategorie speichert und den Dialog geöffnet lässt. Einige Optionen erfordern möglicherweise einen Neustart des Programms, worauf beim Speichern hingewiesen wird. 

### Allgemein

* Sprache: Legt die Programmsprache fest.
* Anzahl der Decks: Die Anzahl sichtbarer Decks im Hauptfenster.
* Theme: Legt das Standard-Aussehen des Programms fest.

### Audio

* Ausgabegerät: Zeigt die im System installierten Wiedergabegeräte an. Neben dem Gerätenamen wird die verwendete Host-API angegeben (MME, Directsound usw.).
* Puffergröße: Muss normalerweise nur bei Wiedergabeproblemen angepasst werden, Standard ist 2048. 
* Abtastrate: Die zu verwendende Abtastrate (Samplingrate) des Wiedergabegeräts.

### Automatisierung

* Umschaltintervall (Sekunden): Die Zeitdauer, nach welcher der Automatisierungsmodus zum nächsten Deck umschalten soll.
* Überblendung aktivieren: Ermöglicht einen sanften Übergang zwischen Deckumschaltungen.
* Überblendungsdauer: Dauer der Überblendung in Sekunden.
* Pegelbasierte Umschaltung aktivieren: Ist diese Option aktiviert, schaltet der Automatikmodus um, sobald der Lautstärkepegel auf einem Deck die nachfolgend eingestellte Schwelle überschreitet.
* Schwellenwert (dB): Angabe des Schwellenwertes zur automatischen Pegelumschaltung.
* Hysterese (dB): Dieser Wert gibt der Umschaltung einen gewissen Spielraum, um allzu schnelles Umschalten zwischen den Decks zu verhindern. Berechnung: Schwellenwert Minus Hysterese.
* Haltezeit (Sekunden): Kontrolliert nach erneutem Abfallen des Pegels die Mindestverweildauer auf dem Deck, bevor weitergeschaltet wird.

### Aufnahme

* Format: Das bevorzugte Audioformat für Aufnahmen Wav. MP3, OGG oder FLAC. 
* Bitrate (nur MP3 und OGG): Die zu verwendende Komprimierungsbitrate. 
* Bittiefe (nur WAV): Die für WAV-Dateien zu verwendende Bittiefe.
* Vorabpuffer (Sekunden): Ermöglicht es, die Aufnahme vor dem eigentlichen Start für bis zu 2 Minuten (120 Sekunden) vorab im Arbeitsspeicher zu halten. Die so gepufferte Aufnahme wird beim Starten der Aufnahme vorangestellt. 
* Ausgabeverzeichnis: Legt den Standardordner für Aufnahmen fest.

### Streaming

* Server: Der für den Livestream zu verwendende Hostname (ohne voranstehendes http).
* Port: Der Port des Icecast-Servers.
* Einhängepunkt (häufig auch Mountpoint): Der Pfad zum Livestream-Mointpoint, beginnend mit einem Schrägstrich. 
* Benutzerdaten: Die Zugangsdaten für den Stream im Format Benutzername:Passwort.
* Codec: Streaming-Codec, MP3 oder OGG Vorbis.
* Bitrate: Qualität des Livestreams.
* Streamname, Beschreibung, Genre und Website-URL: Metadaten des Streams.
* Öffentlicher Stream: Listet den Stream in öffentlichen Verzeichnissen, sofern diese auf dem Icecast-Server aktiviert sind.
* Verbindung bei Programmstart: Aktiviert den Livestream beim Starten des Programms.
* Automatisch neu verbinden bei Verbindungsabbruch: Baut den Stream nach Möglichkeit neu auf, wenn die Verbindung unterbrochen wird.
* Wartezeit für Neuverbindung (Sekunden): Zeitdauer, bis ein neuer Verbindungsversuch gestartet werden soll.

### Sprachausgabe

* Sprachausgabenansagen einschalten: Aktiviert durch Tastenkombinationen ausgelöste Statusereignisse sowie die Ansage des aktiven Decks im Automatikmodus.
* Treiber: Die zu verwendende TTS-Engine.
* Stimme: Stimme der Sprachausgabe, abhängig von der TTS-Engine.
* Sprechgeschwindigkeit: Wörter pro Minute, 0 für Sprachausgabenstandard.
* Lautstärke in Prozent, -1 für Sprachausgabenstandard.

### Erweiterte Konfiguration

Einige spezielle Optionen können nur über die Datei `config.ini` im Programmverzeichnis oder in den Multideck-Anwendungsdaten angepasst werden. 

Im bereich `[UI]`: 

* `deck_list_focus`: Legt fest, ob MultiDeck beim Starten den Tastaturfokus auf die Deckliste legen soll (Standard: True). 
* `window_width` und `window_height`: Speichert beim Beenden des Programms die aktuellen Fenstergrößen und muss normalerweise nicht manuell angepasst werden.

Zusätzliche Optionen im Bereich `[Streaming]`:

* `queue_blocks`: Größe des internen Audio-Puffers für den Livestream. Ein höherer Wert kann für mehr Robustheit bei Hhängenden Streams sorgen, erhöht aber auch die Latenz (Standard: 128).
* `writer_poll_ms`: Wie oft der Writer-Thread auf neue Audioblöcke wartet. Kleiner  Wert sorgt für reaktiveres Verhalten, ein größerer Wert verursacht mehr Trägheit (Standard: 100).
* `ffmpeg_close_timeout`: Wie lange beim Stoppen auf FFmpeg gewartet wird, bevor der Prozess hart beendet wird (Standard: 5.0).
* `ffmpeg_loglevel`: FFmpeg-Protokollstufe, z. B. quiet, error, warning, info (Standard: error).

`[Recent]`: 

* `max_recent_items`: Legt die Anzahl der zuletzt geöffneten Dateien fest (Standard: 10).

`[Logging]`: 

* `level`: Die Protokollstufe des Programms, z. B. DEBUG, INFO, WARNING, ERROR, CRITICAL (Standard: `INFO`).

## Audioeffekte

Über das Werkzeuge-Menü oder mit der Tastenkombination Ctrl+Shift+E sind einige Audioeffekte für den Mastermix oder jedes Deck einzeln verfügbar. Zunächst muss hierfür in der Effektkettenliste das gewünschte Deck oder der Mastermix gewählt werden. Die Effekte sind pro Deck in zwei Seiten unterteilt: Integrierte Effekte und VST-Plugins. 

### Integrierte Effekte

* Effekte für Master/Deck einschalten: Diese Option aktiviert die jeweilige Effektkette und muss auch aktiviert sein, wenn VST-Effekte verwendet werden. 
* Hall: Fügt dem Audio mehr Räumlichkeit hinzu. Parameter: Raumgröße, Dämpfung, Wet- und Dry-Pegel, Breite.
* Echo: Zeit, Feedback und Mix sind konfigurierbar.
* Equalizer: Ein einfacher Dreiband-Equalizer mit Bass-, Mitten- und Höhenregelung. 
* Chorus: Enthält Parameter für Wert, Stärke und Mix.
* Kompressor: Ein einfacher Dynamikkompressor. Der Schwellenwert, das Verhältnis sowie Ansprech- und Abklingzeit sind konfigurierbar.
* Limiter: Ein Begrenzer mit integriertem Kompressor, Schwellenwert und Abklingzeit sind konfigurierbar.
* Verstärkung: Erhöht oder dämpft die Lautstärke von -24 bis +24 dB. 

### VST-Plugins

**Warnung**: Die Verwendung von VST-Effekten ist noch sehr fehleranfällig und sollte daher mit Vorsicht verwendet werden. 

Auf dieser Seite können VST-Plug-ins geladen werden. Sie sind in einer Liste aufgeführt und lassen sich beliebig in der Effektkette verschieben. Es werden nur VST3-Effekte unterstützt. Die Parameter des gewählten Plug-ins lassen sich im Panel in der unteren Bildschirmhälfte anpassen. Um das native GUI des Plugins aufzurufen, kann die Schaltfläche „Editor öffnen” verwendet werden. 

## Projektdateien

Um nicht bei jedem Öffnen des Players alle Decks manuell neu laden zu müssen, kann MultiDeck Audio Player die Deck- und Mixerkonfiguration in Projektdateien („*.mdap“) hinterlegen, und diese über den Dateimanager oder aus dem Programm heraus öffnen. Auch einige Programmeinstellungen lassen sich projektspezifisch abspeichern und werden unabhängig von den in den Optionen festgelegten Einstellungen beim Öffnen der Projektdatei angewendet. Folgende Einstellungen werden übernommen: 

* Betriebsmodus: Mixer, Solo oder Automatik
* Masterlautstärke
* Übergangseinstellungen für den Automatikmodus
* Deck-Inhalte: Name, geladene Datei/URL/Soundeingang, Lautstärke/Balance, Stummschaltung und Wiederholung.
* Geladene Effekte mit allen Parametern

Veränderungen im Mixer sowie der Deckliste werden vom Player automatisch erkannt und durch einen Stern in der Titelleiste als nicht gespeicherte Änderung am Projekt gekennzeichnet. Beim Schließen des Players fragt das Programm, ob die Änderungen übernommen werden sollen. Die angewendeten Effekte müssen momentan manuell gespeichert werden, hierzu reicht aber das Auslösen der Speicherfunktion im Datei-Menü (Ctrl+S). 

## Weiterführende Links

* [Quellcode auf GitHub](https://github.com/schulle4u/multideck)
