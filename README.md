# Lichtregie

Eigenständige Lichtsteuerung für Home Assistant mit eigener Bedienoberfläche.

Home Assistant liefert die Verbindung zu Leuchten und Sensoren. Geplant,
geregelt und protokolliert wird in dieser Integration. Es werden **keine**
Automationen, Skripte, Blueprints oder Home-Assistant-Szenen benutzt und
keine Fremdintegration wie Adaptive Lighting.

## Was steht

| Baustein | Zustand |
|---|---|
| Lichttechnik — Dimmkurven, Mired, Planck-Ort, Betriebsgrenzen | fertig, 16 Tests |
| Prioritätsstapel mit Ebenen und Laufzeiten | fertig, 10 Tests |
| Gestennormalisierung über alle Tasterfabrikate | fertig, 19 Tests |
| Szenenvorschläge und Auflösung auf Stellwerte | fertig, 15 Tests |
| Tagesverlauf mit Sonnenstandsbindung | fertig, 10 Tests |
| Konstantlichtregelung mit Kalibrierfahrt | fertig, 12 Tests |
| Bindungen: Bedingungen, Haltedauer, Vorlagen | fertig, 24 Tests |
| Zeit- und Astro-Auslöser | fertig, 10 Tests |
| Anlage einlesen, Rollen vorschlagen, Sensoren bewerten | fertig, 20 Tests |
| Treiber mit Sammelbefehl, Begrenzung, Verifikation | fertig |
| Entscheidungsprotokoll | fertig |
| Engine: Bewegung, Bedienung, Fremdeingriff, Nachlauf, Dimmen | fertig |
| Panel: Leitstand, Zone, Szenen-Editor, Bindungseditor, Tagesverlauf, Protokoll | fertig |
| Zustandssicherung über Neustart | fertig, 3 Tests |
| Betriebsstunden und Energieauswertung | offen |
| Grundriss im Leitstand | offen |
| Simulation und Inbetriebnahme-Assistent | offen |
| Import bestehender Home-Assistant-Szenen | offen |

## Aufbau

```
custom_components/lichtregie/
├── core/          reine Logik, ohne Home Assistant, vollständig testbar
│   ├── photometry.py   Dimmkurven, Farbtemperatur, Betriebsgrenzen
│   ├── naming.py       Rollen- und Raumtyperkennung, Gruppenfilter
│   ├── model.py        Anlage · Zone · Lichtkreis · Leuchte · Szene · Bindung
│   ├── stack.py        Prioritätsstapel
│   ├── scenes.py       Vorschläge und Auflösung auf Stellbefehle
│   ├── bindings.py     Auslöser · Bedingung · Ebene · Haltedauer · Vorlagen
│   ├── daylight.py     Tagesverlaufskurven, an den Sonnenstand gebunden
│   ├── control.py      Konstantlichtregelung, PI-Regler, Kalibriermatrix
│   └── journal.py      Entscheidungsprotokoll
├── link/          Verbindung zu Home Assistant
│   ├── discovery.py    Anlage einlesen, Rollen raten, Sensoren bewerten
│   ├── driver.py       einziger Ausgang zu den Leuchten
│   └── gestures.py     Normalisierung aller Tasterfabrikate
├── api/websocket.py    Schnittstelle für das Panel
├── panel/              Oberfläche, ein ES-Modul ohne Build-Kette
├── engine.py           Taktgeber, Zonenlogik
└── store.py            Persistenz mit Fassungen und Rückkehr
```

## Dimmkurven

Der Sollwert ist empfundene Helligkeit, nicht Lichtstrom. Vier Kurven stehen
zur Wahl; Voreinstellung ist `log`.

| Kurve | Sollwert 50 % ergibt | Unterscheidbare Stufen bei 8 Bit |
|---|---|---|
| `log` (Standard) | 10 % Lichtstrom | 118 bei 1 % Minimalwert, 135 bei 3 % |
| `gamma` (2,2) | 22 % | 154 |
| `linear` | 50 % | 200 |
| `dali` (IEC 62386-102) | 3,1 % | 92 |

Die normative DALI-Kurve läuft über drei Dekaden von 0,1 % bis 100 %. Home
Assistant nimmt aber nur 8 Bit entgegen, und 1/255 sind bereits 0,39 % —
der untere Regelweg fällt zusammen. `log` legt dieselbe logarithmische
Charakteristik über den *nutzbaren* Bereich der Leuchte und trifft damit die
Wahrnehmung besser als Gamma 2,2: halbe empfundene Helligkeit entspricht nach
der Stevens-Potenzfunktion rund 12 % Lichtstrom.

## Tests

Laufen ohne Home Assistant:

```bash
python3 tests/run.py
```

## Einbau

1. Ordner `custom_components/lichtregie` in das Konfigurationsverzeichnis
   von Home Assistant kopieren.
2. Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Lichtregie*.
4. Die Anlage wird beim ersten Start eingelesen; die Oberfläche erscheint als
   **Lichtregie** in der Seitenleiste.

## Bauformen

Jede Leuchte trägt eine Bauform. Sie steht in der Lampenliste vor dem Namen,
im Kopf ihres Einstellungsdialogs, im Kontextmenü und in der Ausnahmeliste
des Szeneneditors — überall dort, wo man eine Leuchte wiedererkennen muss,
bevor man ihren Namen gelesen hat.

Siebzehn Zeichnungen: Deckenleuchte · Lichtpanel · Einbauspot · Strahler ·
Pendelleuchte · Stehleuchte · Tischleuchte · Wandleuchte · Lichtband ·
Indirekt · Unterbau · Spiegelleuchte · Nachtlicht · Kerze · Lichterkette ·
Außenleuchte · Sonstige.

Es sind eigene Strichzeichnungen, keine Emoji und keine fremde Icon-Schrift:
Emoji sehen auf jedem Gerät anders aus, lassen sich nicht einfärben und
zeigen nie die Leuchte, die im Raum wirklich hängt. Alle liegen im selben
24er-Raster, haben dieselbe Strichstärke und erben die Textfarbe — deshalb
färbt sich die gewählte Bauform im Dialog von allein bernstein. Aufbau ist
immer derselbe: erst der Baukörper, dann das Licht, das er abgibt. Genau
daran erkennt man sie auch in sechzehn Pixeln wieder.

Wer nichts wählt, bekommt die Bauform seiner hauptsächlichen Aufgabe:
Deckenlicht → Deckenleuchte, Arbeitslicht → Einbauspot, Stimmungslicht →
Stehleuchte, Akzentlicht → Strahler, Orientierung → Nachtlicht, Effekt →
Lichterkette. Früher gewählte Emoji werden beim Lesen auf die passende
Bauform abgebildet, die gespeicherte Konfiguration muss dafür nicht
angefasst werden.

## Bedienelemente

Alle Fabrikate werden auf ein gemeinsames Vokabular abgebildet: Tippen,
Doppeltippen, Dreifachtippen, Halten, Loslassen, langer Druck. Fehlende
Gesten rechnet die Software selbst aus.

| Quelle | Beispiel | Was ergänzt wird |
|---|---|---|
| Geräteauslöser (deCONZ, ZHA) | Busch-Jaeger RB01/RM01 | Doppel- und Dreifachtippen aus Einzelereignissen |
| Ereignis-Entität | Shelly-Eingänge | nichts, meldet alles selbst |
| Kontakteingang | Shelly i4 | alle Gesten aus Flankenlänge und -abstand |

## Bindungen

Eine Bindung verknüpft einen Auslöser mit einer Wirkung und besteht aus
fünf Teilen: **Auslöser** (Bewegung, Taste, Zeit, Sonnenstand),
**Bedingung** (Helligkeit, Zeitfenster, Wochentag, Betriebsart, Zustand),
**Ebene** im Prioritätsstapel, **Haltedauer** und **Danach**.

Sieben Haltemodelle: solange belegt · feste Dauer · bis Zone leer ·
bis Gegendruck · bis Zeitpunkt · bis andere Szene · unbegrenzt.

Vier Belegungsvorlagen für Taster: Klassisch, Durchtippen, Direktwahl,
Tag und Nacht.

## Konstantlichtregelung

Die Kalibrierfahrt läuft nachts und misst je Lichtkreis den Lux-Zuwachs am
Sensor der Zone. Danach ist der Eigenanteil des Kunstlichts bekannt und ein
PI-Regler kann auf den Sollwert regeln, ohne sich selbst zu verstärken.
Totband, Ratenbegrenzung unter einem Prozent je Sekunde und eine
Beruhigungszeit nach jedem Stellbefehl halten die Nachführung unsichtbar.

## Zustandssicherung

Der Laufzeitzustand — Anmeldungen im Stapel mit ihrer Restlaufzeit, der
Zustand jeder Zone, laufende Sperrzeiten — wird jede Minute und beim
Herunterfahren gesichert und beim Start zurückgeholt. Ohne das stünde nach
jedem Update jeder Raum wieder im Grundzustand. Ist die Sicherung älter als
eine Stunde, wird sie verworfen: was gestern Abend galt, gilt heute Morgen
nicht mehr.

Gespeichert wird die Restlaufzeit, nicht der Ablaufzeitpunkt — der beruht
auf der monotonen Uhr des Prozesses und ist nach einem Neustart wertlos.

## Gruppen sind keine Leuchten

Beim Einlesen werden Lichtgruppen aussortiert: Home-Assistant-Lichtgruppen
erkennt man am Attribut `entity_id`, Gruppen der Zigbee-Integration am
Gerätemodell. Beide steuern dieselben Leuchten wie die Einzeleinträge — als
eigener Lichtkreis geführt würde jede Lampe zweimal angesprochen, einmal
direkt und einmal über die Gruppe.

Leuchten, die den Raum nicht beleuchten — Kamera-Flutlicht, Statusanzeigen,
Gerätebeleuchtung — werden eingelesen, aber abgeschaltet angelegt, damit
keine Szene sie mitschaltet.
