# Web del curs «Estratègies de comunicació corporativa amb IA»

Landing del curs presencial d'un dia (Barcelona, en català). És una web feta en HTML pla: un sol fitxer, `index.html`, sense cap programa per compilar-la.

## Què hi ha en aquest repositori

| Fitxer | Per a què serveix |
|---|---|
| `index.html` | Tota la web: textos, estils i animacions. |
| `README.md` | Aquest document. |
| `.gitignore` | Evita que es pugin al repositori fitxers privats (claus) o de sistema. |
| `.nojekyll` | Fa que GitHub Pages publiqui la web tal com és. |
| `edicions.json` | Les dates de les edicions, el preu, les places i el lloc. Per afegir una edició, s'hi afegeix aquí. |
| `places.json` | Les places lliures i l'enllaç de pagament de cada edició. L'escriu sola la tasca automàtica: no s'ha de tocar. |
| `scripts/stripe_sync.py` | La tasca automàtica: crea els enllaços de pagament a Stripe, compta les places i passa les inscripcions a Brevo. |
| `correus/` | La primera versió dels correus de benvinguda i de preparació. Un cop creats a Brevo, es canvien des de Brevo. |
| `.github/workflows/places.yml` | Diu a GitHub que faci la tasca automàtica cada 15 minuts. |

## Com es publica

1. La web es publica amb **GitHub Pages**, des de la branca `main`. Cada canvi que s'hi desa surt publicat en un o dos minuts.
2. Ara mateix l'adreça és la que dona GitHub. Més endavant s'hi connectarà el domini **comuniquemambia.cat** (provisional).
3. El fitxer `.nojekyll` (buit) diu a GitHub que publiqui els fitxers tal com són, sense transformar-los.

## Com funcionen les inscripcions

1. Cada edició té el seu enllaç de pagament de **Stripe**, amb un límit de 10 pagaments. Quan s'arriba a 10, Stripe el tanca.
2. Stripe guarda les dades de cada persona inscrita (nom, correu, telèfon, empresa i dades de factura).
3. Cada 15 minuts, GitHub executa `scripts/stripe_sync.py`, que:
   - actualitza `places.json`, i la web mostra les places lliures o «Complet»;
   - passa cada persona inscrita a **Brevo**, a la llista «Inscrits <data>» i a la llista «Butlletí»;
   - li envia el correu de benvinguda i, una setmana abans, el correu de preparació (cada correu, un sol cop).
4. Les claus són dos secrets del repositori (Settings → Secrets and variables → Actions): `STRIPE_KEY` i `BREVO_KEY`. Sense claus, la tasca no fa res.

## Peces que es connectaran més endavant

| Peça | Servei previst |
|---|---|
| Manual gratuït | Brevo (formulari del manual → llista → correu amb el PDF). |
| Contacte d'empreses | Brevo o un servei de formularis. |
| Vídeo de presentació | YouTube o Vimeo. |
| Fotos de les edicions | Cloudinary (o similar). |

## Normes importants

- **Les claus i contrasenyes (Brevo, Stripe…) no es posen mai en aquest repositori.** Van als secrets del repositori de GitHub.
- **Vídeos i fotos grans no es pugen aquí.** Es pugen al servei corresponent i a la web hi va l'enllaç.
- Textos en català, registre formal però directe i simple.

---
Jaume Oliva Sala · especialista en comunicació corporativa i digital
