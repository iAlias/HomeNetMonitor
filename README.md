# HomeNetMonitor

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11+-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-blue.svg)
![Build EXE](https://github.com/iAlias/HomeNetMonitor/actions/workflows/build.yml/badge.svg)

> **Strumento desktop per il monitoraggio della rete domestica su Windows** — monitora il traffico di rete in tempo reale, scopre i dispositivi connessi e avvisa quando vengono rilevate attività sospette.

---

## Indice

- [Avvio rapido (senza terminale)](#avvio-rapido-senza-terminale)
- [Funzionalità](#funzionalità)
- [Requisiti di sistema](#requisiti-di-sistema)
- [Installazione](#installazione)
- [Avvio dell'applicazione](#avvio-dellapplicazione)
- [Guida all'uso](#guida-alluso)
  - [Dashboard](#-dashboard)
  - [Dispositivi](#-dispositivi)
  - [Connessioni](#-connessioni)
  - [Alert](#-alert)
  - [Impostazioni](#️-impostazioni)
  - [Esportazione CSV](#esportazione-csv)
- [Compilare il file EXE](#compilare-il-file-exe)
- [Eseguire i test](#eseguire-i-test)
- [Struttura del progetto](#struttura-del-progetto)
- [Flusso dei dati](#flusso-dei-dati)
- [Domande frequenti](#domande-frequenti)
- [Contribuire](#contribuire)
- [Licenza](#licenza)

---

## Avvio rapido (senza terminale)

Non vuoi usare il terminale? Hai due opzioni:

### Opzione A — Scarica l'eseguibile già pronto

1. Vai alla pagina [**Releases**](https://github.com/iAlias/HomeNetMonitor/releases/latest) del repository.
2. Scarica `HomeNetMonitor.exe` dalla sezione *Assets*.
3. **Installa [Npcap](https://npcap.com/#download)** (seleziona *"Install Npcap in WinPcap API-compatible Mode"*).
4. Fai doppio clic su `HomeNetMonitor.exe`.  
   Windows mostrerà la finestra UAC per richiedere i privilegi di amministratore: clicca **Sì**.  
   La GUI si apre direttamente, senza nessun terminale.

> L'EXE viene compilato automaticamente dalla CI ad ogni release. Non richiede Python installato.

---

### Opzione B — Lancia dalla cartella sorgente con un doppio clic

Se hai clonato il repository e installato Python, puoi usare gli script nella cartella `scripts/`:

| File | Descrizione |
|---|---|
| `scripts/launch.vbs` | **Consigliato** — avvia l'app senza alcuna finestra di terminale visibile |
| `scripts/launch.bat` | Alternativa — apre un terminale temporaneo solo il tempo di avviare la GUI |

**Passi:**

1. Installa Python 3.11+ e assicurati che sia nel PATH.
2. Installa [Npcap](https://npcap.com/#download).
3. Fai doppio clic su `scripts/launch.vbs`.  
   Al primo avvio vengono creati automaticamente il virtual environment e le dipendenze.  
   Verrà mostrata la finestra UAC — clicca **Sì**.  
   La GUI si apre.

---

## Funzionalità

| Funzione | Descrizione |
|---|---|
| 📊 **Dashboard live** | Grafico bytes/sec (ultimi 60 s), KPI (dispositivi online, connessioni attive, banda), top 5 destinazioni con bandiere nazionali |
| 💻 **Rilevamento dispositivi** | Scansione ARP del sottorete locale ogni 30 s; tabella con IP, MAC, produttore, hostname, stato online/offline |
| 🔗 **Connessioni attive** | Tabella in tempo reale di tutti i flussi di rete con codifica colori (verde = sicuro, giallo = sconosciuto, rosso = segnalato) |
| 🔔 **Regole di alert** | Crea avvisi personalizzati su: nuovo dispositivo, soglia di banda, comunicazione verso un IP specifico, attività su una porta |
| 🌐 **Geolocalizzazione** | Risoluzione batch degli IP tramite ip-api.com (gratuito, senza API key) |
| 🔍 **Reverse DNS** | Risoluzione asincrona degli hostname con cache interna thread-safe |
| 🏭 **Lookup produttore** | Identificazione del produttore dal MAC (OUI) tramite database offline |
| 💾 **Persistenza SQLite** | Log connessioni, log alert, cache geo, regole di alert salvati in locale |
| 🛡 **Avvio senza privilegi** | La GUI si avvia anche senza permessi da amministratore (packet capture disabilitato, funzioni di sola lettura disponibili) |

---

## Requisiti di sistema

- **Sistema operativo**: Windows 10 o Windows 11 (64-bit)
- **Python**: versione 3.11 o superiore ([scarica qui](https://www.python.org/downloads/))
- **[Npcap](https://npcap.com/#download)**: libreria per la cattura di pacchetti su Windows — **obbligatoria** per PacketSniffer e ARP scan. Da installare prima di avviare l'applicazione. Durante l'installazione di Npcap, selezionare l'opzione *"Install Npcap in WinPcap API-compatible Mode"*.
- **Privilegi di amministratore**: necessari per la cattura raw dei pacchetti e la scansione ARP.

---

## Installazione

### 1. Clona il repository

```bash
git clone https://github.com/iAlias/HomeNetMonitor.git
cd HomeNetMonitor
```

### 2. (Consigliato) Crea un ambiente virtuale

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Installa le dipendenze

```bash
pip install -r requirements.txt
```

Le principali dipendenze sono:

| Pacchetto | Versione minima | Scopo |
|---|---|---|
| `PyQt6` | >= 6.6.0 | Framework GUI |
| `pyqtgraph` | >= 0.13.3 | Grafico traffico live |
| `scapy` | >= 2.5.0 | Cattura pacchetti e ARP scan |
| `psutil` | >= 5.9.8 | Info sulle interfacce di rete |
| `netifaces` | >= 0.11.0 | Rilevamento gateway e subnet |
| `requests` | >= 2.31.0 | Chiamate API di geolocalizzazione |

---

## Avvio dell'applicazione

> **Avvia sempre il terminale o il prompt dei comandi come Amministratore** per abilitare la cattura dei pacchetti e la scansione ARP.

```bash
# Con l'ambiente virtuale attivato (da un prompt come Amministratore):
python src/main.py
```

All'avvio, l'applicazione:
1. Crea (se non esiste) la cartella dati in `%APPDATA%\HomeNetMonitor\`
2. Inizializza il database SQLite (`data.db`) e il file di log (`app.log`)
3. Avvia la scansione ARP e il packet sniffer in background
4. Mostra la finestra principale

Se l'applicazione non viene eseguita come amministratore, nella barra di stato comparirà il messaggio:

> Not running as Administrator — packet capture and ARP scan are disabled.

In questo caso la GUI è comunque utilizzabile, ma i dati non verranno aggiornati in tempo reale.

---

## Guida all'uso

### Dashboard

La Dashboard è la schermata principale visualizzata all'avvio. È divisa in tre sezioni:

#### Selettore interfaccia
In cima alla scheda è presente un menu a tendina per selezionare l'interfaccia di rete da monitorare. L'interfaccia attiva viene mostrata anche nella barra di stato in basso a sinistra.

#### Schede KPI (Key Performance Indicators)
Quattro riquadri mostrano in tempo reale:
- **Devices Online** — numero di dispositivi rilevati come attivi sulla rete
- **Active Connections** — numero di flussi di rete attivi in memoria
- **Bandwidth Today (giù)** — byte totali in entrata dall'inizio della giornata (mezzanotte)
- **Bandwidth Today (su)** — byte totali in uscita dall'inizio della giornata

I valori si aggiornano ogni 2 secondi.

#### Grafico traffico live
Il grafico mostra i byte al secondo degli ultimi 60 secondi:
- **Linea blu** — traffico in download
- **Linea rossa** — traffico in upload

> Il grafico richiede `pyqtgraph`. Se non installato, verrà mostrato un messaggio informativo.

#### Top 5 destinazioni
Tabella con le 5 destinazioni che hanno ricevuto più bytes nella sessione corrente, con hostname, paese (con bandiera emoji) e volume di dati.

---

### Dispositivi

La scheda **Devices** mostra tutti i dispositivi scoperti tramite scansione ARP.

#### Tabella dispositivi

| Colonna | Contenuto |
|---|---|
| IP Address | Indirizzo IPv4 corrente del dispositivo |
| MAC Address | Indirizzo MAC fisico |
| Vendor | Produttore rilevato dal MAC (OUI) |
| Hostname | Nome host risolto (se disponibile) |
| Status | **Online** (verde) / **Offline** (rosso) |
| First Seen | Data e ora della prima rilevazione |
| Last Seen | Data e ora dell'ultima risposta ARP |

Un dispositivo viene marcato **Offline** se non risponde alle scansioni ARP per più di 90 secondi.

#### Barra di ricerca
Digita nella barra in alto per filtrare la lista per IP, MAC, hostname o produttore. Il filtro si applica in tempo reale.

#### Menu contestuale (tasto destro)
Fai clic destro su un dispositivo per accedere a tre azioni:

- **Copy IP** — copia l'indirizzo IP nella clipboard
- **Resolve Hostname** — esegue una risoluzione DNS inversa e salva il risultato nel record del dispositivo
- **Block Device (Firewall)** — aggiunge una regola al Windows Firewall per bloccare il traffico in uscita verso quel dispositivo (richiede privilegi da amministratore)

#### Clic su una riga
Facendo clic su un dispositivo si viene automaticamente reindirizzati alla scheda **Connections** filtrata per quell'IP sorgente.

---

### Connessioni

La scheda **Connections** mostra in tempo reale tutti i flussi di rete catturati.

#### Tabella connessioni

| Colonna | Contenuto |
|---|---|
| Source IP | IP sorgente (dispositivo locale) |
| Destination IP | IP destinazione |
| Destination Host | Hostname del destinatario (se risolto via DNS) |
| Port | Porta di destinazione |
| Protocol | TCP / UDP / Other |
| Service | Nome del servizio (es. HTTPS, DNS, SSH) |
| Bytes | Byte totali trasferiti in questo flusso |
| Country | Paese di destinazione (da geolocalizzazione) |
| Duration | Durata del flusso dall'inizio |

#### Codifica colori

| Colore | Significato |
|---|---|
| Verde | Destinazione nota come sicura (Google, Cloudflare, Microsoft Azure, AWS) |
| Giallo | Destinazione sconosciuta (geolocalizzazione non ancora risolta) |
| Rosso | Connessione segnalata da una regola di alert |

#### Filtri
- **Testo libero** — filtra per IP sorgente, IP destinazione, hostname o numero di porta
- **Protocol** — filtra per TCP, UDP, Other o tutti
- **Country** — filtra per nome del paese (es. "Italy", "United States")

---

### Alert

La scheda **Alerts** permette di configurare regole di monitoraggio e visualizzare lo storico degli avvisi.

#### Regole di alert disponibili

| Tipo | Descrizione | Parametri |
|---|---|---|
| **New Unknown Device** | Scatta quando appare un nuovo dispositivo non visto in precedenza | Nessuno |
| **Bandwidth Threshold** | Scatta quando un flusso supera la soglia in MB | Device IP (o "any"), soglia in MB |
| **IP Communication** | Scatta quando un dispositivo comunica con un IP specifico | Source IP (o "any"), IP destinazione |
| **Port Activity** | Scatta quando viene usata una porta specifica (es. 4444, 9050) | Device IP (o "any"), numero porta |

> Gli alert sono soggetti a un **cooldown di 60 secondi** per coppia (regola, dispositivo), per evitare lo spam nel log.

#### Aggiungere una regola

1. Clicca il pulsante **Add Rule**
2. Inserisci un nome descrittivo nel campo *Rule Name*
3. Scegli il tipo di regola dal menu a tendina *Rule Type*
4. Compila i parametri richiesti (i campi cambiano in base al tipo selezionato)
5. Clicca **OK** per salvare

I dati inseriti vengono validati prima del salvataggio: la porta deve essere un numero intero tra 1 e 65535, la soglia di banda deve essere un numero.

#### Eliminare una regola

Seleziona la riga nella tabella delle regole e clicca **Delete Selected**.

#### Log degli alert

La sezione inferiore mostra lo storico degli alert scattati con:
- **Timestamp** — data e ora dell'evento
- **Rule** — nome della regola attivata
- **Device IP** — indirizzo IP del dispositivo coinvolto
- **Detail** — descrizione dettagliata dell'evento

Il log viene aggiornato ogni 3 secondi e mostra gli ultimi 500 eventi. Gli alert generano anche una notifica toast di Windows (se il pacchetto `win10toast` è installato) oppure un messaggio nella barra di stato.

---

### Impostazioni

Apri le impostazioni dal menu **File -> Settings...**

| Impostazione | Descrizione | Valore predefinito |
|---|---|---|
| **Capture Interface** | Interfaccia di rete da monitorare | Prima disponibile |
| **ARP Scan Interval** | Frequenza della scansione ARP in secondi (10-300 s) | 30 s |
| **DB Retention** | Quanti giorni mantenere i dati nel database (1-365) | 7 giorni |
| **Alert Sound** | Abilita le notifiche toast di Windows per gli alert | Attivo |

> La modifica dell'interfaccia di cattura richiede il riavvio dell'applicazione per avere effetto.

---

### Esportazione CSV

Vai su **File -> Export CSV...** per esportare tutte le connessioni attive in un file CSV.

Il file contiene le colonne: `src_ip`, `dst_ip`, `dst_host`, `port`, `protocol`, `service`, `bytes_transferred`, `country`, `city`, `isp`, `first_seen`, `last_seen`, `flagged`.

---

## Compilare il file EXE

Per distribuire l'applicazione come eseguibile standalone (senza richiedere Python installato):

```bash
pip install -r requirements.txt
pyinstaller build.spec
```

L'eseguibile verrà creato in `dist/HomeNetMonitor.exe`. Il file `.spec` è già configurato per:
- Modalità *onefile* (tutto in un singolo `.exe`)
- Richiedere automaticamente elevazione UAC all'avvio (`uac_admin=True`)
- Includere i file di risorse (`mac_oui.json`, `icon.ico`)

---

## Eseguire i test

```bash
pip install pytest
pytest tests/ -v
```

> I test che eseguono la cattura di pacchetti tramite Scapy vengono automaticamente saltati (`pytest.skip`) se Scapy non è installato.

Attualmente la suite comprende 24 test che coprono:
- `DeviceScanner` — rilevamento dispositivi, gestione offline, permessi
- `DnsResolver` — cache, timeout, async lookup, eviction
- `PacketSniffer` — parsing pacchetti TCP/UDP, conteggio bytes

---

## Struttura del progetto

```
HomeNetMonitor/
├── src/
│   ├── main.py                 <- Entry point, configurazione logging
│   ├── ui/
│   │   ├── main_window.py      <- QMainWindow, menu, barra stato, orchestrazione thread
│   │   ├── dashboard_tab.py    <- Grafico live (pyqtgraph) + KPI cards
│   │   ├── devices_tab.py      <- Tabella dispositivi ARP
│   │   ├── connections_tab.py  <- Tabella flussi in tempo reale
│   │   ├── alerts_tab.py       <- Editor regole + log alert
│   │   └── settings_dialog.py  <- Dialog impostazioni
│   ├── core/
│   │   ├── packet_sniffer.py   <- Scapy sniff() in QThread -> segnali Connection
│   │   ├── device_scanner.py   <- ARP broadcast in QThread -> segnali Device
│   │   ├── dns_resolver.py     <- ThreadPoolExecutor reverse-DNS con cache thread-safe
│   │   ├── geo_lookup.py       <- Batch lookup ip-api.com, cache SQLite
│   │   └── data_store.py       <- In-memory + SQLite (dispositivi, connessioni, alert)
│   ├── models/
│   │   ├── device.py           <- Dataclass Device
│   │   └── connection.py       <- Dataclass Connection
│   └── utils/
│       ├── mac_vendor.py       <- OUI JSON -> nome produttore
│       ├── formatting.py       <- Utilita di formattazione condivise (format_bytes)
│       └── constants.py        <- Path, colori, mappa porte, tema QSS
├── resources/
│   ├── mac_oui.json            <- Database OUI incluso
│   └── icon.ico                <- Icona applicazione
├── tests/
│   ├── conftest.py             <- Mock PyQt6 per test senza display
│   ├── test_device_scanner.py
│   ├── test_packet_sniffer.py
│   └── test_dns_resolver.py
├── build.spec                  <- PyInstaller (onefile, uac_admin=True)
├── requirements.txt
└── .github/workflows/build.yml <- Build automatica .exe su push a main
```

---

## Flusso dei dati

```
Npcap -> scapy.sniff() -> PacketSniffer (QThread)
                                |
                    packet_received(Connection)
                                |
                  +-------------v-------------+
                  |         MainWindow         |
                  |  DataStore <--------------+|
                  |  GeoLookup (batch thread)  |
                  |  DnsResolver (pool)        |
                  +-------------+-------------+
                                |
              +-----------------+-----------------+
              v                 v                 v
       DashboardTab       DevicesTab        ConnectionsTab
      (grafico + KPI)   (scanner ARP)      (tabella flussi)
                                                  |
                                            AlertsTab
                                     (valutazione regole + log)
```

**Persistenza** — i dati vengono scritti su SQLite:
- ogni **10 secondi** (`flush_connections_to_db`)
- ogni **ora** viene eseguita la pulizia dei dati piu vecchi del periodo di retention

---

## Domande frequenti

**L'applicazione si avvia ma non vedo nessun dispositivo.**
Assicurati di averla avviata come Amministratore e che Npcap sia installato. Controlla la barra di stato: se mostra `Admin: X` la scansione ARP e' disabilitata.

**Il grafico del traffico e' vuoto.**
Il grafico richiede `pyqtgraph` e privilegi da amministratore per catturare i pacchetti. Verifica l'installazione con `pip show pyqtgraph`.

**Come blocco un dispositivo dalla rete?**
Vai nella scheda **Devices**, fai clic destro sul dispositivo e scegli **Block Device (Firewall)**. L'applicazione aggiungera' una regola al Windows Firewall che blocca il traffico in uscita verso quell'IP. Per rimuovere la regola, aprire il Windows Defender Firewall e cercare le regole con prefisso `HomeNetMonitor_Block_`.

**Gli alert si attivano troppo spesso.**
Ogni coppia (regola, dispositivo) ha un cooldown di 60 secondi. Se il log si riempie comunque rapidamente, considera di aumentare le soglie o di specificare un IP preciso invece di "any".

**Dove vengono salvati i dati?**
Il database (`data.db`) e il file di log (`app.log`) si trovano in `%APPDATA%\HomeNetMonitor\`.

**La geolocalizzazione non funziona.**
HomeNetMonitor usa il servizio gratuito [ip-api.com](http://ip-api.com) che non richiede registrazione. Verifica la connessione internet. Gli indirizzi privati (192.168.x.x, 10.x.x.x, ecc.) non vengono mai geolocalizzati per design.

---

## Contribuire

1. Fai un fork del repository
2. Crea un branch: `git checkout -b feature/mia-funzionalita`
3. Esegui le modifiche e i test: `pytest tests/ -v`
4. Fai commit: `git commit -m "Aggiungi mia funzionalita"`
5. Fai push: `git push origin feature/mia-funzionalita`
6. Apri una Pull Request

Si prega di seguire PEP 8, aggiungere type hint su tutte le funzioni e includere docstring su tutti i metodi pubblici.

---

## Licenza

Questo progetto e' distribuito sotto la [licenza MIT](LICENSE).
