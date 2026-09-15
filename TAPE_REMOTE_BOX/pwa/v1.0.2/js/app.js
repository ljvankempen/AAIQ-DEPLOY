/**
 * AAIQ TAPE Remote PWA â€” Application Core
 * Connects to AAIQ Relay Box Pico / TAPERC Public Gateway (/api/v1/...)
 */

// Service Worker Registration
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch((err) => {
    console.debug('ServiceWorker registration skipped:', err);
  });
}

// =============================================================================
// CENTRAL I18N / MULTILINGUAL ENGINE
// =============================================================================
const I18N = {
  en: {
    flag: "ðŸ‡¬ðŸ‡§",
    code: "EN",
    name: "English",
    install_app: "Install App",
    power: "Power",
    menu: "Menu",
    ota_badge_title: "Firmware Update",
    menu_install: "Install App",
    menu_rgb: "RGB LED & Brightness",
    menu_icons: "Icon Guide",
    menu_ota: "Firmware Update",
    menu_diagnostics: "Diagnostics",
    menu_info: "Info",
    rgb_title: "RGB LED Status & Brightness",
    rgb_brightness: "LED Brightness",
    rgb_guide_title: "Status colors and meaning:",
    rgb_green: "<b>Green (Solid):</b> Online & Ready / Power ON / PLAY",
    rgb_red: "<b>Red (Solid):</b> Standby / Power OFF / RECORD",
    rgb_blue: "<b>Blue (Solid):</b> STOP transport",
    rgb_orange: "<b>Orange (Solid):</b> PAUSE transport",
    rgb_cyan: "<b>Cyan (Solid):</b> Fast Forward (FF)",
    rgb_purple: "<b>Purple (Solid):</b> Rewind (REW) / Firmware Update (OTA)",
    rgb_yellow: "<b>Yellow (Solid):</b> Booting / Wi-Fi connecting / Test mode",
    rgb_blink_red: "<b>Red blinking (500ms):</b> Error / Fault",
    rgb_blink_blue: "<b>Blue blinking (500ms):</b> Wi-Fi Setup Mode (Access Point)",
    rgb_white: "<b>White flash (150ms):</b> Command received",
    close: "Close",
    icon_title: "PWA Icon Guide",
    icon_sec_header: "Header & Controls",
    icon_power_title: "Power",
    icon_power_desc: "Main switch (Relay 8 - Power ON / Standby)",
    icon_ota_title: "OTA Badge",
    icon_ota_desc: "Firmware status (Up-to-date, Update available, Server offline)",
    icon_install_title: "Install App",
    icon_install_desc: "Install PWA on home screen or desktop",
    icon_menu_title: "Menu",
    icon_menu_desc: "Access settings, LED dimmer, icons and diagnostics",
    icon_sec_transport: "Transport Functions",
    icon_play_title: "PLAY (R1)",
    icon_play_desc: "Start tape playback",
    icon_stop_title: "STOP (R2)",
    icon_stop_desc: "Stop tape transport",
    icon_rec_title: "RECORD (R3)",
    icon_rec_desc: "Activate recording mode",
    icon_pause_title: "PAUSE (R4)",
    icon_pause_desc: "Pause / pause recording",
    icon_ff_title: "FF (R5)",
    icon_ff_desc: "Fast forward tape",
    icon_rew_title: "REW (R6)",
    icon_rew_desc: "Fast rewind tape",
    icon_sec_visual: "Visual Indications",
    icon_reels_title: "Spinning Reels",
    icon_reels_desc: "Visual feedback of direction and speed",
    info_title: "Info",
    info_app: "App",
    info_version: "Version",
    info_device: "Device",
    info_firmware: "Firmware",
    info_gateway: "Gateway",
    btn_rgb: "RGB LED",
    btn_icons: "Icons",
    ota_title: "Firmware Update (OTA)",
    ota_current_ver: "Current Version",
    ota_avail_ver: "Available Version",
    ota_status: "Status",
    ota_status_checking: "Checking...",
    ota_btn_check: "Check",
    ota_btn_install: "Install Now",
    ota_progress: "Downloading firmware securely and verifying SHA-256...",
    ota_update_available: "Newer version v{ver} available!",
    ota_up_to_date: "Firmware is up-to-date.",
    ota_unreachable: "Device / Server unreachable.",
    ota_downloading: "Downloading firmware...",
    ota_installing: "Installing firmware...",
    ota_rebooting: "Restarting Relay Box...",
    ota_ready: "Ready",
    ota_error_check: "Error checking update",
    ota_none: "None",
    ota_confirm_install: "Are you sure you want to install the latest firmware?\nThe Relay Box will reboot automatically after installation.",
    ota_install_success: "Installation completed! Relay Box rebooting now...",
    ota_install_failed: "Installation failed: ",
    ota_install_error: "Error during installation: ",
    ios_title: "Install App",
    ios_btn_ok: "Understood",
    ios_safari_title: "Open in Safari and choose Share â†’ Add to Home Screen.",
    ios_safari_1: "1. Tap the <b>Share button</b> in Safari.",
    ios_safari_2: "2. Scroll down and tap <b>Add to Home Screen</b> (+).",
    ios_safari_3: "3. Tap <b>Add</b> in the top right.",
    ios_ff_title: "Firefox on iOS",
    ios_ff_desc: "Firefox on iOS does not support PWA installation directly.<br>1. Tap the menu in Firefox (<b>â‹¯</b>).<br>2. Choose <b>Open in Safari</b>.<br>3. In Safari, tap <b>Share</b> and choose <b>Add to Home Screen</b> (+).",
    ios_chrome_title: "Chrome on iOS",
    ios_chrome_desc: "Chrome on iOS does not support PWA installation directly.<br>1. Tap the <b>Share icon</b> in the address bar or menu.<br>2. Tap <b>Add to Home Screen</b> (or open in Safari &rarr; Share &rarr; Add to Home Screen).<br>3. Tap <b>Add</b>.",
    ios_other_desc: "This browser on iOS does not support direct PWA installation. Open this page in Safari to add TAPE to your home screen.",
    mac_safari_title: "Safari Web App on macOS",
    mac_safari_desc: "1. Open the Safari menu at the top.<br>2. Choose <b>File &rarr; Add to Dock...</b>.<br>3. Click <b>Add</b> to launch the app directly from your Dock.",
    desktop_ff_title: "Firefox Desktop",
    desktop_ff_desc: "Firefox supports this page as a fast Web App.<br>â€¢ Press <b>Ctrl + D</b> to create a bookmark.<br>â€¢ Or drag the lock icon from the address bar to your desktop.",
    webapp_title: "Web App Installation",
    webapp_desc: "â€¢ <b>Chrome / Edge:</b> Click the install icon in the address bar.<br>â€¢ <b>Mobile:</b> Choose <i>Add to Home screen</i> in your browser menu."
  },
  fr: {
    flag: "ðŸ‡«ðŸ‡·",
    code: "FR",
    name: "FranÃ§ais",
    install_app: "Installer l'app",
    power: "Alimentation",
    menu: "Menu",
    ota_badge_title: "Mise Ã  jour du firmware",
    menu_install: "Installer l'application",
    menu_rgb: "LED RVB & LuminositÃ©",
    menu_icons: "Signification des icÃ´nes",
    menu_ota: "Mise Ã  jour du firmware",
    menu_diagnostics: "Diagnostic",
    menu_info: "Infos",
    rgb_title: "Statut & LuminositÃ© LED RVB",
    rgb_brightness: "LuminositÃ© LED",
    rgb_guide_title: "Couleurs d'Ã©tat et signification :",
    rgb_green: "<b>Vert (Fixe) :</b> En ligne & PrÃªt / Marche / PLAY",
    rgb_red: "<b>Rouge (Fixe) :</b> Veille / ArrÃªt / RECORD",
    rgb_blue: "<b>Bleu (Fixe) :</b> STOP transport",
    rgb_orange: "<b>Orange (Fixe) :</b> PAUSE transport",
    rgb_cyan: "<b>Cyan (Fixe) :</b> Avance rapide (FF)",
    rgb_purple: "<b>Violet (Fixe) :</b> Rembobinage (REW) / Mise Ã  jour (OTA)",
    rgb_yellow: "<b>Jaune (Fixe) :</b> DÃ©marrage / Connexion Wi-Fi / Mode test",
    rgb_blink_red: "<b>Rouge clignotant (500ms) :</b> Erreur / DÃ©faillance",
    rgb_blink_blue: "<b>Bleu clignotant (500ms) :</b> Mode configuration Wi-Fi (Point d'accÃ¨s)",
    rgb_white: "<b>Flash blanc (150ms) :</b> Commande reÃ§ue",
    close: "Fermer",
    icon_title: "Signification des icÃ´nes PWA",
    icon_sec_header: "En-tÃªte & ContrÃ´les",
    icon_power_title: "Alimentation",
    icon_power_desc: "Interrupteur principal (Relais 8 - Marche / Veille)",
    icon_ota_title: "Badge OTA",
    icon_ota_desc: "Statut du firmware (Ã€ jour, Mise Ã  jour disponible, Serveur hors ligne)",
    icon_install_title: "Installer l'app",
    icon_install_desc: "Installer la PWA sur l'Ã©cran d'accueil ou le bureau",
    icon_menu_title: "Menu",
    icon_menu_desc: "AccÃ¨s aux paramÃ¨tres, variateur LED, icÃ´nes et diagnostic",
    icon_sec_transport: "Fonctions de transport",
    icon_play_title: "PLAY (R1)",
    icon_play_desc: "DÃ©marrer la lecture de la bande",
    icon_stop_title: "STOP (R2)",
    icon_stop_desc: "ArrÃªter le transport de la bande",
    icon_rec_title: "RECORD (R3)",
    icon_rec_desc: "Activer le mode enregistrement",
    icon_pause_title: "PAUSE (R4)",
    icon_pause_desc: "Pause / pause enregistrement",
    icon_ff_title: "FF (R5)",
    icon_ff_desc: "Avance rapide de la bande",
    icon_rew_title: "REW (R6)",
    icon_rew_desc: "Rembobinage rapide de la bande",
    icon_sec_visual: "Indications visuelles",
    icon_reels_title: "Bobines en rotation",
    icon_reels_desc: "Retour visuel de la direction et de la vitesse",
    info_title: "Infos",
    info_app: "Application",
    info_version: "Version",
    info_device: "Appareil",
    info_firmware: "Firmware",
    info_gateway: "Passerelle",
    btn_rgb: "LED RVB",
    btn_icons: "IcÃ´nes",
    ota_title: "Mise Ã  jour du firmware (OTA)",
    ota_current_ver: "Version actuelle",
    ota_avail_ver: "Version disponible",
    ota_status: "Statut",
    ota_status_checking: "VÃ©rification...",
    ota_btn_check: "VÃ©rifier",
    ota_btn_install: "Installer maintenant",
    ota_progress: "TÃ©lÃ©chargement sÃ©curisÃ© du firmware et vÃ©rification SHA-256...",
    ota_update_available: "Nouvelle version v{ver} disponible !",
    ota_up_to_date: "Le firmware est Ã  jour.",
    ota_unreachable: "Appareil / Serveur injoignable.",
    ota_downloading: "TÃ©lÃ©chargement du firmware...",
    ota_installing: "Installation du firmware...",
    ota_rebooting: "RedÃ©marrage de la Relay Box...",
    ota_ready: "PrÃªt",
    ota_error_check: "Erreur lors de la vÃ©rification",
    ota_none: "Aucune",
    ota_confirm_install: "Voulez-vous vraiment installer le dernier firmware ?\nLa Relay Box redÃ©marrera automatiquement aprÃ¨s l'installation.",
    ota_install_success: "Installation terminÃ©e ! La Relay Box redÃ©marre...",
    ota_install_failed: "Ã‰chec de l'installation : ",
    ota_install_error: "Erreur lors de l'installation : ",
    ios_title: "Installer l'application",
    ios_btn_ok: "Compris",
    ios_safari_title: "Ouvrez dans Safari et choisissez Partager â†’ Sur l'Ã©cran d'accueil.",
    ios_safari_1: "1. Touchez le bouton <b>Partager</b> dans Safari.",
    ios_safari_2: "2. Faites dÃ©filer vers le bas et touchez <b>Sur l'Ã©cran d'accueil</b> (+).",
    ios_safari_3: "3. Touchez <b>Ajouter</b> en haut Ã  droite.",
    ios_ff_title: "Firefox sur iOS",
    ios_ff_desc: "Firefox sur iOS ne prend pas en charge l'installation PWA directe.<br>1. Touchez le menu dans Firefox (<b>â‹¯</b>).<br>2. Choisissez <b>Ouvrir dans Safari</b>.<br>3. Dans Safari, touchez <b>Partager</b> puis <b>Sur l'Ã©cran d'accueil</b> (+).",
    ios_chrome_title: "Chrome sur iOS",
    ios_chrome_desc: "Chrome sur iOS ne prend pas en charge l'installation PWA directe.<br>1. Touchez l'icÃ´ne <b>Partager</b>.<br>2. Touchez <b>Sur l'Ã©cran d'accueil</b> (ou ouvrez dans Safari &rarr; Partager &rarr; Sur l'Ã©cran d'accueil).<br>3. Touchez <b>Ajouter</b>.",
    ios_other_desc: "Ce navigateur sur iOS ne supporte pas l'installation PWA directe. Ouvrez cette page dans Safari pour ajouter TAPE Ã  votre Ã©cran d'accueil.",
    mac_safari_title: "Application Web Safari sur macOS",
    mac_safari_desc: "1. Ouvrez le menu Safari en haut.<br>2. Choisissez <b>Fichier &rarr; Ajouter au Dock...</b>.<br>3. Cliquez sur <b>Ajouter</b> pour lancer l'application directement depuis votre Dock.",
    desktop_ff_title: "Firefox pour Bureau",
    desktop_ff_desc: "Firefox prend en charge cette page comme application web rapide.<br>â€¢ Appuyez sur <b>Ctrl + D</b> pour crÃ©er un marque-page.<br>â€¢ Ou glissez l'icÃ´ne du cadenas vers votre bureau.",
    webapp_title: "Installation de l'application Web",
    webapp_desc: "â€¢ <b>Chrome / Edge :</b> Cliquez sur l'icÃ´ne d'installation dans la barre d'adresse.<br>â€¢ <b>Mobile :</b> Choisissez <i>Ajouter Ã  l'Ã©cran d'accueil</i> dans le menu du navigateur."
  },
  de: {
    flag: "ðŸ‡©ðŸ‡ª",
    code: "DE",
    name: "Deutsch",
    install_app: "App installieren",
    power: "Ein/Aus",
    menu: "MenÃ¼",
    ota_badge_title: "Firmware-Update",
    menu_install: "App installieren",
    menu_rgb: "RGB-LED & Helligkeit",
    menu_icons: "Bedeutung der Symbole",
    menu_ota: "Firmware-Update",
    menu_diagnostics: "Diagnose",
    menu_info: "Info",
    rgb_title: "RGB-LED-Status & Helligkeit",
    rgb_brightness: "LED-Helligkeit",
    rgb_guide_title: "Statusfarben und Bedeutung:",
    rgb_green: "<b>GrÃ¼n (Dauerhaft):</b> Online & Bereit / Strom EIN / PLAY",
    rgb_red: "<b>Rot (Dauerhaft):</b> Standby / Strom AUS / RECORD",
    rgb_blue: "<b>Blau (Dauerhaft):</b> STOP Bandtransport",
    rgb_orange: "<b>Orange (Dauerhaft):</b> PAUSE Bandtransport",
    rgb_cyan: "<b>Cyan (Dauerhaft):</b> Schnellvorlauf (FF)",
    rgb_purple: "<b>Lila (Dauerhaft):</b> RÃ¼cklauf (REW) / Firmware-Update (OTA)",
    rgb_yellow: "<b>Gelb (Dauerhaft):</b> Hochfahren / WLAN-Verbindung / Testmodus",
    rgb_blink_red: "<b>Rot blinkend (500ms):</b> Fehler / StÃ¶rung",
    rgb_blink_blue: "<b>Blau blinkend (500ms):</b> WLAN-Einrichtungsmodus (Access Point)",
    rgb_white: "<b>WeiÃŸes Blinken (150ms):</b> Befehl empfangen",
    close: "SchlieÃŸen",
    icon_title: "Bedeutung der PWA-Symbole",
    icon_sec_header: "Header & Bedienung",
    icon_power_title: "Ein/Aus",
    icon_power_desc: "Hauptschalter (Relais 8 - Strom EIN / Standby)",
    icon_ota_title: "OTA-Badge",
    icon_ota_desc: "Firmware-Status (Aktuell, Update verfÃ¼gbar, Server offline)",
    icon_install_title: "App installieren",
    icon_install_desc: "PWA auf Startbildschirm oder Desktop installieren",
    icon_menu_title: "MenÃ¼",
    icon_menu_desc: "Zugriff auf Einstellungen, LED-Dimmer, Symbole und Diagnose",
    icon_sec_transport: "Transportfunktionen",
    icon_play_title: "PLAY (R1)",
    icon_play_desc: "Bandwiedergabe starten",
    icon_stop_title: "STOP (R2)",
    icon_stop_desc: "Bandtransport stoppen",
    icon_rec_title: "RECORD (R3)",
    icon_rec_desc: "Aufnahmemodus aktivieren",
    icon_pause_title: "PAUSE (R4)",
    icon_pause_desc: "Pause / Aufnahme pausieren",
    icon_ff_title: "FF (R5)",
    icon_ff_desc: "Schneller Vorlauf",
    icon_rew_title: "REW (R6)",
    icon_rew_desc: "Schneller RÃ¼cklauf",
    icon_sec_visual: "Visuelle Anzeigen",
    icon_reels_title: "Drehende Spulen",
    icon_reels_desc: "Visuelles Feedback von Laufrichtung und Geschwindigkeit",
    info_title: "Info",
    info_app: "App",
    info_version: "Version",
    info_device: "GerÃ¤t",
    info_firmware: "Firmware",
    info_gateway: "Gateway",
    btn_rgb: "RGB-LED",
    btn_icons: "Symbole",
    ota_title: "Firmware-Update (OTA)",
    ota_current_ver: "Aktuelle Version",
    ota_avail_ver: "VerfÃ¼gbare Version",
    ota_status: "Status",
    ota_status_checking: "PrÃ¼fen...",
    ota_btn_check: "PrÃ¼fen",
    ota_btn_install: "Jetzt installieren",
    ota_progress: "Firmware sicher herunterladen und SHA-256 verifizieren...",
    ota_update_available: "Neuere Version v{ver} verfÃ¼gbar!",
    ota_up_to_date: "Firmware ist aktuell.",
    ota_unreachable: "GerÃ¤t / Server nicht erreichbar.",
    ota_downloading: "Firmware wird heruntergeladen...",
    ota_installing: "Firmware wird installiert...",
    ota_rebooting: "Relay Box wird neu gestartet...",
    ota_ready: "Bereit",
    ota_error_check: "Fehler beim PrÃ¼fen",
    ota_none: "Keine",
    ota_confirm_install: "MÃ¶chten Sie die neueste Firmware wirklich installieren?\nDie Relay Box startet nach der Installation automatisch neu.",
    ota_install_success: "Installation abgeschlossen! Relay Box startet jetzt neu...",
    ota_install_failed: "Installation fehlgeschlagen: ",
    ota_install_error: "Fehler bei der Installation: ",
    ios_title: "App installieren",
    ios_btn_ok: "Verstanden",
    ios_safari_title: "In Safari Ã¶ffnen und Teilen â†’ Zum Home-Bildschirm wÃ¤hlen.",
    ios_safari_1: "1. Tippen Sie in Safari auf die SchaltflÃ¤che <b>Teilen</b>.",
    ios_safari_2: "2. Nach unten scrollen und <b>Zum Home-Bildschirm</b> (+) wÃ¤hlen.",
    ios_safari_3: "3. Oben rechts auf <b>HinzufÃ¼gen</b> tippen.",
    ios_ff_title: "Firefox auf iOS",
    ios_ff_desc: "Firefox auf iOS unterstÃ¼tzt keine direkte PWA-Installation.<br>1. Tippen Sie in Firefox auf das MenÃ¼ (<b>â‹¯</b>).<br>2. WÃ¤hlen Sie <b>In Safari Ã¶ffnen</b>.<br>3. In Safari auf <b>Teilen</b> tippen und <b>Zum Home-Bildschirm</b> (+) wÃ¤hlen.",
    ios_chrome_title: "Chrome auf iOS",
    ios_chrome_desc: "Chrome auf iOS unterstÃ¼tzt keine direkte PWA-Installation.<br>1. Tippen Sie auf das <b>Teilen-Symbol</b>.<br>2. Tippen Sie auf <b>Zum Home-Bildschirm</b> (oder in Safari Ã¶ffnen &rarr; Teilen &rarr; Zum Home-Bildschirm).<br>3. Auf <b>HinzufÃ¼gen</b> tippen.",
    ios_other_desc: "Dieser Browser auf iOS unterstÃ¼tzt keine PWA-Installation wie Safari. Ã–ffnen Sie diese Seite in Safari, um TAPE zum Home-Bildschirm hinzuzufÃ¼gen.",
    mac_safari_title: "Safari Web App auf macOS",
    mac_safari_desc: "1. Safari-MenÃ¼ oben Ã¶ffnen.<br>2. <b>Ablage &rarr; Zum Dock hinzufÃ¼gen...</b> wÃ¤hlen.<br>3. Auf <b>HinzufÃ¼gen</b> klicken, um die App direkt aus dem Dock zu starten.",
    desktop_ff_title: "Firefox Desktop",
    desktop_ff_desc: "Firefox unterstÃ¼tzt diese Seite als schnelle Web-App.<br>â€¢ DrÃ¼cken Sie <b>Strg + D</b> fÃ¼r ein Lesezeichen.<br>â€¢ Oder ziehen Sie das Schloss-Symbol aus der Adressleiste auf den Schreibtisch.",
    webapp_title: "Web-App-Installation",
    webapp_desc: "â€¢ <b>Chrome / Edge:</b> Klicken Sie auf das Installationssymbol in der Adressleiste.<br>â€¢ <b>Mobil:</b> WÃ¤hlen Sie im BrowsermenÃ¼ <i>Zum Startbildschirm hinzufÃ¼gen</i>."
  },
  es: {
    flag: "ðŸ‡ªðŸ‡¸",
    code: "ES",
    name: "EspaÃ±ol",
    install_app: "Instalar app",
    power: "Encendido",
    menu: "MenÃº",
    ota_badge_title: "ActualizaciÃ³n de firmware",
    menu_install: "Instalar aplicaciÃ³n",
    menu_rgb: "LED RGB & Brillo",
    menu_icons: "GuÃ­a de iconos",
    menu_ota: "ActualizaciÃ³n de firmware",
    menu_diagnostics: "DiagnÃ³stico",
    menu_info: "InformaciÃ³n",
    rgb_title: "Estado & Brillo LED RGB",
    rgb_brightness: "Brillo LED",
    rgb_guide_title: "Colores de estado y significado:",
    rgb_green: "<b>Verde (Fijo):</b> En lÃ­nea & Listo / Encendido / PLAY",
    rgb_red: "<b>Rojo (Fijo):</b> En espera / Apagado / RECORD",
    rgb_blue: "<b>Azul (Fijo):</b> STOP transporte",
    rgb_orange: "<b>Naranja (Fijo):</b> PAUSA transporte",
    rgb_cyan: "<b>Cian (Fijo):</b> Avance rÃ¡pido (FF)",
    rgb_purple: "<b>PÃºrpura (Fijo):</b> Rebobinado (REW) / ActualizaciÃ³n (OTA)",
    rgb_yellow: "<b>Amarillo (Fijo):</b> Iniciando / Conectando Wi-Fi / Modo de prueba",
    rgb_blink_red: "<b>Rojo parpadeante (500ms):</b> Error / Fallo",
    rgb_blink_blue: "<b>Azul parpadeante (500ms):</b> Modo configuraciÃ³n Wi-Fi (Punto de acceso)",
    rgb_white: "<b>Destello blanco (150ms):</b> Comando recibido",
    close: "Cerrar",
    icon_title: "GuÃ­a de iconos PWA",
    icon_sec_header: "Encabezado & Controles",
    icon_power_title: "Encendido",
    icon_power_desc: "Interruptor principal (RelÃ© 8 - Encendido / En espera)",
    icon_ota_title: "Insignia OTA",
    icon_ota_desc: "Estado del firmware (Actualizado, ActualizaciÃ³n disponible, Servidor desconectado)",
    icon_install_title: "Instalar app",
    icon_install_desc: "Instalar PWA en pantalla de inicio o escritorio",
    icon_menu_title: "MenÃº",
    icon_menu_desc: "Acceso a ajustes, atenuador LED, iconos y diagnÃ³sticos",
    icon_sec_transport: "Funciones de transporte",
    icon_play_title: "PLAY (R1)",
    icon_play_desc: "Iniciar reproducciÃ³n de cinta",
    icon_stop_title: "STOP (R2)",
    icon_stop_desc: "Detener transporte de cinta",
    icon_rec_title: "RECORD (R3)",
    icon_rec_desc: "Activar modo grabaciÃ³n",
    icon_pause_title: "PAUSE (R4)",
    icon_pause_desc: "Pausar / pausar grabaciÃ³n",
    icon_ff_title: "FF (R5)",
    icon_ff_desc: "Avance rÃ¡pido de cinta",
    icon_rew_title: "REW (R6)",
    icon_rew_desc: "Rebobinado rÃ¡pido de cinta",
    icon_sec_visual: "Indicaciones visuales",
    icon_reels_title: "Carretes giratorios",
    icon_reels_desc: "Respuesta visual de direcciÃ³n y velocidad",
    info_title: "InformaciÃ³n",
    info_app: "AplicaciÃ³n",
    info_version: "VersiÃ³n",
    info_device: "Dispositivo",
    info_firmware: "Firmware",
    info_gateway: "Pasarela",
    btn_rgb: "LED RGB",
    btn_icons: "Iconos",
    ota_title: "ActualizaciÃ³n de firmware (OTA)",
    ota_current_ver: "VersiÃ³n actual",
    ota_avail_ver: "VersiÃ³n disponible",
    ota_status: "Estado",
    ota_status_checking: "Comprobando...",
    ota_btn_check: "Comprobar",
    ota_btn_install: "Instalar ahora",
    ota_progress: "Descargando firmware de forma segura y verificando SHA-256...",
    ota_update_available: "Â¡Nueva versiÃ³n v{ver} disponible!",
    ota_up_to_date: "El firmware estÃ¡ actualizado.",
    ota_unreachable: "Dispositivo / Servidor no disponible.",
    ota_downloading: "Descargando firmware...",
    ota_installing: "Instalando firmware...",
    ota_rebooting: "Reiniciando Relay Box...",
    ota_ready: "Listo",
    ota_error_check: "Error al comprobar",
    ota_none: "Ninguna",
    ota_confirm_install: "Â¿Seguro que desea instalar el Ãºltimo firmware?\nLa Relay Box se reiniciarÃ¡ automÃ¡ticamente tras la instalaciÃ³n.",
    ota_install_success: "Â¡InstalaciÃ³n completada! La Relay Box se estÃ¡ reiniciando...",
    ota_install_failed: "Error en la instalaciÃ³n: ",
    ota_install_error: "Error durante la instalaciÃ³n: ",
    ios_title: "Instalar aplicaciÃ³n",
    ios_btn_ok: "Entendido",
    ios_safari_title: "Abra en Safari y elija Compartir â†’ AÃ±adir a pantalla de inicio.",
    ios_safari_1: "1. Toque el botÃ³n <b>Compartir</b> en Safari.",
    ios_safari_2: "2. DesplÃ¡cese hacia abajo y toque <b>AÃ±adir a pantalla de inicio</b> (+).",
    ios_safari_3: "3. Toque <b>AÃ±adir</b> arriba a la derecha.",
    ios_ff_title: "Firefox en iOS",
    ios_ff_desc: "Firefox en iOS no admite la instalaciÃ³n directa de PWA.<br>1. Toque el menÃº en Firefox (<b>â‹¯</b>).<br>2. Elija <b>Abrir en Safari</b>.<br>3. En Safari, toque <b>Compartir</b> y luego <b>AÃ±adir a pantalla de inicio</b> (+).",
    ios_chrome_title: "Chrome en iOS",
    ios_chrome_desc: "Chrome en iOS no admite la instalaciÃ³n directa de PWA.<br>1. Toque el icono <b>Compartir</b>.<br>2. Toque <b>AÃ±adir a pantalla de inicio</b> (o abra en Safari &rarr; Compartir &rarr; AÃ±adir a pantalla de inicio).<br>3. Toque <b>AÃ±adir</b>.",
    ios_other_desc: "Este navegador en iOS no admite la instalaciÃ³n de PWA como Safari. Abra esta page en Safari para aÃ±adir TAPE a su pantalla de inicio.",
    mac_safari_title: "AplicaciÃ³n web Safari en macOS",
    mac_safari_desc: "1. Abra el menÃº Safari en la parte superior.<br>2. Elija <b>Archivo &rarr; AÃ±adir al Dock...</b>.<br>3. Haga clic en <b>AÃ±adir</b> para iniciar la app directamente desde el Dock.",
    desktop_ff_title: "Firefox Escritorio",
    desktop_ff_desc: "Firefox admite esta pÃ¡gina como aplicaciÃ³n web rÃ¡pida.<br>â€¢ Presione <b>Ctrl + D</b> para crear un marcador.<br>â€¢ O arrastre el icono del candado al escritorio.",
    webapp_title: "InstalaciÃ³n de la aplicaciÃ³n web",
    webapp_desc: "â€¢ <b>Chrome / Edge:</b> Haga clic en el icono de instalaciÃ³n en la barra de direcciones.<br>â€¢ <b>MÃ³vil:</b> Elija <i>AÃ±adir a pantalla de inicio</i> en el menÃº del navegador."
  }
};

let currentLang = 'en';

function getInitialLanguage() {
  try {
    const saved = localStorage.getItem('taperc_lang');
    if (saved && (saved === 'en' || saved === 'fr' || saved === 'de' || saved === 'es')) {
      return saved;
    }
  } catch(e) {}

  const browserLang = (navigator.language || navigator.userLanguage || '').toLowerCase();
  if (browserLang.startsWith('fr')) return 'fr';
  if (browserLang.startsWith('de')) return 'de';
  if (browserLang.startsWith('es')) return 'es';
  if (browserLang.startsWith('en')) return 'en';
  
  return 'en';
}

function t(key, params) {
  const dict = I18N[currentLang] || I18N.en;
  let text = dict[key] || (I18N.en && I18N.en[key]) || key;
  if (params && typeof text === 'string') {
    for (const k in params) {
      text = text.replace(new RegExp('\\{' + k + '\\}', 'g'), params[k]);
    }
  }
  return text;
}

function setLanguage(lang) {
  if (!I18N[lang]) lang = 'en';
  currentLang = lang;
  try {
    localStorage.setItem('taperc_lang', lang);
  } catch(e) {}
  document.documentElement.lang = lang;
  applyTranslations();
}

function toggleLangMenu(force) {
  const m = document.getElementById('langMenu');
  const btn = document.getElementById('btnLang');
  if (!m) return;
  const show = typeof force === 'boolean' ? force : !m.classList.contains('show');
  if (show) {
    toggleMenu(false);
  }
  m.classList.toggle('show', show);
  if (btn) btn.classList.toggle('active', show);
}

function applyTranslations() {
  const dict = I18N[currentLang] || I18N.en;
  
  // 1. data-i18n attributes
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.getAttribute('data-i18n');
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });

  // 2. data-i18n-html attributes
  document.querySelectorAll('[data-i18n-html]').forEach((el) => {
    const key = el.getAttribute('data-i18n-html');
    if (dict[key]) {
      el.innerHTML = dict[key];
    }
  });

  // 3. data-i18n-menu attributes
  document.querySelectorAll('[data-i18n-menu]').forEach((el) => {
    const key = el.getAttribute('data-i18n-menu');
    const icon = el.getAttribute('data-icon') || '';
    if (dict[key]) {
      el.innerHTML = (icon ? icon + ' ' : '') + dict[key];
    }
  });

  // 4. Header buttons & tooltips
  const flagEl = document.getElementById('langFlag');
  const codeEl = document.getElementById('langCode');
  if (flagEl) flagEl.textContent = dict.flag;
  if (codeEl) codeEl.textContent = dict.code;

  const btnPower = document.getElementById('btnPower');
  if (btnPower) {
    btnPower.title = dict.power;
    btnPower.setAttribute('aria-label', dict.power);
  }
  const btnMenu = document.getElementById('btnMenu');
  if (btnMenu) {
    btnMenu.title = dict.menu;
    btnMenu.setAttribute('aria-label', dict.menu);
  }

  // 5. Update iOS modal & OTA status if available
  updateIosModalContent();
  if (typeof lastOtaData !== 'undefined') {
    updateOtaUI(lastOtaData);
  }
}

// PWA Install Prompt Handling
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = document.getElementById('btnInstall');
  if (btn) btn.style.display = 'inline-block';
});

function getBrowserEnv() {
  const ua = navigator.userAgent || '';
  const isIos = (/iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) && !window.MSStream;
  const isMac = /Macintosh|Mac OS X/i.test(ua) && !isIos;
  const isAndroid = /Android/i.test(ua);
  const isWindows = /Windows/i.test(ua);

  let browser = 'other';
  if (/FxiOS/i.test(ua)) browser = 'ios-firefox';
  else if (/CriOS/i.test(ua)) browser = 'ios-chrome';
  else if (/EdgiOS/i.test(ua)) browser = 'ios-edge';
  else if (/Firefox/i.test(ua)) browser = 'firefox';
  else if (/Edg/i.test(ua)) browser = 'edge';
  else if (/Chrome/i.test(ua)) browser = 'chrome';
  else if (/Safari/i.test(ua) && (isIos || isMac)) browser = 'safari';

  return { isIos, isMac, isAndroid, isWindows, browser };
}

function updateIosModalContent() {
  const titleEl = document.getElementById('iosModalTitle');
  const bodyEl = document.getElementById('iosModalBody');
  if (!bodyEl) return;

  const env = getBrowserEnv();
  if (titleEl) titleEl.textContent = t('ios_title');

  if (env.isIos) {
    if (env.browser === 'ios-firefox') {
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">' + t('ios_ff_title') + '</p>' +
        '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' + t('ios_ff_desc') + '</p>';
    } else if (env.browser === 'ios-chrome') {
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">' + t('ios_chrome_title') + '</p>' +
        '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' + t('ios_chrome_desc') + '</p>';
    } else if (env.browser === 'ios-edge' || /OPiOS/i.test(navigator.userAgent)) {
      bodyEl.innerHTML = '<p style="margin-bottom:8px;color:#cbd5e1;">' + t('ios_other_desc') + '</p>';
    } else {
      bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">' + t('ios_safari_title') + '</p>' +
        '<p style="font-size:12px;color:#94a3b8;text-align:left;line-height:1.6;">' +
        t('ios_safari_1') + '<br>' +
        t('ios_safari_2') + '<br>' +
        t('ios_safari_3') + '</p>';
    }
  } else if (env.isMac && env.browser === 'safari') {
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">' + t('mac_safari_title') + '</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' + t('mac_safari_desc') + '</p>';
  } else if (env.browser === 'firefox') {
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">' + t('desktop_ff_title') + '</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' + t('desktop_ff_desc') + '</p>';
  } else {
    bodyEl.innerHTML = '<p style="margin-bottom:8px;font-weight:600;color:#f8fafc;">' + t('webapp_title') + '</p>' +
      '<p style="font-size:13px;color:#cbd5e1;line-height:1.6;text-align:left;">' + t('webapp_desc') + '</p>';
  }
}

function promptInstall() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => {
      deferredPrompt = null;
      const btn = document.getElementById('btnInstall');
      if (btn) btn.style.display = 'none';
    });
  } else {
    toggleIosModal(true);
  }
}

function toggleIosModal(show) {
  const m = document.getElementById('iosModal');
  if (m) {
    if (show) updateIosModalContent();
    m.style.display = show ? 'flex' : 'none';
  }
}

function toggleInfoModal(show) {
  const m = document.getElementById('infoModal');
  if (m) m.style.display = show ? 'flex' : 'none';
}

function toggleRgbModal(show) {
  const m = document.getElementById('rgbLedModal');
  if (m) m.style.display = show ? 'flex' : 'none';
}

function toggleIconModal(show) {
  const m = document.getElementById('pwaIconModal');
  if (m) m.style.display = show ? 'flex' : 'none';
}

function onRgbSliderChange(val) {
  const valEl = document.getElementById('rgbDimmerVal');
  if (valEl) valEl.textContent = val + '%';
  const diagVal = document.getElementById('diagRgbDimmerVal');
  if (diagVal) diagVal.textContent = val + '%';
}

async function saveRgbBrightness(val) {
  try {
    const res = await fetch('/api/v1/led/brightness', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({brightness: Number(val)})
    });
    if (res.ok) {
      const data = await res.json();
      const valEl = document.getElementById('rgbDimmerVal');
      if (valEl && typeof data.brightness !== 'undefined') {
        valEl.textContent = data.brightness + '%';
      }
    }
  } catch(e) {
    console.debug('Failed to save LED brightness:', e);
  }
}

function toggleOtaModal(show) {
  const m = document.getElementById('otaModal');
  if (m) {
    m.style.display = show ? 'flex' : 'none';
    if (show) triggerOtaCheck();
  }
}

let lastOtaData = null;

function updateOtaUI(ota) {
  if (ota) lastOtaData = ota;
  const badge = document.getElementById('otaBadge');
  const availVerEl = document.getElementById('otaAvailVer');
  const currentVerEl = document.getElementById('otaCurrentVer');
  const statusTextEl = document.getElementById('otaStatusText');
  const btnInstall = document.getElementById('btnOtaInstall');
  const shaRow = document.getElementById('rowOtaSha');
  const shaEl = document.getElementById('otaSha');

  if (badge) {
    badge.style.display = 'inline-flex';
    badge.title = t('ota_badge_title');
    if (ota && ota.update_available) {
      badge.className = 'ota-badge update-ready';
      badge.innerHTML = '&#x2B06; v' + (ota.available_version || 'update');
    } else if (ota && (ota.state === 'unreachable' || ota.state === 'error' || ota.status === 'offline')) {
      badge.className = 'ota-badge offline';
      badge.innerHTML = (ota.current_version ? ('v' + ota.current_version) : 'v0.5.4') + ' &#9888;';
    } else {
      badge.className = 'ota-badge';
      badge.innerHTML = ((ota && ota.current_version) ? ('v' + ota.current_version) : 'v0.5.4') + ' &#x2714;';
    }
  }

  if (!ota) return;

  if (currentVerEl && ota.current_version) currentVerEl.textContent = 'v' + ota.current_version;
  if (availVerEl) availVerEl.textContent = ota.available_version ? ('v' + ota.available_version) : t('ota_none');

  if (statusTextEl) {
    if (ota.update_available) {
      statusTextEl.textContent = t('ota_update_available', {ver: ota.available_version});
      statusTextEl.style.color = '#4ade80';
    } else if (ota.state === 'up_to_date') {
      statusTextEl.textContent = t('ota_up_to_date');
      statusTextEl.style.color = '#38bdf8';
    } else if (ota.state === 'unreachable' || ota.status === 'offline') {
      statusTextEl.textContent = t('ota_unreachable');
      statusTextEl.style.color = '#f87171';
    } else if (ota.state === 'downloading') {
      statusTextEl.textContent = t('ota_downloading');
      statusTextEl.style.color = '#f59e0b';
    } else if (ota.state === 'installing') {
      statusTextEl.textContent = t('ota_installing');
      statusTextEl.style.color = '#f59e0b';
    } else if (ota.state === 'rebooting') {
      statusTextEl.textContent = t('ota_rebooting');
      statusTextEl.style.color = '#22c55e';
    } else {
      statusTextEl.textContent = ota.state || t('ota_ready');
      statusTextEl.style.color = '#cbd5e1';
    }
  }

  if (btnInstall) {
    btnInstall.style.display = ota.update_available ? 'inline-block' : 'none';
  }

  if (shaRow && shaEl) {
    if (ota.release_info && ota.release_info.sha256) {
      shaRow.style.display = 'flex';
      shaEl.textContent = ota.release_info.sha256.substring(0, 16) + '...';
    } else {
      shaRow.style.display = 'none';
    }
  }
}

async function triggerOtaCheck() {
  const statusTextEl = document.getElementById('otaStatusText');
  if (statusTextEl) {
    statusTextEl.textContent = t('ota_status_checking');
    statusTextEl.style.color = '#38bdf8';
  }
  try {
    const res = await fetch('/api/v1/ota/check', {method: 'POST'});
    if (res.ok) {
      const data = await res.json();
      updateOtaUI(data);
    }
  } catch(e) {
    if (statusTextEl) {
      statusTextEl.textContent = t('ota_error_check');
      statusTextEl.style.color = '#f87171';
    }
  }
}

async function pollOtaStatus() {
  try {
    const res = await fetch('/api/v1/ota/status', {cache: 'no-store'});
    if (res.ok) {
      const data = await res.json();
      updateOtaUI(data);
    } else {
      updateOtaUI(null);
    }
  } catch(e) {
    updateOtaUI(null);
  }
}

async function confirmAndInstallOta() {
  if (!confirm(t('ota_confirm_install'))) {
    return;
  }
  const prog = document.getElementById('otaProgress');
  const progText = document.getElementById('otaProgressText');
  const actArea = document.getElementById('otaActionArea');
  if (prog) prog.style.display = 'block';
  if (actArea) actArea.style.display = 'none';
  if (progText) progText.textContent = t('ota_progress');

  try {
    const res = await fetch('/api/v1/ota/install', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({confirmed: true})
    });
    const data = await res.json();
    if (res.ok && data.success) {
      if (progText) progText.textContent = t('ota_install_success');
      setTimeout(() => {
        location.reload();
      }, 6000);
    } else {
      alert(t('ota_install_failed') + (data.error || 'Unknown error'));
      if (prog) prog.style.display = 'none';
      if (actArea) actArea.style.display = 'flex';
    }
  } catch(e) {
    alert(t('ota_install_error') + e);
    if (prog) prog.style.display = 'none';
    if (actArea) actArea.style.display = 'flex';
  }
}

function toggleMenu(show) {
  const menu = document.getElementById('dropdownMenu');
  const btn = document.getElementById('btnMenu');
  if (!menu) return;
  const isVisible = menu.classList.contains('show');
  const next = show !== undefined ? show : !isVisible;
  if (next) {
    toggleLangMenu(false);
    menu.classList.add('show');
    if (btn) btn.classList.add('active');
  } else {
    menu.classList.remove('show');
    if (btn) btn.classList.remove('active');
  }
}

function handleOutsideClick(e) {
  const menuContainer = document.querySelector('.menu-container');
  if (menuContainer && !menuContainer.contains(e.target)) {
    toggleMenu(false);
  }
  const langContainer = document.querySelector('.lang-container');
  if (langContainer && !langContainer.contains(e.target)) {
    toggleLangMenu(false);
  }
}
function handleOutsideMenu(e) { handleOutsideClick(e); }
document.addEventListener('click', handleOutsideClick);
document.addEventListener('touchstart', handleOutsideClick, { passive: true });

// State
let isPowered = false;
let isSending = false;
let currentMotion = null;
let activeTransport = null;

function updateTransportUI(activeName) {
  activeTransport = activeName;
  const transportRelays = [1, 2, 3, 4, 5, 6];
  transportRelays.forEach(r => {
    const btn = document.getElementById('btn-r' + r);
    if (!btn) return;
    btn.classList.remove('active-fn');
    const led = btn.querySelector('.led-indicator');
    if (led) led.classList.remove('on');
  });

  if (activeName) {
    const map = {
      'PLAY': 'btn-r1',
      'STOP': 'btn-r2',
      'RECORD': 'btn-r3',
      'PAUSE': 'btn-r4',
      'FF': 'btn-r5',
      'REW': 'btn-r6'
    };
    const id = map[activeName];
    if (id) {
      const activeBtn = document.getElementById(id);
      if (activeBtn) {
        activeBtn.classList.add('active-fn');
        const led = activeBtn.querySelector('.led-indicator');
        if (led) led.classList.add('on');
      }
    }
  }
}

function updatePowerUI(powered) {
  isPowered = powered;
  const btnPower = document.getElementById('btnPower');
  if (btnPower) {
    if (powered) {
      btnPower.classList.remove('off');
      btnPower.classList.add('on');
    } else {
      btnPower.classList.remove('on');
      btnPower.classList.add('off');
    }
  }

  const transportRelays = [1, 2, 3, 4, 5, 6];
  transportRelays.forEach(r => {
    const btn = document.getElementById('btn-r' + r);
    if (btn) btn.disabled = !powered;
  });

  if (!powered) {
    setReelsMotion(null);
    updateTransportUI(null);
  }
}

async function togglePower() {
  if (isSending) return;
  isSending = true;

  if (navigator.vibrate) {
    try { navigator.vibrate(50); } catch(e){}
  }

  const targetState = !isPowered;
  const endpoint = targetState ? '/api/v1/relay/8/on' : '/api/v1/relay/8/off';

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'}
    });
    if (res.ok) {
      updatePowerUI(targetState);
    } else {
      checkInitialPower();
    }
  } catch(e) {
    console.error('Power API error:', e);
    checkInitialPower();
  } finally {
    isSending = false;
  }
}

async function checkInitialPower() {
  try {
    const res = await fetch('/api/v1/status', {cache: 'no-store'});
    if (res.ok) {
      const data = await res.json();
      const r8State = (data.relay && (data.relay[8] === 1 || data.relay['8'] === 1)) || (data.relay8 === true);
      updatePowerUI(!!r8State);
      if (data.ota) updateOtaUI(data.ota);
      if (data.led && typeof data.led.brightness !== 'undefined') {
        const slider = document.getElementById('rgbDimmerSlider');
        const valEl = document.getElementById('rgbDimmerVal');
        if (slider && document.activeElement !== slider) {
          slider.value = data.led.brightness;
        }
        if (valEl && document.activeElement !== slider) {
          valEl.textContent = data.led.brightness + '%';
        }
      }
    }
  } catch(e) {
    console.debug('Status fetch error:', e);
  }
}

function setReelsMotion(motionClass) {
  const left = document.getElementById('reelLeft');
  const right = document.getElementById('reelRight');
  if (left) left.className = 'reel' + (motionClass ? ' ' + motionClass : '');
  if (right) right.className = 'reel' + (motionClass ? ' ' + motionClass : '');
  currentMotion = motionClass;
}

async function handleTransport(relayNum, name, motion) {
  if (!isPowered || isSending) return;
  isSending = true;

  if (navigator.vibrate) {
    try { navigator.vibrate(35); } catch(e){}
  }

  const btn = document.getElementById('btn-r' + relayNum);
  if (btn) btn.classList.add('pressed');

  try {
    const res = await fetch('/api/v1/relay/' + relayNum + '/pulse', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({duration_ms: 100})
    });
    if (res.ok) {
      updateTransportUI(name);
      if (motion !== undefined) setReelsMotion(motion);
    }
  } catch(e) {
    console.error('Transport command error:', e);
  } finally {
    setTimeout(() => {
      if (btn) btn.classList.remove('pressed');
      isSending = false;
    }, 150);
  }
}

// Logo Handling
const GIT_LOGO_URL = 'https://taperc.aaiq.nl/images/logo.png';
const LOGO_CACHE_KEY = 'aaiq_tape_logo_v1';

async function initLogo() {
  const logoImg = document.getElementById('headerLogo');
  if (!logoImg) return;

  function setLogoSrc(src) {
    if (src) logoImg.src = src;
  }

  try {
    const res = await fetch(GIT_LOGO_URL, { cache: 'no-cache' });
    if (res.ok) {
      const blob = await res.blob();
      const reader = new FileReader();
      reader.onloadend = function() {
        const dataUrl = reader.result;
        try {
          localStorage.setItem(LOGO_CACHE_KEY, dataUrl);
        } catch(e) {}
        setLogoSrc(dataUrl);
      };
      reader.readAsDataURL(blob);
      return;
    }
  } catch(e) {
    // Offline / Git unreachable
  }

  try {
    const cached = localStorage.getItem(LOGO_CACHE_KEY);
    if (cached) {
      setLogoSrc(cached);
      return;
    }
  } catch(e) {}

  logoImg.onerror = function() {
    logoImg.style.display = 'none';
  };
}

window.addEventListener('DOMContentLoaded', () => {
  setLanguage(getInitialLanguage());
  checkInitialPower();
  initLogo();
  pollOtaStatus();
  setInterval(checkInitialPower, 5000);
  setInterval(pollOtaStatus, 30000);
});

