# Web del curs «Estratègies de comunicació corporativa amb IA»

Landing del curs presencial d'un dia (Barcelona, en català). És una web feta en HTML pla: un sol fitxer, `index.html`, sense cap programa per compilar-la.

## Què hi ha en aquest repositori

| Fitxer | Per a què serveix |
|---|---|
| `index.html` | Tota la web: textos, estils i animacions. |
| `README.md` | Aquest document. |
| `.gitignore` | Evita que es pugin al repositori fitxers privats (claus) o de sistema. |
| `.nojekyll` | Fa que GitHub Pages publiqui la web tal com és. |

## Com es publica

1. La web es publica amb **GitHub Pages**, des de la branca `main`. Cada canvi que s'hi desa surt publicat en un o dos minuts.
2. Ara mateix l'adreça és la que dona GitHub. Més endavant s'hi connectarà el domini **comuniquemambia.cat** (provisional).
3. El fitxer `.nojekyll` (buit) diu a GitHub que publiqui els fitxers tal com són, sense transformar-los.

## Peces que es connectaran més endavant

| Peça | Servei previst | On viu |
|---|---|---|
| Manual gratuït i llista de correu | Brevo | Formulari del manual → llista de Brevo → correu automàtic amb el PDF. |
| Pagament de 149 € | Stripe | Botó «Reserva plaça» → pàgina de pagament de Stripe. |
| Places (màxim 10 per edició) | Stripe + un servei extern per comptar places | Quan una edició arriba a 10 inscripcions, el botó es tanca. |
| Contacte d'empreses | Brevo o un servei de formularis | Finestra «Contacte», opció empresa. |
| Vídeo de presentació | YouTube o Vimeo | Fora del repositori; a la web només s'hi enganxa. |
| Fotos de les edicions | Cloudinary (o similar) | Fora del repositori; a la web només hi ha els enllaços. |

## Normes importants

- **Les claus i contrasenyes (Brevo, Stripe…) no es posen mai en aquest repositori.** Van a les variables d'entorn de l'allotjament.
- **Vídeos i fotos grans no es pugen aquí.** Es pugen al servei corresponent i a la web hi va l'enllaç.
- Textos en català, registre formal però directe i simple.

---
Jaume Oliva Sala · especialista en comunicació corporativa i digital
