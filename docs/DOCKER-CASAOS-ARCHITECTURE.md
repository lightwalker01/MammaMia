# MammaMia — documentazione tecnica del fork Docker / CasaOS

> Stato: documentazione del fork `lightwalker01/MammaMia`, aggiornata al 15 novembre 2026. È un **fork di packaging non ufficiale**, non un fork funzionale. Il codice e l'idea dell'addon appartengono a [UrloMythus/MammaMia](https://github.com/UrloMythus/MammaMia). Questo documento permette di capire e ricostruire la distribuzione del container, ma non sostituisce i test runtime sul server.

## 1. Obiettivi e confini

- Conservare sul fork i sorgenti upstream (anche se il repository originale diventasse temporaneamente inaccessibile).
- Sincronizzare gli aggiornamenti upstream una volta al giorno **senza force-push** e senza eliminare file personalizzati.
- Costruire su GitHub Actions, pubblicare su `ghcr.io/lightwalker01/mammamia`, eseguire su CasaOS senza clone locale.
- Supportare **soltanto linux/amd64**, preferendo una base minima compatibile rispetto a Alpine.
- Non modificare in Git i file applicativi originali: personalizzazioni grafiche eseguite **solo durante la build**.
- Mantenere `config.json` editabile e persistente in AppData, inizializzato automaticamente la prima volta.
- L'addon non è offline: richieste a provider, TMDB, Kitsu, EPG ecc. continuano a richiedere Internet. Si ospitano localmente soltanto gli asset grafici generali dell'interfaccia.

## 2. Repository e componenti

| Percorso | Responsabilità |
| --- | --- |
| `Dockerfile.ghcr` | Build dell'immagine AMD64, dipendenze Python, Tesseract, predisposizione configurazione e patch di packaging |
| `Dockerfile.ghcr.dockerignore` | Esclusioni dal contesto di build specifiche del Dockerfile |
| `docker-entrypoint.sh` | Primo avvio: copia il config di default nel bind mount, senza sovrascrivere modifiche successive |
| `docker-assets/patch_branding.py` | Riscrive, **nell'immagine**, i riferimenti alle immagini e il logo del manifest |
| `docker-assets/pizza.png` | Icona della pizza storica, recuperata dall'utente tramite Wayback Machine e ridimensionata per il packaging |
| `docker-assets/background.png` | Sfondo originale 800×800 recuperato dall'utente; derivato PNG 256×256 con palette a 3 colori per ridurre la dimensione dell'immagine. Si conserva il disegno originale, non la qualità originale |
| `compose.casaos.yml` | Compose per CasaOS, con metadati `x-casaos`, bind mount e impostazioni |
| `.github/workflows/sync-upstream.yml` | Fetch/merge giornaliero o manuale da upstream |
| `.github/workflows/publish-ghcr.yml` | Build su PR; build + push GHCR dopo modifiche a main, dispatch o sync |
| `README.md` | Avviso sullo scopo limitato del fork, link al compose e a questo documento |
| `run.py`, `static/*`, `Src/*` | Sorgenti dell'applicazione mantenuti identici a upstream nel repository, salvo eventuali cambiamenti upstream |

Storico: la PR #1 ha aggiunto la distribuzione Docker e CasaOS; la PR #2 introduce gli asset locali (pizza e sfondo) e la patch di branding.

## 3. Scelte Docker

- Base `python:3.11-slim-bookworm`: Debian Slim/glibc per compatibilità con wheel binarie, soprattutto `curl_cffi` e `lxml`. Alpine è più piccola in astratto, ma potrebbe richiedere compilazioni e adattamenti musl; distroless aumenta la complessità con Tesseract.
- `apt-get install --no-install-recommends tesseract-ocr ca-certificates`: Tesseract eseguibile necessario al progetto; `libtesseract-dev` non serve al runtime Python tramite `pytesseract`.
- `pip install -r requirements.txt pytesseract`, senza cache persistente.
- `COPY requirements.txt` prima del sorgente per riutilizzare cache delle dipendenze.
- Porta applicativa 8080; la porta applicativa è letta dal `config.json` upstream (e può essere sovrascritta da `PORT_ENV` se supportato).
- Immagine limitata a `linux/amd64` nel workflow Docker Buildx. Non è configurata una build ARM64.
- Il container non viene automaticamente aggiornato quando GHCR modifica `latest`: occorre pull/ricreazione in CasaOS o uno strumento dedicato.

## 4. Configurazione persistente e primo avvio

L'applicazione upstream legge `/app/config.json`. Per non sovrascrivere il codice e non dover preparare un file sull'host:

1. Il Dockerfile copia la configurazione di default in `/app/defaults/config.json`.
2. Elimina il file originale da `/app/config.json` e crea un **symlink** `/app/config.json -> /app/data/config.json`.
3. Il Compose monta `/DATA/AppData/mammamia` sull'intera directory `/app/data`, senza coprire `/app` (che contiene i sorgenti).
4. L'entrypoint crea `/app/data/config.json` copiando il default **solo se assente**, poi esegue `python run.py`.
5. Agli aggiornamenti il file dell'host rimane intatto: eventuali nuove opzioni upstream non vengono automaticamente aggiunte a un config già esistente. Se upstream modifica lo schema JSON, verificare manualmente differenze e migrazione.

L'entrypoint interrompe l'avvio se `/app/data/config.json` è una directory, per evitare un errore difficile da diagnosticare.

**Nota:** montare tutto `/DATA/AppData/mammamia:/app` nasconderebbe i sorgenti nell'immagine e impedirebbe l'avvio. Un bind di un *file* inesistente può diventare una directory e fallire; si monta dunque una directory dedicata.

## 5. CasaOS

Nel `compose.casaos.yml`:

- `name: mammamia`, `services.mammamia`, `container_name: mammamia`, immagine `ghcr.io/lightwalker01/mammamia:latest`.
- App ID esplicito: `x-casaos.store_app_id: lightwalker01-mammamia`. Titolo UI `MammaMia`; architettura `amd64`; porta 8080; `index: /configure`.
- Icona e thumbnail CasaOS puntano all'asset PNG tracciato nel **fork GitHub** (CasaOS non può caricare icone da un'istanza locale non nota al momento dell'importazione). Le immagini dell'interfaccia interna vengono invece servite dal **container**.
- Variabile `TMDB_KEY`: impostare un valore valido nell'interfaccia CasaOS, non nel repository. Variabile `TZ: Europe/Rome`.
- `restart: unless-stopped`, `init: true`, `no-new-privileges:true`, rotazione dei log `json-file` con 10 MiB × 3.
- Percorso dati: `/DATA/AppData/mammamia/config.json`; la collocazione effettiva del Compose su CasaOS dipende dalla versione e dalla procedura di import (`/var/lib/casaos/apps/...` è tipico ma non garantito dal solo `store_app_id`).

Da un server CasaOS non serve conservare un clone Git. Se il package GHCR è privato, serve autenticazione Docker; per pull anonimi impostarlo pubblico da GitHub Packages.

## 6. Asset grafici self-hosted e patch in fase di build

URL legacy in upstream:

- Pizza: `https://creazilla-store.fra1.digitaloceanspaces.com/emojis/49647/pizza-emoji-clipart-md.png` (ora restituisce AccessDenied).
- Sfondo: `https://i.postimg.cc/ry3p76HY/italian-seamless-free-vector-pattern3.png`.

La PR #2 conserva le immagini in `docker-assets`. Il pattern fornito originariamente in formato 800×800 è stato ridotto a un derivato 256×256 con quantizzazione a 3 colori per contenere la dimensione del repository; il motivo grafico è quello originale, ma la risoluzione e alcune sfumature cambiano.

La PR #2 conserva le immagini in `docker-assets` e lancia `python3 /app/docker-assets/patch_branding.py` **dopo** `COPY . ./` nel Dockerfile. Modifica le copie già presenti nell'immagine, senza commit sui sorgenti upstream:

- `static/static.py` e `static/configure.py`: URL pizza -> `/icon.png`; background -> `/background.png`; tipo favicon -> `image/png`.
- `static/uprot.html`: stessa sostituzione per la pagina Captcha.
- `run.py`: aggiunta runtime delle route FastAPI `/icon.png` e `/background.png` via `FileResponse`.
- Manifest Stremio: il campo `logo` diventa l'URL assoluto dell'istanza che ha ricevuto la richiesta, derivato da protocollo e host e dai forwarded headers del reverse proxy. Esempi: `http://192.168.1.20:8080/icon.png`, `https://mammamia.example.com/icon.png`.
- CasaOS continua a usare un link RAW a `docker-assets/pizza.png` nel fork.
- Le patch hanno controlli sugli elementi strutturali principali (`from fastapi.responses`, route `/configure`, funzione manifest), così una modifica upstream incompatibile può far fallire la build anziché produrre un'immagine errata.

**Attenzione al reverse proxy:** l'host/protocollo dei forwarded headers devono essere impostati/filtrati dal proxy fidato, non presi ciecamente dal client pubblico. Stremio raggiunge `/icon.png` soltanto se raggiunge l'istanza stessa (un URL LAN non è accessibile fuori dalla LAN).

La patch è volutamente confinata alla presentazione e al manifest: non cambia i provider di streaming.

## 7. Sincronizzazione upstream

Il workflow `sync-upstream.yml` è schedulato con cron `23 3 * * *` (UTC), e avviabile manualmente. Esegue:

```sh
git fetch upstream main
git merge --no-edit upstream/main
git push origin HEAD:main  # soltanto se c'è un nuovo commit
```

Non usa `git reset --hard` né `git push --force`. Se upstream scompare o si verifica un conflitto, l'azione fallisce e lascia `main` invariato. I file specifici del fork non vengono cancellati intenzionalmente, ma non è garantita l'assenza di futuri conflitti se upstream aggiunge file negli stessi percorsi.

**Limitazione:** i fork GitHub non costituiscono un backup offsite indipendente. Per tollerare cancellazione o rimozione del fork, effettuare un mirror periodico `git clone --mirror` su un provider separato o backup privato. Se upstream sparisce, le build possono continuare usando il codice già conservato nel fork.

La precedente action ereditata `sync-build.yml`, con reset forzato e pubblicazione su un Docker Hub di terzi, e `update_domains.yml` sono state rimosse nella PR #1. La modifica dei domini può essere gestita direttamente dal container con il `config.json` persistente; l'endpoint `/update` di upstream usa un servizio esterno e può modificare il file.

## 8. Build e pubblicazione su GHCR

`publish-ghcr.yml` si attiva su:

- Push a `main`: pubblica immagine.
- Pull request verso `main`: **compila senza push**, per verificare le dipendenze (non sono previsti smoke test).
- `workflow_dispatch`: permette build/push manuale.
- `workflow_run` dopo un sync riuscito: controlla il ramo aggiornato e pubblica.

Quest'ultimo trigger è importante: i push fatti con `GITHUB_TOKEN` non avviano necessariamente un ulteriore workflow `push`. Il job di pubblicazione utilizza `packages: write`, login GHCR con `GITHUB_TOKEN`, `docker/build-push-action` e cache `type=gha`.

Tag immagine: `ghcr.io/lightwalker01/mammamia:latest` e `ghcr.io/lightwalker01/mammamia:sha-<12caratteri>`. Il tag SHA consente un rollback a una specifica versione se ancora presente nel registry; `latest` è mutabile e non equivale ad aggiornamento automatico del container.

Il workflow pubblica su una registry raggiungibile via Internet; nessuna chiave TMDB viene inserita nell'immagine.

## 9. Procedura di ricostruzione da zero

Prerequisiti: account GitHub con fork/sorgenti, GitHub Actions abilitato, permessi `contents: write` per sync e `packages: write` per GHCR, host CasaOS `linux/amd64`, Docker, chiave API TMDB.

1. Forkare `UrloMythus/MammaMia` (oppure recuperare un backup dei sorgenti e della storia Git).
2. Aggiungere tutti i file specificati nella sezione 2, prendendoli da questo fork/commit. Non sostituire permanentemente il codice upstream in `run.py` o `static/`.
3. Abilitare i workflow GitHub Actions. Eseguire il workflow di pubblicazione su `main`; verificare su Actions che la build finisca e il package sia creato.
4. Rendere pubblico il package GHCR se CasaOS deve effettuare pull anonimi.
5. In CasaOS importare `compose.casaos.yml`, impostare `TMDB_KEY` reale e verificare che porta 8080 sia libera; se necessario cambiarne la porta **pubblicata**.
6. Avviare il container e verificare `/configure`, `/icon.png`, `/background.png`, `/manifest.json` (quest'ultimo può reindirizzare al manifest parametrizzato).
7. Controllare `/DATA/AppData/mammamia/config.json` creato automaticamente; salvare una copia per backup.
8. Negli aggiornamenti ricreare il container dopo un nuovo pull dell'immagine, preservando il bind mount. Aggiornamenti tramite CasaOS o `docker compose pull && docker compose up -d` dal percorso Compose appropriato.

## 10. Verifiche diagnostiche

```sh
docker ps --filter name=mammamia
docker logs --tail=100 mammamia
docker inspect mammamia --format '{{ .Config.Image }}'
curl -I http://IP_DEL_SERVER:8080/icon.png
curl -I http://IP_DEL_SERVER:8080/background.png
```

`curl -I` usa HEAD: se un endpoint FastAPI accetta soltanto GET potrebbe rispondere 405; in quel caso verificare con `curl -o /dev/null -w '%{http_code}' http://IP_DEL_SERVER:8080/icon.png`. Per il manifest seguire i redirect.

- **Icona CasaOS assente:** controllare l'URL Raw GitHub e la cache della UI CasaOS. Può essere necessario aggiornare/reimportare il Compose o svuotare la cache.
- **Icona web assente:** verificare `/icon.png` dal browser del client e gli errori di rete del browser; verificare che l'immagine Docker sia aggiornata.
- **Config non presente:** controllare permessi del bind mount e log dello script entrypoint.
- **Sync fallita:** leggere il log del workflow e risolvere manualmente il conflitto sul fork, senza forzare la storia.
- **Build fallita:** possibili nuove versioni/strutture upstream, dipendenze Python, cambiamenti delle ancore dello script branding.
- **Manifest con URL sbagliato:** verificare host, `X-Forwarded-Proto`, `X-Forwarded-Host` e configurazione del reverse proxy.
- **Package non scaricabile da CasaOS:** controllare visibilità GHCR e autenticazione.

## 11. Limiti e decisioni di sicurezza

- Questo packaging non rende offline il servizio: metadata, provider, EPG, immagini dei canali TV e flussi multimediali possono continuare a usare siti remoti.
- Non sono inclusi database o volumi aggiuntivi; solo la configurazione è persistente secondo l'attuale codice.
- Si consiglia di esporre verso Internet soltanto tramite reverse proxy HTTPS opportunamente configurato. Non usare l'endpoint `/update` su una porta pubblica senza valutarne la protezione.
- La pubblicazione automatica di commit upstream implica fiducia nei manutentori e nelle dipendenze: un aggiornamento può cambiare comportamenti o rompere l'app. Controllare gli esiti GitHub Actions e conservare tag SHA.
- Per la ridistribuzione degli asset recuperati via archivio verificare la licenza del materiale originale. La presenza sul progetto upstream o su Wayback non prova una licenza di redistribuzione.
- L'immagine viene compilata ma non avviata in CI; lo smoke test è stato escluso per scelta dell'utente, che effettua verifica manuale su CasaOS.

## 12. Riferimenti

- [Upstream](https://github.com/UrloMythus/MammaMia)
- [Fork dedicato al container](https://github.com/lightwalker01/MammaMia)
- [GHCR Packages](https://github.com/lightwalker01?tab=packages)
- [PR #1](https://github.com/lightwalker01/MammaMia/pull/1) — infrastruttura Docker/CasaOS
- [PR #2](https://github.com/lightwalker01/MammaMia/pull/2) — asset grafici locali
- [CasaOS app-management source](https://github.com/IceWhaleTech/CasaOS-AppManagement)
- [Docker Compose reference](https://docs.docker.com/reference/compose-file/)
