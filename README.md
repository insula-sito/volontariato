# Volontariato nei Paesi baltici → Telegram

Ogni mattina alle 7:00 (ora italiana) un workflow gratuito di GitHub Actions
controlla le nuove opportunità di volontariato in **Lettonia, Lituania ed Estonia**
per l'estate (15 luglio – 10 settembre), le filtra, assegna un punteggio di
affinità e invia su Telegram:

- un messaggio per ogni **nuovo** annuncio (titolo, organizzazione, paese, date,
  scadenza, punteggio con il motivo, link). Se i nuovi sono più di 10, ad esempio
  al primo avvio, arriva un unico elenco riassuntivo;
- ogni **lunedì** un riepilogo degli annunci ancora aperti, ordinati per punteggio,
  con ⏰ sulle scadenze entro 14 giorni;
- un **avviso di salute** se una fonte va in errore o restituisce zero risultati
  per 3 esecuzioni di fila (probabile cambio del sito), e un messaggio quando torna a funzionare.

Costo: zero. GitHub Actions è gratuito per i repository pubblici e Telegram è gratuito.

## Fonti

| Fonte | Metodo | Stato |
|---|---|---|
| Portale europeo per i giovani (ESC) | API JSON interna del sito | ✅ attiva |
| Liepāja 2027 | API WordPress | ✅ attiva |
| Scambieuropei | API WordPress (ricerca) | ✅ attiva |
| Lunaria | endpoint JSON del widget di ricerca | ✅ attiva (campi baltici di solito da marzo) |
| IVS GB | pagina HTML con la tabella dei progetti | ✅ attiva (idoneità: candidatura tramite partner italiano) |
| EstYES | feed RSS dei progetti (+ pagina di dettaglio) | ✅ attiva (solo progetti in Estonia) |
| Youth for Smile (Jaunatne smaidam) | feed RSS | ✅ attiva (solo attività in Lettonia) |
| Legambiente | sitemap + pagine dei campi (JSON-LD), con cache in `data/cache/` | ✅ attiva (max 120 pagine al giorno: la cache si completa in pochi giorni) |
| LCC International University (Klaipėda) | portale annunci (lcchr.catsone.com) + sezione volontari della pagina `summer-program` | ✅ attiva (avvisa quando la sezione cambia) |
| YouthWorksHub | pagine di categoria per paese (dati Nuxt nella pagina) + dettaglio, con cache | ✅ attiva (max 40 dettagli al giorno; l'API è vietata da robots.txt e non si usa) |
| SCI (volunteer.sci.ngo) | API GraphQL pubblica del database | ✅ attiva (idoneità: candidatura tramite SCI Italia) |
| Visas Iespējas | API GraphQL pubblica (eventi "Voluntary work" ed "Exchange programme") | ✅ attiva (molti annunci locali in lettone: penalizzati) |

Fonti escluse di proposito:
- **Allianssi (ESC Baltic Sea)**: i giovani italiani non sono tra quelli ammessi.
- **Database workcamp di EstYES (e-vet.org/fo)**: vietato da robots.txt. I campi di EstYES arrivano comunque tramite Lunaria e Legambiente.
- **Laiks Jauniešiem (sito)**: offerte visibili solo con login. I loro progetti ESC sono già sul Portale europeo.
- **workcamps.sci.ngo**: protetto da Cloudflare. Si usa il nuovo database `volunteer.sci.ngo`.

Il programma rispetta i siti: una richiesta ogni 2-3 secondi per sito (o il
`Crawl-delay` indicato in robots.txt), timeout, User-Agent descrittivo, niente
pagine vietate da robots.txt.

## 1. Creare il bot Telegram

1. In Telegram apri **@BotFather** e invia `/newbot`. Scegli un nome e uno username che finisca in `bot`.
2. BotFather ti risponde con il **token** (tipo `123456789:AA...`). Tienilo segreto.
3. Apri la chat con il tuo nuovo bot e scrivigli un messaggio qualsiasi (per esempio `ciao`).
4. Nel browser apri `https://api.telegram.org/bot<TOKEN>/getUpdates`, sostituendo `<TOKEN>`.
   Nel JSON cerca `"chat":{"id":123456789,...}`: quel numero è il **chat id**.
   Non condividere questo indirizzo: contiene il token.

## 2. Dove mettere i segreti

Su GitHub: **Settings → Secrets and variables → Actions → New repository secret**, e crea:

| Nome | Valore |
|---|---|
| `TELEGRAM_BOT_TOKEN` | il token di BotFather |
| `TELEGRAM_CHAT_ID` | il chat id |

Non scriverli mai nei file del repository: il repository è pubblico.

## 3. Avvio e prove

- **Automatico**: ogni giorno alle 7:00 di Roma. GitHub può ritardare l'avvio di qualche minuto.
  Il cron di GitHub usa l'ora UTC, quindi il workflow parte alle 05:00 e alle 06:00 UTC
  e il programma tiene solo l'esecuzione che corrisponde alle 7:00 italiane (ora legale o solare).
- **Manuale**: scheda **Actions → Controllo giornaliero → Run workflow**.
  - `dry_run` (attivo di default): stampa i risultati nel log senza inviare messaggi né salvare lo stato;
  - `year`: per esempio `2026` per verificare filtri e punteggio sugli annunci dell'estate scorsa ancora online;
  - `sources`: per esempio `eyp liepaja2027` per provare solo alcune fonti;
  - `weekly`: aggiunge il riepilogo settimanale.
- **In locale** (serve Python 3.11 o superiore):
  ```bash
  pip install -r requirements.txt -r requirements-dev.txt
  python -m baltic_watch --dry-run                  # prossima estate
  python -m baltic_watch --dry-run --year 2026 -v   # estate scorsa, mostra anche gli scartati
  python -m pytest -q                               # test
  ```

Lo stato (annunci già visti, salute delle fonti) è in `data/seen.json` e viene
aggiornato con un commit a fine esecuzione. Contiene solo i dati dell'annuncio,
nessun contatto personale.

## 4. Modificare filtri e pesi

Tutto si trova in `config/`, in file YAML che puoi modificare anche dal sito di GitHub (icona della matita):

- `config/filters.yaml`: paesi, con i nomi in più lingue e le città; periodo; durata
  (10-35 giorni, 5-9 nella sezione "brevi, combinabili", individuale ESC fino a 61);
  paese di residenza (`IT`); età (21-30); stati che fanno scartare l'annuncio.
- `config/scoring.yaml`: gruppi di parole chiave con il loro peso (bambini, sport,
  eventi, inglese, ruoli guida), bonus (ESC, spese coperte, gruppo di giovani) e
  penalità (lingua locale obbligatoria, solo lavori manuali).
  Ogni gruppo conta una volta sola. Il punteggio è limitato tra 0 e 100.

Come funzionano i filtri:
- **paese**: deve essere Lettonia, Lituania o Estonia;
- **date**: devono sovrapporsi al periodo; se mancano l'annuncio resta, segnato "date da verificare";
- **durata**: da 10 a 35 giorni; da 5 a 9 giorni va tra i "brevi, combinabili"; il
  volontariato individuale oltre i 2 mesi viene scartato;
- **idoneità**: se l'annuncio elenca i paesi ammessi, l'Italia deve esserci; se non li elenca, l'annuncio è segnato "idoneità da verificare";
- **età**: compatibile con 21-30 anni, quando l'annuncio la indica.

## 5. Aggiungere una fonte

1. Crea `baltic_watch/sources/nome.py` con una classe che eredita da `Source`:
   ```python
   from ..models import Listing
   from .base import Source

   class NomeSource(Source):
       name = "nome"            # usato negli id, in --source e negli avvisi
       label = "Nome leggibile"

       def fetch(self) -> list[Listing]:
           data = self.http.get("https://...").json()   # self.http rispetta robots.txt e il ritmo
           self.raw_count = len(data)                   # elementi letti, prima dei filtri
           return [Listing(id=f"nome:{x['id']}", fonte=self.name, titolo=..., url=..., paese="LV", ...)
                   for x in data]
   ```
   Se possibile usa feed o API; altrimenti leggi l'HTML con BeautifulSoup.
   Le funzioni in `baltic_watch/textutil.py` aiutano a riconoscere paese (`detect_country`),
   date (`find_date_ranges`) ed età (`parse_age`).
2. Registrala in `baltic_watch/sources/__init__.py`.
3. Provala con `--dry-run --source nome`, in locale o da Actions.

## Struttura

```
baltic_watch/
  sources/      una fonte per modulo, interfaccia comune (base.py)
  http.py       richieste rispettose (robots.txt, ritmo, timeout, User-Agent)
  filters.py    filtri          scoring.py   punteggio
  dedupe.py     unione dei duplicati (codice progetto ESC, oppure titolo + date)
  state.py      data/seen.json   notify.py   messaggi Telegram
  main.py       riga di comando
config/         filtri e pesi modificabili
tests/          test automatici (girano su GitHub a ogni push)
```
