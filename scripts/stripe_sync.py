"""Sincronitza les inscripcions del curs: Stripe -> web (places) -> Brevo (correus).

Cada vegada que s'executa (GitHub ho fa cada 15 minuts):
  1. Per a cada edició d'edicions.json, crea l'enllaç de pagament de Stripe si
     encara no existeix (límit de pagaments = nombre de places).
  2. Compta els pagaments completats i escriu places.json, que llegeix la web.
  3. Si hi ha clau de Brevo, per a cada persona inscrita:
       - l'afegeix a la llista «Inscrits <edició>» i a la llista «Butlletí»;
       - li envia el correu de benvinguda (un sol cop);
       - quan falten pocs dies per a l'edició, li envia el correu de preparació
         (un sol cop).
     Què s'ha enviat ja es recorda a Stripe (metadades del pagament), així no es
     repeteix mai cap correu.

Les claus arriben per les variables d'entorn STRIPE_KEY i BREVO_KEY (secrets de
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
PLANTILLES = {
    "benvinguda": ("Curs IA · Benvinguda", "Gràcies per inscriure't: {{ params.EDICIO }}"),
    "preparacio": ("Curs IA · Preparació", "Falta una setmana: com preparar la jornada"),
}


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
        for nom in ("NOM", "EMPRESA", "EDICIO", "TELEFON"):
            if nom not in tenim:
                self("POST", f"/contacts/attributes/normal/{nom}", {"type": "text"})

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
        ids = {}
        for clau, (nom, assumpte) in PLANTILLES.items():
            if nom not in existents:
                with open(os.path.join(arrel, "correus", clau + ".html"), encoding="utf-8") as f:
                    html = f.read()
                existents[nom] = self("POST", "/smtp/templates", {
                    "templateName": nom, "subject": assumpte, "htmlContent": html, "isActive": True,
                    "sender": {"email": rem["email"], "name": rem.get("name") or rem["email"]},
                    "replyTo": rem["email"],
                })["id"]
                print(f"Brevo: creada la plantilla «{nom}».")
            ids[clau] = existents[nom]
        return ids

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
def main():
    clau = os.environ.get("STRIPE_KEY", "").strip()
    if not clau:
        print("Encara no hi ha cap clau de Stripe (secret STRIPE_KEY). No es fa res.")
        return
    mode = "proves" if clau.startswith(("sk_test_", "rk_test_")) else "real"
    clau_brevo = os.environ.get("BREVO_KEY", "").strip()
    brevo = Brevo(clau_brevo) if clau_brevo else None
    avui = datetime.date.today()

    with open(os.path.join(ARREL, "edicions.json"), encoding="utf-8") as f:
        cfg = json.load(f)

    existents = {}
    for pl in stripe_tots("/payment_links", {}, clau):
        md = pl.get("metadata") or {}
        if md.get("curs") == MARCA and md.get("edicio"):
            existents.setdefault(md["edicio"], pl)  # Stripe llista primer el més recent

    if brevo:
        carpeta = brevo.carpeta()
        llistes = brevo.llistes()
        butlleti = brevo.llista(LLISTA_BUTLLETI, llistes, carpeta)
        brevo.atributs()
        plantilles = brevo.plantilles(ARREL)
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

    ruta = os.path.join(ARREL, "places.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            abans = json.load(f)
    except (OSError, ValueError):
        abans = {}
    if abans.get("edicions") == sortida and abans.get("mode") == mode:
        print("Places sense canvis.")
        return
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({
            "actualitzat": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": mode,
            "edicions": sortida,
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("places.json actualitzat.")


if __name__ == "__main__":
    main()
