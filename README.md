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
| `scripts/inscripcions.py` | La tasca automàtica: llegeix les reserves de Brevo (o els pagaments de Stripe), compta les places i envia els correus. |
| `correus/` | La primera versió dels correus (transferència, benvinguda, preparació, caducada i edició completa). Un cop creats a Brevo, es canvien des de Brevo. |
| `.github/workflows/places.yml` | Diu a GitHub que faci la tasca automàtica cada 15 minuts. |

## Com es publica

1. La web es publica amb **GitHub Pages**, des de la branca `main`. Cada canvi que s'hi desa surt publicat en un o dos minuts.
2. Ara mateix l'adreça és la que dona GitHub. Més endavant s'hi connectarà el domini **comuniquemambia.cat** (provisional).
3. El fitxer `.nojekyll` (buit) diu a GitHub que publiqui els fitxers tal com són, sense transformar-los.

## Com funcionen les inscripcions

Cada 15 minuts, GitHub executa `scripts/inscripcions.py` (`.github/workflows/places.yml`). Què fa depèn de `pagament` a `edicions.json`.

### Mode `transferencia` (curs pilot, ara actiu)

1. «Reserva» obre un formulari a la web. Les dades van a la llista **Reserves** de Brevo (l'adreça del formulari és `formulari_brevo` a `edicions.json`).
2. L'script envia el correu amb les dades de la transferència i el termini (`hores_per_pagar`, ara 48 h). La plaça compta com a ocupada.
3. Quan arriba la transferència, a Brevo s'obre el contacte i es marca **PAGAT**. L'script envia la benvinguda i afegeix la persona a «Inscrits <data>» i a «Butlletí».
4. Si passa el termini sense pagar, la reserva caduca (correu d'avís) i la plaça queda lliure.
5. Una setmana abans de l'edició, els que han pagat reben el correu de preparació.
6. Si una edició ja és plena quan arriba una reserva, la persona rep el correu «Edició completa» i queda amb ESTAT `espera`.

Els textos dels correus són plantilles de Brevo («Curs IA · …»). La primera versió és a `correus/`. El correu de transferència no s'envia mentre la plantilla tingui el text «[ESCRIU AQUÍ…]»: cal posar-hi el titular i l'IBAN des de Brevo.

### Mode `stripe` (per a més endavant)

Cada edició té un enllaç de pagament de Stripe amb un límit de 10 pagaments. L'script crea els enllaços, compta els pagaments i fa la mateixa feina amb Brevo (benvinguda, butlletí i preparació).

### Claus

Són secrets del repositori (Settings → Secrets and variables → Actions): `BREVO_KEY` i, per al mode Stripe, `STRIPE_KEY`. Sense claus, la tasca no fa res.

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
