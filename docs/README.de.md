# Fenix A320 unter Linux

Dieses Community-Paket richtet die getesteten Fenix-Korrekturen für
**MSFS 2024 in Flightdeck** ein. Unterstützt wird ausschließlich der in
`bundle.json` festgelegte Xodus-Wine-Runner. Andere Wine-/Proton-Versionen und
MSFS 2020 werden vor Änderungen abgewiesen.

1. MSFS einmal mit Flightdeck starten und danach Simulator und Fenix schließen.
2. Das Linux-Installer-ZIP aus den GitHub-Releases entpacken und `./install.sh`
   starten. Alternativ Flightdeck → Add-ons → Fenix A320 öffnen.
3. Patch einrichten. Der Installer sichert das Windows-Profil, erstellt eine
   eigene Runner-Kopie und installiert bei Bedarf Microsoft .NET Framework 4.8
   sowie die geprüfte Geometrie-Abhängigkeit für die Routenanzeige.
4. Den offiziellen Fenix-Installer aus dem eigenen Fenix-Konto auswählen und
   die normale Installation einschließlich der angebotenen Voraussetzungen abschließen.
5. Fenix öffnen, anmelden und aktivieren. Anschließend Fenix samt Helfern schließen.
6. CPU-Anzeigen und Legacy-Readouts anwenden. Danach MSFS über Flightdeck starten.

Du benötigst die gekaufte Fenix-Lizenz, Python 3.10+, glibc 2.38+, GNU `cp`
und für das eigenständige Fenster Python Tk. Keine Root-Rechte nötig.

Getestet: Fenix 2.4.0.4720, MSFS 2024 1.8.16.0, Xodus Wine 11.0 und Hyprland.
Die Cockpitanzeigen wurden im laufenden Flugzeug geprüft. Ein vollständiger
Testflug steht noch aus. Wetterradar wird im verwendeten CPU-Modus nicht unterstützt.
Helligkeit und Flugmodi stellst du wie üblich im Cockpit ein.

„Wiederherstellen“ setzt Runner, Startskripte und das Windows-Profil auf den
Stand vor dem Patch zurück. Das neuere Profil bleibt als lokale Sicherung erhalten.
Außerhalb des Profils installierte Community-Inhalte werden nicht entfernt.
Bei einer unterbrochenen Einrichtung bleibt diese Funktion ebenfalls verfügbar.

Das Downloadpaket enthält keine Fenix-/Microsoft-Programme, Flugzeuge, Fonts,
Kontodaten oder privaten Profile. Es enthält den Installer, die Wine-Patches,
Wine-Binärmodule sowie deren vollständige Quellarchive und Bauanleitung.

Preview.3 ergänzt die Korrekturen für fehlende Routen und überlange Linien.
Unter X11/Xwayland werden die passenden Fenix-Hilfsfenster direkt im Wine-Treiber
vom Desktop ferngehalten. Updates von preview.1 und preview.2 behalten Flugzeug,
Einstellungen und den ursprünglichen Wiederherstellungspunkt.

Nach einem Neustart von Fenix Display frischt ein Helfer festgehaltene dunkle
MCDU-Bilder automatisch auf. Er stellt die Anzeigeeinstellung und Helligkeit
wieder her und sendet keine Seiten- oder Flugplaneingaben. Bei maximaler
Helligkeit ist dafür ein kurzer DIM/BRT-Wechsel nötig.
[Verhalten und Grenzen](mcdu-restart.md).
