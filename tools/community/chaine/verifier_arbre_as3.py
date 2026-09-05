#!/usr/bin/env python3
"""verifier_arbre_as3.py — l'arbre AS3 exporté est-il COMPLET ? Deux instruments de NATURES différentes.

═══ QUOI / WHAT ═══
Maillon C3 de la chaîne 2.x, la gate qui se pose AVANT d'exploiter un arbre décompilé. Entrée : le
`.swf` et l'arbre `.as`. Sortie : un verdict, la liste NOMMÉE des classes manquantes, et les paquets
troués. N'appartient QU'À la chaîne 2.x (L4).
Stage C3 of the 2.x chain: the gate to run before trusting a decompiled tree.

═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
FR : ffdec ne peut pas être son propre juge. `Exported script 6428/6428` dit que la boucle est allée au
     bout, pas que 6428 classes sont sur le disque (un script peut échouer, une classe peut manquer).
     I1 = parseur ABC MAISON, lit le binaire du SWF (zlib/lzma + tags + pool de constantes + instance_info).
     I2 = l'arbre `.as` exporté, lu comme du TEXTE.
     Deux natures : constantes binaires contre déclarations décompilées. Elles ne partagent pas d'angle mort.
EN : ffdec cannot judge its own export. I1 = home-grown ABC parser over the SWF binary; I2 = the exported
     .as tree read as text. Two different natures, no shared blind spot.

Verdict VERT ssi : couverture |I1∩I2|/|I1| >= seuil (défaut 99 %) ET invention |I2∖I1| == 0
                   ET les 3 témoins inventés absents des deux côtés.
Partition assertée : |I1∩I2| + |I1∖I2| == |I1|.

═══ COMMENT LANCER / HOW TO RUN ═══
  verifier_arbre_as3.py <fichier.swf> <racine-arbre-as3> [--seuil 0.99] [--manquants N]
                        [--prefixe com.ankamagames.dofus.network.]
  verifier_arbre_as3.py --epreuve <fichier.swf> <racine-arbre-as3> [--prefixe …]

`--prefixe` restreint LES DEUX instruments à un sous-arbre de paquets : c'est ainsi qu'on juge un export
PARTIEL (« l'arbre est-il complet CÔTÉ RÉSEAU ? ») sans le déclarer faux parce qu'il n'a pas tout le SWF.
Sans `--prefixe`, la question posée est « l'arbre est-il complet sur TOUT le SWF ».

═══ GATE ═══
`--epreuve` — 5 contrôles, tous verts au 04/09/2026, et chaque barrière doit mordre sur SON sabotage
(le motif du refus est vérifié, sinon un sabotage attrapé par une autre barrière ne prouverait rien) :
témoin NÉGATIF (arbre parfait → VERT) · +200 classes fantômes → refus par la COUVERTURE · +1 classe
inventée → refus par l'INVENTION · témoin injecté des deux côtés → refus par le TÉMOIN · 1 classe
retirée avec le seuil à 0 % → refus par le PAQUET TROUÉ.
Les sabotages s'appliquent à une base SAINE construite exprès : l'état réel, souvent rouge, ne sert que
de repère. Un témoin qui porte déjà un défaut ne mesure que celui-là.
"""
import io
import os
import re
import struct
import sys
import time
import zlib

# 0.99 : seuil choisi pour laisser passer un export sain et refuser un export tronqué. Il ne suffit PAS
# à lui seul — mesuré le 04/09 : 99,44 % sur l'arbre 2.42 cachait 8 classes dont tout le chemin de login.
# D'où le refus PAR PAQUET, qui n'a pas de seuil. / 0.99 alone is not enough: hence the per-package rule.
SEUIL_DEFAUT = 0.99
# Noms fabriqués pour ce test, absents des deux instruments par construction. Ils vérifient que la garde
# LIT vraiment ses deux entrées : si l'un d'eux apparaît, c'est l'instrument ou le témoin qui est cassé.
# Fabricated names, absent from both instruments by construction: they prove the gate actually reads.
TEMOINS_INVENTES = [
    "com.ankamagames.dofus.network.messages.fake.PhantomFooMessage",
    "com.ankamagames.jerakine.fake.DecoyBarType",
    "gs.fake.MirageBazEnum",
]


def log(m):
    """Trace de progression sur stderr : stdout ne porte que le RÉSULTAT.
    Progress goes to stderr; stdout carries the result only."""
    print(m, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- I1 : SWF → ABC → noms de classes
class Lecteur:
    """Lecteur d'octets ABC : u30/u32 sont des entiers à longueur variable (7 bits par octet)."""

    def __init__(self, data):
        """Curseur sur les octets ABC. Cursor over the ABC bytes."""
        self.d = data
        self.i = 0

    def u8(self):
        """Un octet. One byte."""
        v = self.d[self.i]
        self.i += 1
        return v

    def u30(self):
        """Entier à longueur variable : 7 bits utiles par octet, 5 octets au plus (format ABC).
        Variable-length integer: 7 payload bits per byte, at most 5 bytes."""
        v = 0
        for k in range(5):
            b = self.d[self.i]
            self.i += 1
            v |= (b & 0x7F) << (7 * k)
            if not (b & 0x80):
                break
        return v

    u32 = u30
    s32 = u30      # même encodage ; on ne fait que traverser / same encoding, we only skip

    def d64(self):
        """Saute un double : on TRAVERSE le pool sans le décoder, seuls les noms nous intéressent.
        Skips a double; the pool is traversed, not decoded."""
        self.i += 8

    def octets(self, n):
        """n octets bruts. n raw bytes."""
        v = self.d[self.i:self.i + n]
        self.i += n
        return v


def decompresser_swf(chemin):
    """FWS (brut) · CWS (zlib) · ZWS (lzma). Rend le corps NON compressé après l'entête de 8 octets."""
    brut = open(chemin, "rb").read()
    sig, version, taille = brut[:3], brut[3], struct.unpack("<I", brut[4:8])[0]
    if sig == b"FWS":
        corps = brut[8:]
    elif sig == b"CWS":
        corps = zlib.decompress(brut[8:])
    elif sig == b"ZWS":
        import lzma
        # entête LZMA d'Adobe : 4 octets de taille compressée + 5 octets de propriétés
        props = brut[12:17]
        corps = lzma.LZMADecompressor(format=lzma.FORMAT_RAW,
                                      filters=[lzma._decode_filter_properties(lzma.FILTER_LZMA1, props)]
                                      ).decompress(brut[17:])
    else:
        raise SystemExit(f"REFUS : signature SWF inconnue {sig!r} dans {chemin}")
    return sig.decode(), version, taille, corps


def tags_swf(corps):
    """Saute le RECT + frameRate + frameCount, puis rend (code, données) pour chaque tag."""
    f = io.BytesIO(corps)
    premier = f.read(1)[0]
    nbits = premier >> 3
    total_bits = 5 + nbits * 4
    f.seek((total_bits + 7) // 8 - 1, io.SEEK_CUR)   # -1 : l'octet déjà lu
    f.seek(4, io.SEEK_CUR)                            # frameRate (2) + frameCount (2)
    while True:
        entete = f.read(2)
        if len(entete) < 2:
            return
        v = struct.unpack("<H", entete)[0]
        code, longueur = v >> 6, v & 0x3F
        if longueur == 0x3F:
            longueur = struct.unpack("<I", f.read(4))[0]
        yield code, f.read(longueur)
        if code == 0:
            return


def _pool(r):
    """Traverse le pool de constantes et rend (chaînes, namespaces, multinames)."""
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.s32()
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.u32()
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.d64()
    n = r.u30()
    chaines = [""]
    for _ in range(max(0, n - 1)):
        chaines.append(r.octets(r.u30()).decode("utf-8", "replace"))
    n = r.u30()
    ns = [("", 0)]
    for _ in range(max(0, n - 1)):
        kind = r.u8()
        ns.append((kind, r.u30()))
    n = r.u30()
    for _ in range(max(0, n - 1)):        # ns_set : on traverse
        for _ in range(r.u30()):
            r.u30()
    n = r.u30()
    multi = [None]
    for _ in range(max(0, n - 1)):
        kind = r.u8()
        if kind in (0x07, 0x0D):          # QName / QNameA : (ns, name)
            multi.append(("Q", r.u30(), r.u30()))
        elif kind in (0x0F, 0x10):        # RTQName
            multi.append(("RTQ", 0, r.u30()))
        elif kind in (0x11, 0x12):        # RTQNameL
            multi.append(("RTQL", 0, 0))
        elif kind in (0x09, 0x0E):        # Multiname
            multi.append(("M", 0, r.u30())); r.u30()
        elif kind in (0x1B, 0x1C):        # MultinameL
            r.u30(); multi.append(("ML", 0, 0))
        elif kind == 0x1D:                # TypeName (générique)
            r.u30()
            for _ in range(r.u30()):
                r.u30()
            multi.append(("T", 0, 0))
        else:
            raise ValueError(f"multiname de kind inconnu 0x{kind:02X}")
    return chaines, ns, multi


def _traits(r):
    """Traverse les traits d'une classe. Indispensable MÊME SANS LES LIRE : sans cette traversée,
    impossible d'atteindre l'instance SUIVANTE. Skipping traits is required to reach the next one."""
    for _ in range(r.u30()):
        r.u30()                            # name
        kind = r.u8()
        bas = kind & 0x0F
        if bas in (0, 6):                  # Slot / Const
            r.u30(); r.u30()
            if r.u30() != 0:
                r.u8()
        elif bas in (1, 2, 3):             # Method / Getter / Setter
            r.u30(); r.u30()
        elif bas in (4, 5):                # Class / Function
            r.u30(); r.u30()
        else:
            raise ValueError(f"trait de kind inconnu 0x{kind:02X}")
        if (kind >> 4) & 0x04:             # ATTR_Metadata
            for _ in range(r.u30()):
                r.u30()


def classes_dun_abc(data):
    """Noms pleinement qualifiés des classes DÉFINIES par ce bloc ABC (instance_info)."""
    r = Lecteur(data)
    r.u8(); r.u8(); r.u8(); r.u8()         # minor + major (2 × u16)
    r.i = 4
    chaines, ns, multi = _pool(r)
    for _ in range(r.u30()):               # method_info
        pc = r.u30(); r.u30()
        for _ in range(pc):
            r.u30()
        r.u30()
        flags = r.u8()
        if flags & 0x08:
            for _ in range(r.u30()):
                r.u30(); r.u8()
        if flags & 0x80:
            for _ in range(pc):
                r.u30()
    for _ in range(r.u30()):               # metadata_info
        r.u30()
        for _ in range(r.u30()):
            r.u30(); r.u30()
    n_classes = r.u30()
    noms = []
    for _ in range(n_classes):             # instance_info
        idx = r.u30(); r.u30()
        flags = r.u8()
        if flags & 0x08:
            r.u30()
        for _ in range(r.u30()):
            r.u30()
        r.u30()
        _traits(r)
        forme = multi[idx] if 0 < idx < len(multi) else None
        if forme and forme[0] == "Q":
            paquet = chaines[ns[forme[1]][1]] if 0 < forme[1] < len(ns) else ""
            nom = chaines[forme[2]] if 0 < forme[2] < len(chaines) else ""
            noms.append(f"{paquet}.{nom}" if paquet else nom)
    return noms


def instrument_1(swf):
    """I1 — le SWF lui-même : noms pleinement qualifiés des classes DÉFINIES par le binaire.
    I1, the SWF itself: fully-qualified names of the classes it defines."""
    t = time.time()
    sig, ver, taille, corps = decompresser_swf(swf)
    blocs, noms = 0, []
    for code, data in tags_swf(corps):
        if code == 82:                     # DoABC : u32 flags + nom terminé par \0 + ABC
            j = data.index(b"\0", 4)
            noms += classes_dun_abc(data[j + 1:])
            blocs += 1
        elif code == 72:                   # DoABCDefine : ABC brut
            noms += classes_dun_abc(data)
            blocs += 1
    uniques = set(noms)
    log(f"  I1 SWF : {sig} v{ver}, {taille/1e6:.1f} Mo décompressés, {blocs} blocs ABC, "
        f"{len(noms)} classes définies ({len(uniques)} uniques) ({time.time()-t:.1f}s)")
    return uniques, len(noms), blocs


# ------------------------------------------------------------------- I2 : arbre .as → noms de classes
RE_PKG = re.compile(r"^\s*package(?:\s+([\w.]+))?\s*$")
RE_CLS = re.compile(r"^\s*(?:public\s+|final\s+|dynamic\s+|internal\s+)*(class|interface)\s+(\w+)")


def instrument_2(racine):
    """I2 — l'arbre décompilé, lu comme du TEXTE. Nature différente de I1, donc aucun angle mort
    partagé avec ffdec. I2, the decompiled tree read as text: no blind spot shared with ffdec."""
    t = time.time()
    fichiers = []
    for base, _, noms in os.walk(racine):
        for n in noms:
            if n.endswith(".as"):
                fichiers.append(os.path.join(base, n))
    trouves, hors_paquet = set(), 0
    for k, p in enumerate(sorted(fichiers), 1):
        if k % 1000 == 0:
            log(f"  I2 arbre : {k}/{len(fichiers)} fichiers…")
        paquet = None
        for ligne in open(p, encoding="utf-8", errors="replace"):
            m = RE_PKG.match(ligne)
            if m:
                paquet = m.group(1) or ""
                continue
            m = RE_CLS.match(ligne)
            if m:
                if paquet:
                    trouves.add(f"{paquet}.{m.group(2)}")
                else:
                    trouves.add(m.group(2))
                    hors_paquet += 1
    log(f"  I2 arbre : {len(fichiers)} fichiers .as, {len(trouves)} classes déclarées "
        f"({hors_paquet} hors paquet) ({time.time()-t:.1f}s)")
    return trouves, len(fichiers)


# ------------------------------------------------------------------------------------ verdict
def paquet_de(nom):
    """Paquet d'un nom pleinement qualifié — la clé du refus PAR PAQUET.
    Package of a fully-qualified name: the key of the per-package refusal."""
    return nom.rsplit(".", 1)[0] if "." in nom else "<sans>"


def verdict(i1, i2, seuil):
    """Trois refus, pas un seul. Le POURCENTAGE seul est un faux vert : mesuré le 04/09 sur l'arbre 2.42,
    99,44 % de couverture cachaient 3 messages du CHEMIN DE LOGIN absents. Un ratio ne dit pas la forme
    de sa population — d'où le refus PAR PAQUET : tout paquet que l'arbre contient doit être ENTIER."""
    inter = i1 & i2
    manquants = sorted(i1 - i2)
    inventes = sorted(i2 - i1)
    couverture = len(inter) / len(i1) if i1 else 0.0
    temoins_ok = all(t not in i1 and t not in i2 for t in TEMOINS_INVENTES)
    assert len(inter) + len(manquants) == len(i1), "PARTITION CASSÉE sur I1"

    paquets_arbre = {paquet_de(n) for n in i2}
    troues = {}
    for m in manquants:
        p = paquet_de(m)
        if p in paquets_arbre:
            troues.setdefault(p, []).append(m)

    raisons = []
    if couverture < seuil:
        raisons.append(f"couverture {couverture:.2%} < {seuil:.0%} "
                       f"({len(manquants)} classes du SWF absentes de l'arbre)")
    if troues:
        n = sum(len(v) for v in troues.values())
        raisons.append(f"paquets TROUÉS : {len(troues)} paquet(s) présents dans l'arbre mais incomplets "
                       f"({n} classes manquantes) — un paquet à moitié exporté est un trou silencieux")
    if inventes:
        raisons.append(f"invention : {len(inventes)} classe(s) dans l'arbre absentes du SWF")
    if not temoins_ok:
        raisons.append("un témoin inventé est présent — l'instrument ou le témoin est cassé")
    return dict(vert=not raisons, couverture=couverture, inter=len(inter), troues=troues,
                manquants=manquants, inventes=inventes, raisons=raisons)


def main():
    """Arguments, restriction éventuelle à un préfixe, deux modes.
    Arguments, optional prefix restriction, two modes."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seuil = float(sys.argv[sys.argv.index("--seuil") + 1]) if "--seuil" in sys.argv else SEUIL_DEFAUT
    n_show = int(sys.argv[sys.argv.index("--manquants") + 1]) if "--manquants" in sys.argv else 12
    prefixe = sys.argv[sys.argv.index("--prefixe") + 1] if "--prefixe" in sys.argv else ""
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    swf, arbre = args[0], args[1]

    def restreindre(s):
        """Restreint un ensemble au préfixe demandé : c'est ainsi qu'on juge un export VOLONTAIREMENT
        partiel sans le déclarer faux. Restricts a set to the requested prefix."""
        return {n for n in s if n.startswith(prefixe)} if prefixe else s

    if "--epreuve" in sys.argv:
        print("=== ÉPREUVE de verifier_arbre_as3.py (les deux sens) ===")
        i1, n_def, blocs = instrument_1(swf)
        i2, n_fic = instrument_2(arbre)
        i1, i2 = restreindre(i1), restreindre(i2)
        if prefixe:
            print(f"ℹ️  restreint au préfixe `{prefixe}` : I1={len(i1)}, I2={len(i2)}")
        # L'état RÉEL est informatif, jamais la base des sabotages : s'il est déjà rouge, chaque
        # sabotage rougirait par le défaut PRÉEXISTANT et on ne mesurerait rien (un témoin qui porte
        # deux défauts ne mesure que le premier). On sabote donc une base SAINE construite exprès.
        reel = verdict(i1, i2, seuil)
        print(f"ℹ️  état réel → {'VERT' if reel['vert'] else 'ROUGE'} (couverture "
              f"{reel['couverture']:.2%}) ; {'; '.join(reel['raisons']) or 'aucun refus'}")
        print(f"ℹ️  partition : {reel['inter']} communes + {len(reel['manquants'])} manquantes "
              f"= {len(i1)} classes du SWF ; arbre = {n_fic} fichiers .as, {len(i2)} classes")

        sain = set(i1)                       # base SAINE : un arbre parfait, par construction
        milieu = sorted(sain)[len(sain) // 2]
        cas = [
            ("témoin NÉGATIF : arbre parfait (doit PASSER)", i1, sain, seuil, True, None),
            ("sabotage couverture : +200 classes fantômes dans le SWF (doit ROUGIR)",
             i1 | {f"fantome.pkg.Classe{i}" for i in range(200)}, sain, seuil, False, "couverture"),
            ("sabotage invention : +1 classe dans l'arbre absente du SWF (doit ROUGIR)",
             i1, sain | {"invente.par.larbre.Classe"}, seuil, False, "invention"),
            ("sabotage témoin : un témoin inventé injecté des deux côtés (doit ROUGIR)",
             i1 | {TEMOINS_INVENTES[0]}, sain | {TEMOINS_INVENTES[0]}, seuil, False, "témoin"),
            (f"sabotage paquet troué : `{milieu.rsplit('.', 1)[1]}` retirée de l'arbre, seuil à 0 % "
             "(le POURCENTAGE ne peut plus refuser — seul le refus PAR PAQUET peut ; doit ROUGIR)",
             i1, sain - {milieu}, 0.0, False, "TROUÉS"),
        ]
        tout = True
        for nom, a, b, s, att, motif in cas:
            v = verdict(a, b, s)
            raisons = "; ".join(v["raisons"]) or "aucun refus"
            # le refus doit venir du BON critère : un sabotage attrapé par une autre barrière ne
            # prouve pas que la barrière visée fonctionne.
            ok = (v["vert"] == att) and (motif is None or any(motif in r for r in v["raisons"]))
            tout &= ok
            print(f"{'✅' if ok else '❌'} {nom} → {'VERT' if v['vert'] else 'ROUGE'} ; {raisons}")
        print("ÉPREUVE :", "chaque barrière mord sur SON sabotage" if tout else "VÉRIFICATION INERTE")
        sys.exit(0 if tout else 1)

    i1, n_def, blocs = instrument_1(swf)
    i2, n_fic = instrument_2(arbre)
    i1, i2 = restreindre(i1), restreindre(i2)
    v = verdict(i1, i2, seuil)
    print(f"SWF   : {swf}")
    print(f"arbre : {arbre}")
    if prefixe:
        print(f"portée: préfixe `{prefixe}` — la question posée est la COMPLÉTUDE DE CE SOUS-ARBRE")
    print(f"I1 (parseur ABC maison)  : {len(i1)} classes uniques, {blocs} blocs ABC")
    print(f"I2 (arbre .as décompilé) : {len(i2)} classes déclarées dans {n_fic} fichiers")
    print(f"couverture I2 ⊇ I1       : {v['inter']}/{len(i1)} = {v['couverture']:.2%} (seuil {seuil:.0%})")
    print(f"manquantes (I1∖I2)       : {len(v['manquants'])}")
    for m in v["manquants"][:n_show]:
        print(f"    - {m}")
    if len(v["manquants"]) > n_show:
        print(f"    … et {len(v['manquants'])-n_show} autres")
    print(f"paquets TROUÉS           : {len(v['troues'])}")
    for p, cs in sorted(v["troues"].items()):
        print(f"    - {p} : {len(cs)} manquante(s) — " + ", ".join(c.rsplit('.', 1)[1] for c in cs[:4]))
    print(f"inventées (I2∖I1)        : {len(v['inventes'])}"
          + ("" if not v["inventes"] else " — " + ", ".join(v["inventes"][:5])))
    print(f"VERDICT : {'🟢 VERT' if v['vert'] else '🔴 ROUGE'}")
    for r in v["raisons"]:
        print(f"  refus : {r}")
    sys.exit(0 if v["vert"] else 1)


if __name__ == "__main__":
    main()
