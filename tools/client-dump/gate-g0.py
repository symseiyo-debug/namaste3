#!/usr/bin/env python3
"""QUOI/POURQUOI : gate-g0.py — Gate G0 du cahier Namaste 3 (étage 0 : le dump du client 3.6.10.10).

Mesure INDÉPENDANTE — jamais le mot « SUCCESS » de l'outil de dump. Deux instruments de natures
différentes, qui doivent rendre le MÊME ensemble :
  I1 = regex sur global-metadata.dat BRUT          (la référence : ce que le client embarque)
  I2 = regex sur les DLL fantômes du dump          (ce que le dump a conservé)
  I3 = flux sur cs/il2cpp.cs                        (les classes protobuf, sous nom obfusqué)

Forme du terrain, mesurée le 04/09 : les 1223 noms Com.Ankama.Dofus.Server.* ne sont PAS des noms de
types du C# (les types sont obfusqués) — ce sont des LITTÉRAUX portés par Ankama.Dofus.Protocol.Game.dll
(1200) et Ankama.Dofus.Protocol.Connection.dll (23). Une gate qui les cherchait comme `class X` rendait
0 % sur un dump complet : un rouge fabriqué par l'instrument.

VERT ssi : couverture |I1∩I2|/|I1| ≥ 95 %  ET  invention |I2∖I1| == 0  ET  5 témoins inventés absents
           ET  ≥ 1000 classes IBufferMessage dans le C#.
--epreuve : éprouve la gate DANS LES DEUX SENS (04/09) — le dump réel doit passer (témoin négatif),
            et deux sabotages (couverture, invention) doivent la faire ROUGIR (témoins positifs).
            Une garde qui ne rougit pas sur un sabotage est inerte ; une qui rougit sur le réel sera
            contournée puis désarmée.
Loi F : imprime sa progression ; tout ce qu'elle écarte se compte et se dit.

COMMENT LANCER : python3 gate-g0.py <dossier-dump> [--epreuve]
GATE : rc=0 ssi VERT (voir le seuil VERT ci-dessus) ; rc=1 si ROUGE ; rc=2 si l'argument dump manque.
"""
import os, re, sys, time, itertools
from collections import Counter

# DÉFAUT CORRIGÉ le 05/09 (trouvé par la chaîne d'outils) : ce chemin était EN DUR sur la build
# 3.6.10.10/11. Juger le dump d'une build N contre le metadata d'une build M rend un VERT PAR ACCIDENT
# (deux builds voisines se ressemblent) — exactement ce que la loi L6 interdit. La référence se PASSE
# maintenant en argument, et le rapport imprime le chemin utilisé. / Metadata path is now an argument:
# judging build N's dump against build M's metadata would pass by accident.
META_DEFAUT = "internal/artefacts/temoins-3.0/global-metadata.dat"
META = os.environ.get("NAMASTE_META", META_DEFAUT)
ETAGE0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Définition de la RÉFÉRENCE (mesurée le 04/09, trois lectures du même terrain) :
#   sans + ni |  → 513  messages de tête        · avec + → 1003 noms de types uniques (imbriqués `Outer+Types+X`,
#   convention .NET FullName) · avec + et | → 1223 littéraux (les variantes `X|Types` sont d'autres chaînes).
# On retient « avec + » : un type imbriqué EST un message du protocole. / Reference = .NET FullName incl. nested.
NAME_RE = re.compile(rb"Com\.Ankama\.Dofus\.Server\.[A-Za-z0-9_.+]+")
SEUIL = 0.95
TEMOINS_INVENTES = [
    "Com.Ankama.Dofus.Server.Game.Protocol.Fake.FakeFooEvent",
    "Com.Ankama.Dofus.Server.Game.Protocol.Fake.PhantomBarRequest",
    "Com.Ankama.Dofus.Server.Connection.Protocol.DecoyBazMessage",
    "Com.Ankama.Dofus.Server.Game.Protocol.Fake.GhostQuxEvent",
    "Com.Ankama.Dofus.Server.Game.Protocol.Fake.MirageQuuxCmd",
]

# Imprime la progression sur stderr (jamais stdout, qui porte le rapport final). / Progress on stderr only (stdout carries the final report).
def log(msg):
    print(msg, file=sys.stderr, flush=True)

def noms_dans(path):
    """Ensemble des noms + suffixes bruts (6 octets après chaque nom) pour voir la forme du terrain."""
    data = open(path, "rb").read()
    noms, suffixes = set(), Counter()
    for m in NAME_RE.finditer(data):
        noms.add(m.group(0).decode())
        suffixes[data[m.end():m.end() + 6]] += 1
    return noms, suffixes, len(data)

# I1 = la référence : noms du global-metadata.dat BRUT. / I1 = the reference: names from the RAW global-metadata.dat.
def instrument_1(meta=META):
    t = time.time()
    noms, suffixes, n = noms_dans(meta)
    log(f"  I1 metadata brut : {n/1e6:.1f} Mo lus, {len(noms)} noms uniques ({time.time()-t:.1f}s)")
    return noms, suffixes

# I2 = ce que le dump a conservé : noms trouvés dans chaque DLL fantôme. / I2 = what the dump kept: names found in each ghost DLL.
def instrument_2(dump):
    t = time.time()
    dll_dir = os.path.join(dump, "dll")
    total, par_dll = set(), {}
    fichiers = sorted(os.listdir(dll_dir)) if os.path.isdir(dll_dir) else []
    for i, f in enumerate(fichiers, 1):
        noms, _, _ = noms_dans(os.path.join(dll_dir, f))
        if noms:
            par_dll[f] = len(noms)
            total |= noms
        if i % 40 == 0:
            log(f"  I2 DLL : {i}/{len(fichiers)} lues…")
    log(f"  I2 DLL fantômes : {len(fichiers)} DLL, {len(par_dll)} en portent, {len(total)} noms uniques ({time.time()-t:.1f}s)")
    return total, par_dll

def instrument_3(dump, exemples=3):
    """Compte les classes protobuf (IBufferMessage) du C# et capture N exemples avec leurs numéros de champ."""
    t = time.time()
    cs = os.path.join(dump, "cs", "il2cpp.cs")
    n_msg, n_ns_clair, lignes = 0, 0, 0
    # Les en-têtes '// Image N: X.dll - … - Types A-B' sont REGROUPÉS en tête de fichier : on attribue
    # chaque classe à son assembly par sa plage TypeDefIndex, pas par position dans le fichier.
    # Image headers are grouped at the top: attribute each class by its TypeDefIndex range, not by position.
    par_image, plages = Counter(), []
    img_re = re.compile(r"^// Image \d+: (\S+) - .* - Types (\d+)-(\d+)")
    tdi_re = re.compile(r"TypeDefIndex: (\d+)")
    # Trouve l'assembly (image) d'un TypeDefIndex par sa plage — pas par position dans le fichier.
    # / Finds a TypeDefIndex's assembly (image) by its range — not by file position.
    def image_de(tdi):
        for nom, a, b in plages:
            if a <= tdi <= b: return nom
        return "?"
    captures, en_cours = [], None
    with open(cs, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            lignes += 1
            if lignes % 500_000 == 0:
                log(f"  I3 C# : {lignes} lignes…")
            m = img_re.match(line)
            if m:
                plages.append((m.group(1), int(m.group(2)), int(m.group(3)))); continue
            if line.startswith("namespace Com.Ankama.Dofus.Server"):
                n_ns_clair += 1                  # attendu 0 : les types du PROTOCOLE sont obfusqués / expected 0
            if "IBufferMessage" in line and " class " in line:
                mt = tdi_re.search(line)          # pas `t` : il masquait le chrono / not `t`: shadowed the timer
                image = image_de(int(mt.group(1))) if mt else "?"
                n_msg += 1; par_image[image] += 1
                if len(captures) < exemples and "Protocol" in image:   # exemples pris dans le protocole, pas dans Google
                    en_cours = {"decl": line.strip()[:140], "image": image, "champs": []}
            elif en_cours is not None:
                if "const int" in line:
                    en_cours["champs"].append(line.strip()[:100])
                if line.strip().startswith("// Properties") or line.strip().startswith("// Methods"):
                    captures.append(en_cours); en_cours = None
    log(f"  I3 C# : {lignes} lignes, {n_msg} classes IBufferMessage, {n_ns_clair} namespaces Com.Ankama.Dofus.Server en clair ({time.time()-t:.1f}s)")
    return n_msg, n_ns_clair, captures, par_image

# Compose le verdict VERT/ROUGE depuis les 3 instruments : couverture, invention, témoins, volume.
# / Composes the VERT/ROUGE verdict from the 3 instruments: coverage, invention, witnesses, volume.
def verdict(ref, dump_noms, n_msg):
    inter = ref & dump_noms
    manquants = sorted(ref - dump_noms)
    inventes = sorted(dump_noms - ref)
    couverture = len(inter) / len(ref) if ref else 0.0
    temoins_ok = all(t not in ref and t not in dump_noms for t in TEMOINS_INVENTES)
    vert = couverture >= SEUIL and not inventes and temoins_ok and n_msg >= 1000
    raisons = []
    if couverture < SEUIL: raisons.append(f"couverture {couverture:.1%} < {SEUIL:.0%} ({len(manquants)} manquants)")
    if inventes: raisons.append(f"invention : {len(inventes)} nom(s) dans le dump ABSENTS du metadata")
    if not temoins_ok: raisons.append("un témoin inventé est présent — l'instrument ou le témoin est cassé")
    if n_msg < 1000: raisons.append(f"seulement {n_msg} classes IBufferMessage (< 1000)")
    return dict(vert=vert, couverture=couverture, inter=len(inter), manquants=manquants,
                inventes=inventes, temoins_ok=temoins_ok, raisons=raisons)

# Rend le rapport markdown complet (verdict + détail des 3 instruments) — c'est ÇA qui est archivé.
# / Renders the full markdown report (verdict + 3-instrument detail) — this is what gets archived.
def rapport(dump, ref, suffixes, dump_noms, par_dll, n_msg, n_ns_clair, captures, v):
    par_image = v["par_image"]
    lignes = []
    P = lignes.append
    P(f"# Gate G0 — rapport mesuré le {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    P(f"Dump : `{dump}`  ·  script : `tools/gate-g0.py` (rejouable, `--epreuve` pour les deux sens)\n")
    P(f"## Verdict : {'🟢 VERT' if v['vert'] else '🔴 ROUGE'}")
    for r in v["raisons"]: P(f"- refus : {r}")
    P("")
    P("## Instrument 1 — metadata brut (référence)")
    tete = len({n.split('+')[0] for n in ref})
    P(f"- **{len(ref)} noms de types uniques** `Com.Ankama.Dofus.Server.*` (convention .NET `Outer+Types+X`), "
      f"dont {tete} messages de tête. Les 1223 « noms » d'avant étaient des LITTÉRAUX (variantes `X|Types` comptées) ; "
      "le 2687 du cahier n'a jamais été reproduit — retiré.")
    P("- forme du terrain, 6 octets APRÈS chaque nom (top 5) : " + ", ".join(f"`{k!r}`×{n}" for k, n in suffixes.most_common(5)))
    P("")
    P("## Instrument 2 — DLL fantômes du dump")
    for f, n in sorted(par_dll.items(), key=lambda x: -x[1]): P(f"- `{f}` : {n}")
    P(f"- **couverture I2 ⊇ I1 : {v['inter']}/{len(ref)} = {v['couverture']:.2%}** (seuil {SEUIL:.0%})")
    P(f"- manquants (I1∖I2) : {len(v['manquants'])}" + (" — " + ", ".join(v['manquants'][:8]) if v['manquants'] else ""))
    P(f"- **inventés (I2∖I1) : {len(v['inventes'])}**" + (" — " + ", ".join(v['inventes'][:8]) if v['inventes'] else " — le dump n'invente rien"))
    P(f"- témoins inventés ({len(TEMOINS_INVENTES)}) absents des deux côtés : {'oui' if v['temoins_ok'] else 'NON'}")
    P("")
    P("## Instrument 3 — C# décompilé")
    P(f"- classes `IBufferMessage` (messages protobuf générés) : **{n_msg}**, par assembly : " +
      ", ".join(f"`{k}` {n}" for k, n in par_image.most_common(6)))
    P(f"- namespaces `Com.Ankama.Dofus.Server.*` en clair : {n_ns_clair} → les types du PROTOCOLE sont obfusqués "
      "(les autres `Com.Ankama.*`, ex. HaapiAnkama, restent en clair) ; les 513 noms clairs sont des littéraux")
    P("- exemples de messages du protocole, nom obfusqué mais NUMÉROS DE CHAMP en clair :")
    for c in captures:
        P(f"- `{c['decl']}` ← `{c['image']}`")
        for ch in c["champs"][:6]: P(f"    - `{ch}`")
    P("")
    P("## Ce que G0 prouve / ne prouve pas")
    P("- prouve : le dump conserve les noms de messages et expose les classes protobuf avec leurs numéros de champ.")
    P("- ne prouve PAS : la correspondance nom clair ↔ classe obfusquée (c'est l'étage 1, le matcher structurel).")
    return "\n".join(lignes) + "\n"

# Fait tourner les 3 instruments + le verdict ; *_override permet à --epreuve d'injecter un sabotage.
# / Runs the 3 instruments + the verdict; *_override lets --epreuve inject a sabotage.
def mesurer(dump, ref_override=None, dump_override=None, quiet=False):
    ref, suffixes = instrument_1()
    dump_noms, par_dll = instrument_2(dump)
    if ref_override: ref = ref | ref_override
    if dump_override: dump_noms = dump_noms | dump_override
    n_msg, n_ns_clair, captures, par_image = instrument_3(dump)
    v = verdict(ref, dump_noms, n_msg)
    v["par_image"] = par_image
    return ref, suffixes, dump_noms, par_dll, n_msg, n_ns_clair, captures, v

# Point d'entree CLI : --epreuve (3 témoins, deux sens) ou une mesure réelle + rapport écrit sur disque.
# / CLI entry point: --epreuve (3 witnesses, both directions) or a real measurement + report written to disk.
def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    dump = sys.argv[1]
    if "--meta" in sys.argv:                      # référence explicite : --meta <global-metadata.dat de CETTE build>
        globals()["META"] = sys.argv[sys.argv.index("--meta") + 1]
    log(f"  référence (metadata) : {META}")
    if "--epreuve" in sys.argv:
        log("=== ÉPREUVE de la gate dans les DEUX sens ===")
        sabot_couv = {f"Com.Ankama.Dofus.Server.Game.Protocol.Sabotage.Fantome{i}Event" for i in range(100)}
        sabot_inv = {"Com.Ankama.Dofus.Server.Game.Protocol.Sabotage.InventeParLeDumpEvent"}
        cas = [
            ("dump réel (témoin NÉGATIF : doit PASSER)", {}, True),
            ("sabotage couverture : +100 noms fantômes dans la référence (doit ROUGIR)", {"ref_override": sabot_couv}, False),
            ("sabotage invention : +1 nom dans le dump absent du metadata (doit ROUGIR)", {"dump_override": sabot_inv}, False),
        ]
        tout_bon = True
        for nom, kw, attendu_vert in cas:
            *_, v = mesurer(dump, **kw)
            ok = v["vert"] == attendu_vert
            tout_bon &= ok
            print(f"{'✅' if ok else '❌'} {nom} → {'VERT' if v['vert'] else 'ROUGE'} ; {'; '.join(v['raisons']) or 'aucun refus'}")
        print("ÉPREUVE :", "la gate mord dans les deux sens" if tout_bon else "LA GATE EST CASSÉE (inerte ou paranoïaque)")
        sys.exit(0 if tout_bon else 1)

    ref, suffixes, dump_noms, par_dll, n_msg, n_ns_clair, captures, v = mesurer(dump)
    texte = rapport(dump, ref, suffixes, dump_noms, par_dll, n_msg, n_ns_clair, captures, v)
    out = os.path.join(ETAGE0, "GATE-G0-RAPPORT.md")
    open(out, "w").write(texte)
    v2 = os.path.join(ETAGE0, "noms-protocole-en-clair.v2.txt")
    open(v2, "w").write("\n".join(sorted(ref)) + "\n")
    print(texte)
    print(f"→ rapport : {out}\n→ noms propres (v2, sans octet parasite ni suffixe) : {v2} ({len(ref)} lignes)")
    sys.exit(0 if v["vert"] else 1)

if __name__ == "__main__":
    main()
