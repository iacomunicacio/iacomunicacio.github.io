"""Inscripcions del curs: web -> Brevo (o Stripe) -> places i correus.

GitHub l'executa cada 15 minuts. Hi ha dos modes, segons «pagament» a edicions.json:

transferencia (curs pilot)
  La web envia la reserva a la llista «Reserves» de Brevo. Aquest script:
    - envia a cada reserva nova el correu amb les instruccions de la transferència;
    - quan marques PAGAT a Brevo, envia la benvinguda i l'afegeix a «Inscrits <data>»
      i a «Butlletí»;
    - si passa el termini sense pagar, la reserva caduca i la plaça torna a quedar lliure;
    - una setmana abans, envia el correu de preparació als que han pagat;
    - escriu places.json (places ocupades = pendents + pagades).

stripe
  Crea un enllaç de pagament per edició, compta els pagaments i fa el mateix amb
  Brevo (llistes, benvinguda i preparació).

Les claus arriben per les variables d'entorn BREVO_KEY i STRIPE_KEY (secrets de
GitHub) i no s'escriuen mai en cap fitxer. Només fa servir la biblioteca
estàndard de Python.
"""
import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARCA = "curs-comunicacio-ia"
CARPETA_BREVO = "Curs comunicació amb IA"
LLISTA_BUTLLETI = "Butlletí"
LLISTA_RESERVES = "Reserves"
PLANTILLES = {
    "benvinguda": ("Curs IA · Benvinguda", "Plaça confirmada: {{ params.EDICIO }}"),
    "preparacio": ("Curs IA · Preparació", "Falta una setmana: com preparar la jornada"),
    "transferencia": ("Curs IA · Instruccions de pagament", "La teva reserva: com fer la transferència"),
    "caducada": ("Curs IA · Reserva caducada", "La teva reserva ha caducat"),
    "complet": ("Curs IA · Edició completa", "L'edició que has triat ja és plena"),
}
# Mentre la plantilla de transferència contingui aquest text, no s'envia (falta el número de compte).
MARCA_IBAN = "[ESCRIU AQUÍ"


# ---------------------------------------------------------------- utilitats
def peticio(metode, url, capcaleres, cos=None):
    req = urllib.request.Request(url, data=cos, method=metode)
    for k, v in capcaleres.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        missatge = e.read().decode(errors="replace")
        sys.exit(f"Error {e.code} a {metode} {url.split('?')[0]}: {missatge}")


def stripe(metode, ruta, dades=None, clau=None):
    url = "https://api.stripe.com/v1" + ruta
    cos = None
    if dades and metode == "GET":
        url += "?" + urllib.parse.urlencode(dades)
    elif dades:
        cos = urllib.parse.urlencode(dades).encode()
    return peticio(metode, url, {
        "Authorization": "Basic " + base64.b64encode((clau + ":").encode()).decode(),
        "Stripe-Version": "2024-06-20",
    }, cos)


def stripe_tots(ruta, dades, clau):
    dades = dict(dades, limit=100)
    while True:
        pagina = stripe("GET", ruta, dades, clau)
        yield from pagina["data"]
        if not pagina.get("has_more"):
            return
        dades["starting_after"] = pagina["data"][-1]["id"]


class Brevo:
    def __init__(self, clau):
        self.clau = clau

    def __call__(self, metode, ruta, dades=None):
        url = "https://api.brevo.com/v3" + ruta
        cos = json.dumps(dades).encode() if dades is not None and metode != "GET" else None
        if dades and metode == "GET":
            url += "?" + urllib.parse.urlencode(dades)
        return peticio(metode, url, {"api-key": self.clau, "accept": "application/json",
                                     "content-type": "application/json"}, cos)

    def carpeta(self):
        for c in self("GET", "/contacts/folders", {"limit": 50}).get("folders") or []:
            if c["name"] == CARPETA_BREVO:
                return c["id"]
        return self("POST", "/contacts/folders", {"name": CARPETA_BREVO})["id"]

    def llistes(self):
        totes, offset = {}, 0
        while True:
            r = self("GET", "/contacts/lists", {"limit": 50, "offset": offset})
            for l in r.get("lists") or []:
                totes[l["name"]] = l["id"]
            offset += 50
            if offset >= r.get("count", 0):
                return totes

    def llista(self, nom, existents, carpeta):
        if nom not in existents:
            existents[nom] = self("POST", "/contacts/lists", {"name": nom, "folderId": carpeta})["id"]
            print(f"Brevo: creada la llista «{nom}».")
        return existents[nom]

    def atributs(self):
        tenim = {a["name"] for a in self("GET", "/contacts/attributes").get("attributes") or []}
        tipus = {"NOM": "text", "EMPRESA": "text", "EDICIO": "text", "TELEFON": "text", "FACTURA": "text",
                 "ESTAT": "text", "RESERVA_HORA": "text", "PAGAT": "boolean", "PREPARACIO": "boolean"}
        for nom, t in tipus.items():
            if nom not in tenim:
                self("POST", f"/contacts/attributes/normal/{nom}", {"type": t})
                print(f"Brevo: creat el camp {nom}.")

    def plantilles(self, arrel):
        """Crea les plantilles si no hi són. Si ja hi són, no les toca (les edites a Brevo)."""
        existents = {}
        r = self("GET", "/smtp/templates", {"limit": 1000, "templateStatus": "true"})
        for t in r.get("templates") or []:
            existents[t["name"]] = t["id"]
        remitents = [s for s in self("GET", "/senders").get("senders") or [] if s.get("active")]
        if not remitents:
            sys.exit("Brevo: no hi ha cap remitent verificat. Cal verificar el teu correu a Brevo (Remitents).")
        rem = remitents[0]
        ids, self.html = {}, {}
        for t in r.get("templates") or []:
            self.html[t["id"]] = t.get("htmlContent") or ""
        for clau, (nom, assumpte) in PLANTILLES.items():
            if nom not in existents:
                with open(os.path.join(arrel, "correus", clau + ".html"), encoding="utf-8") as f:
                    html = f.read()
                existents[nom] = self("POST", "/smtp/templates", {
                    "templateName": nom, "subject": assumpte, "htmlContent": html, "isActive": True,
                    "sender": {"email": rem["email"], "name": rem.get("name") or rem["email"]},
                    "replyTo": rem["email"],
                })["id"]
                self.html[existents[nom]] = html
                print(f"Brevo: creada la plantilla «{nom}».")
            ids[clau] = existents[nom]
        return ids

    def contactes(self, llista):
        offset = 0
        while True:
            r = self("GET", f"/contacts/lists/{llista}/contacts", {"limit": 500, "offset": offset})
            yield from r.get("contacts") or []
            offset += 500
            if offset >= r.get("count", 0):
                return

    def actualitza(self, email, atributs, llistes=None):
        cos = {"attributes": atributs}
        if llistes:
            cos["listIds"] = llistes
        self("PUT", "/contacts/" + urllib.parse.quote(email), cos)

    def envia(self, plantilla, email, nom, params):
        self("POST", "/smtp/email", {"templateId": plantilla, "to": [{"email": email, "name": nom or email}],
                                     "params": params})


# ---------------------------------------------------------------- Stripe
def crea_enllac(ed, cfg, clau):
    producte = stripe("POST", "/products", {
        "name": f"Curs Comunicació corporativa amb IA · {ed['nom']}",
        "description": "Formació presencial d'un dia a Barcelona. De 9 a 13 h i de 14 a 18 h. Dinar inclòs.",
        "default_price_data[currency]": "eur",
        "default_price_data[unit_amount]": str(int(round(cfg["preu_euros"] * 100))),
        "metadata[curs]": MARCA,
        "metadata[edicio]": ed["data"],
    }, clau)
    return stripe("POST", "/payment_links", {
        "line_items[0][price]": producte["default_price"],
        "line_items[0][quantity]": "1",
        "restrictions[completed_sessions][limit]": str(cfg["places"]),
        "phone_number_collection[enabled]": "true",
        "billing_address_collection": "auto",
        "tax_id_collection[enabled]": "true",
        "invoice_creation[enabled]": "true",
        "custom_fields[0][key]": "nom",
        "custom_fields[0][label][type]": "custom",
        "custom_fields[0][label][custom]": "Nom i cognoms de qui assistirà",
        "custom_fields[0][type]": "text",
        "custom_fields[1][key]": "empresa",
        "custom_fields[1][label][type]": "custom",
        "custom_fields[1][label][custom]": "Empresa o organització (opcional)",
        "custom_fields[1][type]": "text",
        "custom_fields[1][optional]": "true",
        "custom_text[submit][message]": ("Rebràs per correu la confirmació i les indicacions per preparar la jornada, "
                                         "i també el nostre butlletí. Te'n pots donar de baixa quan vulguis."),
        "after_completion[type]": "redirect",
        "after_completion[redirect][url]": f"{cfg['web']}/?inscripcio=ok#edicions",
        "metadata[curs]": MARCA,
        "metadata[edicio]": ed["data"],
    }, clau)


def camp(sessio, clau):
    for c in sessio.get("custom_fields") or []:
        if c.get("key") == clau:
            return ((c.get("text") or {}).get("value") or "").strip()
    return ""


# ---------------------------------------------------------------- principal
def escriu_places(sortida, mode, extra=None):
    ruta = os.path.join(ARREL, "places.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            abans = json.load(f)
    except (OSError, ValueError):
        abans = {}
    nou = dict({"mode": mode, "edicions": sortida}, **(extra or {}))
    if all(abans.get(k) == v for k, v in nou.items()):
        print("Places sense canvis.")
        return
    nou["actualitzat"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(nou, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("places.json actualitzat.")


def preparar_brevo(brevo):
    carpeta = brevo.carpeta()
    llistes = brevo.llistes()
    brevo.atributs()
    return carpeta, llistes, brevo.plantilles(ARREL)


def main():
    with open(os.path.join(ARREL, "edicions.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    clau_brevo = os.environ.get("BREVO_KEY", "").strip()
    brevo = Brevo(clau_brevo) if clau_brevo else None
    if cfg.get("pagament", "transferencia") == "stripe":
        main_stripe(cfg, brevo)
    else:
        main_transferencia(cfg, brevo)


# ---------------------------------------------------------------- transferència
def main_transferencia(cfg, brevo):
    """Reserves amb el formulari de la web (Brevo) i pagament per transferència.

    Estats d'una reserva (camp ESTAT a Brevo):
      nova      acaba d'arribar del formulari (l'script ho canvia a «rebuda» de seguida)
      rebuda    reserva registrada; encara no s'han pogut enviar les instruccions
      pendent   ha rebut les instruccions i encara no ha pagat (compta com a plaça ocupada)
      pagat     en Jaume ha marcat la casella PAGAT a Brevo
      caducada  ha passat el termini sense pagar (plaça alliberada)
      espera    l'edició ja era plena quan va reservar
    """
    extra = {"formulari": cfg.get("formulari_brevo") or None}
    if not brevo:
        print("Encara no hi ha cap clau de Brevo (secret BREVO_KEY). Només s'actualitza places.json.")
        escriu_places({}, "transferencia", extra)
        return
    avui = datetime.date.today()
    hores_pagar = int(cfg.get("hores_per_pagar", 48))
    ara = datetime.datetime.now(datetime.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        local = ZoneInfo("Europe/Madrid")
    except Exception:  # sense dades de zona horària: hora UTC + 1
        local = datetime.timezone(datetime.timedelta(hours=1))
    carpeta, llistes, plantilles = preparar_brevo(brevo)
    reserves = brevo.llista(LLISTA_RESERVES, llistes, carpeta)
    butlleti = brevo.llista(LLISTA_BUTLLETI, llistes, carpeta)
    iban_llest = MARCA_IBAN not in brevo.html.get(plantilles["transferencia"], MARCA_IBAN)
    if not iban_llest:
        print("AVÍS: la plantilla «Curs IA · Instruccions de pagament» encara no té el número de compte. "
              "No s'envien instruccions fins que l'omplis a Brevo.")

    edicions = {e["data"]: e for e in cfg["edicions"]}
    ocupades = {d: 0 for d in edicions}
    # Per ordre d'arribada, perquè l'última plaça sigui per a qui ha reservat abans.
    for c in sorted(brevo.contactes(reserves), key=lambda c: c.get("createdAt") or ""):
        email = c.get("email") or ""
        at = c.get("attributes") or {}
        ed = edicions.get(str(at.get("EDICIO") or "").strip()[:10])
        if not email or not ed:
            continue
        data_ed = datetime.date.fromisoformat(ed["data"])
        # El pagament ha d'arribar com a molt el dia abans de l'edició.
        limit_ed = datetime.datetime.combine(data_ed, datetime.time(0, 0), tzinfo=datetime.timezone.utc)
        estat = (at.get("ESTAT") or "").strip().lower()
        pagat = at.get("PAGAT") in (True, "true", "True", 1, "1", "yes", "Sí")
        if estat == "nova":
            # El formulari posa ESTAT=nova a cada reserva (també si la persona ja havia reservat abans).
            estat, pagat = "rebuda", False
            at["PREPARACIO"] = False
            brevo.actualitza(email, {"ESTAT": "rebuda", "PAGAT": False, "PREPARACIO": False})
        nom = (at.get("NOM") or "").strip()
        params = {"NOM": nom.split(" ")[0] if nom else "", "EDICIO": ed["nom"], "LLOC": cfg.get("lloc", ""),
                  "IMPORT": f"{cfg['preu_euros']} €", "CONCEPTE": f"CURS {ed['data']} {nom}".upper()[:60],
                  "HORES": str(hores_pagar), "WEB": cfg["web"]}
        canvis = {}

        if pagat and estat != "pagat":
            if avui <= data_ed:
                brevo.envia(plantilles["benvinguda"], email, nom, params)
            canvis["ESTAT"] = estat = "pagat"
            brevo.actualitza(email, canvis, [brevo.llista(f"Inscrits {ed['data']}", llistes, carpeta), butlleti])
            print(f"  {email}: pagament confirmat.")
            canvis = {}
        elif estat in ("", "rebuda"):
            if ocupades[ed["data"]] >= cfg["places"] or avui > data_ed:
                brevo.envia(plantilles["complet"], email, nom, params)
                canvis["ESTAT"] = "espera"
            elif iban_llest:
                termini = min(ara + datetime.timedelta(hours=hores_pagar), limit_ed)
                params["TERMINI"] = termini.astimezone(local).strftime("%d/%m/%Y a les %H:%M h")
                brevo.envia(plantilles["transferencia"], email, nom, params)
                canvis.update({"ESTAT": "pendent", "RESERVA_HORA": ara.strftime("%Y-%m-%dT%H:%M:%SZ")})
                estat = "pendent"
            else:
                estat = "pendent"  # la plaça ja compta, però encara no s'han enviat les instruccions
        elif estat == "pendent":
            try:
                reservat = datetime.datetime.strptime(str(at.get("RESERVA_HORA") or ""), "%Y-%m-%dT%H:%M:%SZ") \
                    .replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                reservat = ara
                canvis["RESERVA_HORA"] = ara.strftime("%Y-%m-%dT%H:%M:%SZ")
            if ara > min(reservat + datetime.timedelta(hours=hores_pagar), limit_ed):
                brevo.envia(plantilles["caducada"], email, nom, params)
                canvis["ESTAT"] = estat = "caducada"

        if estat == "pagat" and at.get("PREPARACIO") not in (True, "true") and \
                data_ed - datetime.timedelta(days=cfg.get("dies_preparacio", 7)) <= avui <= data_ed:
            brevo.envia(plantilles["preparacio"], email, nom, params)
            canvis["PREPARACIO"] = True
        if canvis:
            brevo.actualitza(email, canvis)
            print(f"  {email}: {canvis}")
        if estat in ("pendent", "pagat"):
            ocupades[ed["data"]] += 1

    sortida = {d: {"inscrits": n, "places": cfg["places"], "obert": n < cfg["places"], "url": None}
               for d, n in ocupades.items()}
    for d, n in ocupades.items():
        print(f"{edicions[d]['nom']}: {n} de {cfg['places']} places ocupades.")
    escriu_places(sortida, "transferencia", extra)


# ---------------------------------------------------------------- Stripe
def main_stripe(cfg, brevo):
    clau = os.environ.get("STRIPE_KEY", "").strip()
    if not clau:
        print("Encara no hi ha cap clau de Stripe (secret STRIPE_KEY). No es fa res.")
        return
    mode = "proves" if clau.startswith(("sk_test_", "rk_test_")) else "real"
    avui = datetime.date.today()
    existents = {}
    for pl in stripe_tots("/payment_links", {}, clau):
        md = pl.get("metadata") or {}
        if md.get("curs") == MARCA and md.get("edicio"):
            existents.setdefault(md["edicio"], pl)  # Stripe llista primer el més recent

    if brevo:
        carpeta, llistes, plantilles = preparar_brevo(brevo)
        butlleti = brevo.llista(LLISTA_BUTLLETI, llistes, carpeta)
    else:
        print("Sense clau de Brevo (secret BREVO_KEY): no es passen contactes ni s'envien correus.")

    sortida = {}
    for ed in cfg["edicions"]:
        pl = existents.get(ed["data"])
        if pl is None:
            pl = crea_enllac(ed, cfg, clau)
            print(f"Creat l'enllaç de pagament per al {ed['nom']}.")
        sessions = [s for s in stripe_tots("/checkout/sessions", {"payment_link": pl["id"], "status": "complete",
                                                                    "expand[]": "data.payment_intent"}, clau)
                    if s.get("payment_status") == "paid"]
        sortida[ed["data"]] = {
            "inscrits": len(sessions),
            "places": cfg["places"],
            "obert": bool(pl.get("active")) and len(sessions) < cfg["places"],
            "url": pl["url"],
        }
        print(f"{ed['nom']}: {len(sessions)} de {cfg['places']} places.")

        if not brevo or not sessions:
            continue
        data_ed = datetime.date.fromisoformat(ed["data"])
        llista_ed = brevo.llista(f"Inscrits {ed['data']}", llistes, carpeta)
        toca_preparacio = data_ed - datetime.timedelta(days=cfg.get("dies_preparacio", 7)) <= avui <= data_ed
        for s in sessions:
            pi = s.get("payment_intent")
            if not isinstance(pi, dict):
                continue
            fet = pi.get("metadata") or {}
            det = s.get("customer_details") or {}
            email = (det.get("email") or "").strip().lower()
            if not email:
                continue
            nom = camp(s, "nom") or det.get("name") or ""
            params = {"NOM": nom.split(" ")[0] if nom else "", "EDICIO": ed["nom"], "LLOC": cfg.get("lloc", "")}
            nou = {}
            if fet.get("brevo_contacte") != "1":
                brevo("POST", "/contacts", {
                    "email": email, "updateEnabled": True, "listIds": [llista_ed, butlleti],
                    "attributes": {"NOM": nom, "EMPRESA": camp(s, "empresa"), "EDICIO": ed["data"],
                                   "TELEFON": det.get("phone") or ""},
                })
                nou["brevo_contacte"] = "1"
            if fet.get("correu_benvinguda") != "1" and avui <= data_ed:
                brevo.envia(plantilles["benvinguda"], email, nom, params)
                nou["correu_benvinguda"] = "1"
            if fet.get("correu_preparacio") != "1" and toca_preparacio:
                brevo.envia(plantilles["preparacio"], email, nom, params)
                nou["correu_preparacio"] = "1"
            if nou:
                stripe("POST", f"/payment_intents/{pi['id']}", {f"metadata[{k}]": v for k, v in nou.items()}, clau)
                print(f"  {email}: {', '.join(nou)}")

    escriu_places(sortida, mode)


if __name__ == "__main__":
    main()
