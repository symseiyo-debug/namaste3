#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : Bibliothèque de LECTURE du dump Il2CppInspector-Redux (`cs/il2cpp.cs`).
    Reconstruit l'arbre des types protobuf du client Dofus 3.x : messages
    (`class X : IMessage<X>`), énumérations, champs (numéro + type résolu),
    imbrication et `oneof`. Aucune écriture, aucun jugement sémantique.
    / Read-only library that rebuilds the protobuf type tree from the IL2CPP dump.

POURQUOI (05/09/2026, maillon A6 de `tools/community/chaine/CHAINE.md`, déclaré
    MANQUANT) : loi L6 du cahier — « l'opcode 3 lettres EST le nom de classe
    obfusqué, re-brassé à chaque build ». Donc le `.proto` et la table de
    dispatch se REGÉNÈRENT depuis le dump à chaque build ; rien ne s'écrit à la
    main. `generer_proto.py` et `generer_dispatch.py` lisent tous deux le dump :
    un seul lecteur, sinon deux lecteurs divergent en silence.
    Trois pièges MESURÉS le 05/09 sur ce dump, qui sont la raison de ce fichier :
      1. Le décompilateur échappe un identifiant qui heurte un mot-clé C# :
         `public const int @enum = 1;` dans la classe `jin`. Un regex `\\w+`
         rend 6277 champs au lieu de 6278 — un compte plausible, faux d'un.
      2. Une VRAIE classe protobuf s'appelle littéralement `int`
         (`il2cpp.cs:895280`). Le token `int` est donc ambigu en position de
         type. Mesure : 0 champ de type `int` (la classe) dans la reconstruction
         indépendante de Jondo → on lit `int` comme `int32`, et
         `gate-proto-sync.py` re-mesure cette absence.
      3. Le texte `namespace X` de ce décompilateur ne délimite RIEN (mesuré par
         le matcher v3, RAPPORT-MATCHER-V3.md §2) : l'appartenance à un
         assembly se lit par `TypeDefIndex` contre les plages `// Image N:`,
         JAMAIS par le texte du namespace.

COMMENT LANCER : module, pas exécutable.
    from _lib_dump import charger_dump
    d = charger_dump("…/cs/il2cpp.cs")

GATE : pas de gate propre — cette bibliothèque est éprouvée à travers
    `gate-proto-sync.py --epreuve`, qui rejoue ses sorties et les sabote.
    Deux invariants qu'elle asserte elle-même à la lecture (`Dump.controles`) :
    (a) nombre de champs par la voie des `const int` == nombre par la voie des
    propriétés de données ; (b) tout type cité est résolu ou nommé inconnu.
"""

import hashlib
import os
import re
from dataclasses import dataclass, field as _dc_field
from typing import Dict, List, Optional

# ── Constantes sourcées ───────────────────────────────────────────────────────
# Les deux assemblies qui portent le protocole de jeu. Mesuré le 05/09 :
# Game.dll = 2169 classes `IMessage<self>`, Connection.dll = 37, total 2206 —
# le même 2206 que le matcher v3 (RAPPORT-MATCHER-V3.md §2), par un autre chemin.
ASSEMBLIES_PROTOCOLE = (
    "Ankama.Dofus.Protocol.Game.dll",
    "Ankama.Dofus.Protocol.Connection.dll",
)

# Types C# scalaires rencontrés en position de champ. Inventaire EXHAUSTIF
# mesuré le 05/09 sur les 6278 champs des 2206 messages : aucun autre scalaire
# n'apparaît (ni `double`, ni `ulong`, ni `ByteString`).
# ⚠️ `int`/`uint`/`long` ne disent PAS le type de fil : protobuf distingue
# int32/sint32/sfixed32, que le C# généré compile tous vers `int`. Le choix
# ci-dessous est donc DÉDUIT, et c'est le même que celui de Jondo.
SCALAIRES_CS_VERS_PROTO = {
    "int": "int32",
    "long": "int64",
    "uint": "uint32",
    "ulong": "uint64",
    "bool": "bool",
    "float": "float",
    "double": "double",
    "string": "string",
    "ByteString": "bytes",
}

# Types Google bien connus référencés par le protocole (enveloppe `Any`).
BIEN_CONNUS = {
    "Any": ("google.protobuf.Any", "google/protobuf/any.proto"),
    "Timestamp": ("google.protobuf.Timestamp", "google/protobuf/timestamp.proto"),
    "Duration": ("google.protobuf.Duration", "google/protobuf/duration.proto"),
    "Empty": ("google.protobuf.Empty", "google/protobuf/empty.proto"),
}

# Champs de plomberie du code généré par protoc : jamais des champs de protocole.
PLOMBERIE = ("MessageParser<", "MessageDescriptor", "UnknownFieldSet", "FieldCodec<")

_RE_STR = re.compile(r'"(?:\\.|[^"\\])*"')
_RE_CHR = re.compile(r"'(?:\\.|[^'\\])*'")
_RE_IMAGE = re.compile(r"^// Image (\d+): ([\w\.]+) - Assembly: .* - Types (\d+)-(\d+)")
_RE_CLASSE = re.compile(r"^\s*(?P<mods>[\w\s]*?)\b(?:class|struct|interface)\s+(?P<nom>@?[\w`]+)\s*(?::\s*(?P<base>.+?))?\s*$")
_RE_ENUM = re.compile(r"^\s*public\s+enum\s+(?P<nom>@?\w+)\s*$")
_RE_TDI = re.compile(r"TypeDefIndex:\s*(\d+)")
# `@?` : indispensable — `public const int @enum = 1;` existe (cf. en-tête, piège 1).
_RE_CONST = re.compile(r"^\s*public const int (?P<nom>@?\w+) = (?P<val>-?\d+);")
_RE_CHAMP = re.compile(
    r"^\s*(?P<mods>(?:private|public|internal|protected)(?:\s+static)?(?:\s+readonly)?)"
    r"\s+(?P<type>.+?)\s+(?P<nom>@?\w+);\s*//\s*0x(?P<off>[0-9A-Fa-f]+)"
)
_RE_PROP = re.compile(
    r"^\s*(?:public|private|internal|protected)?\s*(?:static\s+)?(?:override\s+)?"
    r"(?P<type>[\w\.<>,\[\]\s]+?)\s+(?P<nom>@?[\w\.]+)\s*\{\s*get;(?P<setter>\s*set;)?\s*\}\s*$"
)
_RE_VAL_ENUM = re.compile(r"^\s*(?P<nom>@?\w+)\s*=\s*(?P<val>-?\d+),?\s*$")


def depurer(ligne: str) -> str:
    """Retire chaînes et commentaire de fin pour compter les accolades sans se faire piéger.
    / Strips string literals and trailing comment so brace counting is not fooled by `{` inside text."""
    ligne = _RE_CHR.sub("''", _RE_STR.sub('""', ligne))
    i = ligne.find("//")
    return ligne[:i] if i >= 0 else ligne


def chemin_stable(chemin: str) -> str:
    """Rend le chemin RELATIF à la racine du chantier. Un artefact qui recopierait le chemin
    tel que l'appelant l'a tapé changerait de sha256 selon le répertoire courant : le rejeu
    byte-identique deviendrait intestable, et un contributeur qui régénère depuis chez lui
    obtiendrait un fichier « différent » sans qu'une seule donnée ait bougé.
    / Returns the path relative to the chantier root, so the artifact does not depend on how
      the caller spelled it and byte-identical replay stays testable."""
    racine = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    absolu = os.path.abspath(chemin)
    return os.path.relpath(absolu, racine) if absolu.startswith(racine + os.sep) else absolu


def sha256_fichier(chemin: str, bloc: int = 1 << 20) -> str:
    """Empreinte d'un fichier — c'est elle qui rend une régénération PROUVABLEMENT identique.
    / File digest: the only thing that makes a regeneration provably byte-identical."""
    h = hashlib.sha256()
    with open(chemin, "rb") as fh:
        for morceau in iter(lambda: fh.read(bloc), b""):
            h.update(morceau)
    return h.hexdigest()


@dataclass
class Champ:
    """Un champ protobuf : son NUMÉRO et son TYPE sont lus (VÉRIFIÉ) ; son nom est le
    token obfusqué de la propriété. / One protobuf field; number and type are read, name is obfuscated."""
    numero: int
    nom: str                    # token obfusqué de la propriété (celui que Jondo écrit aussi)
    type_cs: str                # type tel qu'écrit par le décompilateur
    label: str                  # "singular" | "repeated" | "map" | "oneof"
    ligne: int                  # ligne du `const int` dans il2cpp.cs
    oneof: Optional[str] = None  # nom du groupe oneof, quand le champ y appartient
    type_proto: str = ""        # rempli par la résolution
    cle_map: str = ""           # pour un map, le type de clé résolu
    presence: bool = False      # `optional` de proto3 (présence explicite) — cf. `props_has`


@dataclass
class Type:
    """Un type du dump : message protobuf, énumération, ou conteneur `Types` de protoc.
    / One dump type: protobuf message, enum, or protoc's transparent `Types` container."""
    nom: str
    genre: str                  # "message" | "enum" | "conteneur" | "autre"
    chemin_cs: str
    ligne: int
    tdi: Optional[int]
    assembly: str = "?"
    parent: Optional["Type"] = None
    enfants: List["Type"] = _dc_field(default_factory=list)
    champs: List[Champ] = _dc_field(default_factory=list)
    valeurs: List[tuple] = _dc_field(default_factory=list)   # (nom, valeur) pour un enum
    membres: List[tuple] = _dc_field(default_factory=list)   # (no_ligne, texte brut)

    @property
    def chemin_proto(self) -> str:
        """Chemin proto : identique au chemin C# mais SANS les conteneurs `Types`, qui sont
        une invention du générateur C# et n'existent pas dans le `.proto` d'origine.
        / Proto path = C# path minus protoc's `Types` containers, which are a C#-ism."""
        bouts, t = [], self
        while t is not None:
            if t.genre != "conteneur":
                bouts.append(t.nom)
            t = t.parent
        return ".".join(reversed(bouts))


class Dump:
    """Le dump lu : index des types par chemin C#, liste des messages, contrôles internes.
    / The parsed dump: types indexed by C# path, message list, self-checks."""

    def __init__(self, chemin: str):
        # Le sha256 est pris À L'OUVERTURE : c'est lui qui lie l'artefact produit à
        # l'octet exact du dump lu. / Digest taken at open time, binding output to input.
        self.chemin = chemin
        self.sha256 = sha256_fichier(chemin)
        self.images: List[tuple] = []
        self.types: Dict[str, Type] = {}
        self.racines: List[Type] = []
        self.messages: List[Type] = []
        self.controles: Dict[str, int] = {}

    def assembly_de(self, tdi: Optional[int]) -> str:
        """Assembly d'un type par son TypeDefIndex — jamais par le texte `namespace`, qui ne
        délimite rien dans ce décompilateur (mesuré, cf. en-tête piège 3).
        / Assembly by TypeDefIndex, never by the `namespace` text, which delimits nothing here."""
        if tdi is None:
            return "?"
        for nom, a, b in self.images:
            if a <= tdi <= b:
                return nom
        return "?"

    def resoudre(self, expr: str, portee: Type) -> str:
        """Résout un type C# écrit dans une portée donnée vers son chemin proto complet.
        Applique la règle C# : on cherche le premier segment de l'intérieur vers l'extérieur.
        / Resolves a C# type expression to its full proto path, C#-style innermost-outward lookup."""
        expr = expr.strip()
        if expr in SCALAIRES_CS_VERS_PROTO:
            return SCALAIRES_CS_VERS_PROTO[expr]
        if expr in BIEN_CONNUS:
            return BIEN_CONNUS[expr][0]
        bouts = expr.split(".")
        courant = portee
        while courant is not None:
            cible = self._descendre(courant, bouts)
            if cible is not None:
                return cible.chemin_proto
            courant = courant.parent
        # Portée globale : le dump n'a pas de namespace fiable, on tente le chemin nu.
        cible = self.types.get(expr)
        if cible is not None:
            return cible.chemin_proto
        return ""   # non résolu — l'appelant décide quoi en dire, on n'invente pas

    @staticmethod
    def _descendre(depuis: Type, bouts: List[str]) -> Optional[Type]:
        """Descend une suite de segments dans les enfants d'un type. / Walks segments down a type's children."""
        courant = depuis
        for i, b in enumerate(bouts):
            suivant = next((e for e in courant.enfants if e.nom == b), None)
            if suivant is None:
                # premier segment : peut aussi désigner le type lui-même
                if i == 0 and courant.nom == b:
                    continue
                return None
            courant = suivant
        return courant if courant is not depuis or bouts == [depuis.nom] else courant


def _est_conteneur_types(attrs: List[str], mods: str) -> bool:
    """Reconnaît le conteneur `Types` de protoc, obfusqué comme le reste (ex. `jrt` dans `jru`).
    Marqueur fiable : classe statique portant l'attribut `[GeneratedCode("protoc", null)]`.
    / Recognises protoc's `Types` container, obfuscated like everything else."""
    return "static" in mods and any('GeneratedCode("protoc"' in a for a in attrs)


def charger_dump(chemin: str, assemblies=ASSEMBLIES_PROTOCOLE) -> Dump:
    """Lit le dump entier et rend l'arbre des types protocolaires, champs résolus.
    / Parses the whole dump and returns the protocol type tree with resolved fields."""
    d = Dump(chemin)
    with open(chemin, encoding="utf-8-sig", errors="replace") as fh:
        lignes = fh.read().split("\n")

    for l in lignes[:2000]:                       # l'en-tête des images tient dans le début du fichier
        m = _RE_IMAGE.match(l)
        if m:
            d.images.append((m.group(2), int(m.group(3)), int(m.group(4))))

    _balayer(d, lignes)
    _extraire_champs(d, assemblies)
    _extraire_valeurs_enum(d, assemblies)
    return d


def _extraire_valeurs_enum(d: Dump, assemblies) -> None:
    """Lit les valeurs des énumérations protocolaires. Ce sont elles qui portent le SENS
    métier côté client (états, raisons de refus) : les perdre rendrait le `.proto`
    compilable et pourtant inutilisable pour écrire un serveur.
    / Reads protocol enum values; without them the .proto compiles but says nothing."""
    d.controles["enums"] = 0
    d.controles["valeurs_enum"] = 0
    for t in d.types.values():
        if t.genre != "enum" or t.assembly not in assemblies:
            continue
        for _, brut in t.membres:
            m = _RE_VAL_ENUM.match(depurer(brut))
            if m:
                t.valeurs.append((m.group("nom").lstrip("@"), int(m.group("val"))))
        d.controles["enums"] += 1
        d.controles["valeurs_enum"] += len(t.valeurs)


def _balayer(d: Dump, lignes: List[str]) -> None:
    """Balayage à pile : reconstruit l'imbrication réelle par comptage d'accolades.
    / Stack scan: rebuilds real nesting by brace counting, the only reliable structure here."""
    prof, pile, attrs, attente = 0, [], [], None
    for no, brut in enumerate(lignes, 1):
        l = depurer(brut)
        st = l.strip()
        if st.startswith("["):
            # ⚠️ on empile la ligne BRUTE : `depurer()` vide les chaînes, or le marqueur
            # cherché est justement dans une chaîne — `[GeneratedCode("protoc", null)]`.
            # / Raw line on purpose: the marker we need lives inside a string literal.
            attrs.append(brut.strip())
            continue
        m_enum, m_cls = _RE_ENUM.match(l), None
        if not m_enum:
            m_cls = _RE_CLASSE.match(l)
        if m_enum or m_cls:
            mods = (m_cls.group("mods").strip() if m_cls else "public")
            nom = (m_enum or m_cls).group("nom")
            base = (m_cls.group("base") if m_cls else "") or ""
            tdi = _RE_TDI.search(brut)
            genre = "enum" if m_enum else ("conteneur" if _est_conteneur_types(attrs, mods) else "autre")
            if m_cls and re.search(r"\bIMessage<" + re.escape(nom) + r">", base):
                genre = "message"
            attente = Type(nom=nom, genre=genre, chemin_cs="", ligne=no,
                           tdi=int(tdi.group(1)) if tdi else None)
            attente_attrs = list(attrs)
            attente.membres = []
            attrs = []
            attente.__dict__["_attrs"] = attente_attrs
            continue
        if st.startswith("namespace "):
            attente = None          # les namespaces ne délimitent rien ici : on les ignore
            attrs = []
            continue
        ouv, fer = l.count("{"), l.count("}")
        if ouv and ouv != fer and attente is not None:
            _empiler(d, pile, attente, prof)
            attente = None
            prof += ouv - fer
            _depiler(pile, prof)
            continue
        if ouv != fer:
            attente = None
            prof += ouv - fer
            _depiler(pile, prof)
            continue
        if pile:
            pile[-1][0].membres.append((no, brut))
        attrs = []


def _empiler(d: Dump, pile: List[tuple], t: Type, prof: int) -> None:
    """Attache un type à son parent et l'indexe. / Attaches a type to its parent and indexes it."""
    parent = pile[-1][0] if pile else None
    t.parent = parent
    t.chemin_cs = (parent.chemin_cs + "." + t.nom) if parent else t.nom
    t.assembly = d.assembly_de(t.tdi) if t.tdi is not None else (parent.assembly if parent else "?")
    if parent is not None:
        parent.enfants.append(t)
    else:
        d.racines.append(t)
    d.types[t.chemin_cs] = t
    if t.genre == "message":
        d.messages.append(t)
    pile.append((t, prof))


def _depiler(pile: List[tuple], prof: int) -> None:
    """Referme les portées dont l'accolade vient de se fermer. / Closes scopes whose brace just closed."""
    while pile and pile[-1][1] >= prof:
        pile.pop()


def _extraire_champs(d: Dump, assemblies) -> None:
    """Apparie `const int` (le NUMÉRO) et propriété publique (le NOM et le TYPE), dans l'ordre.
    Les deux voies sont comptées séparément : leur désaccord est un CONTRÔLE, pas un détail.
    / Pairs `const int` (number) with public property (name+type) in order; the two counts are a check."""
    d.controles = {"consts": 0, "props_donnee": 0, "props_has": 0, "props_case": 0,
                   "messages": 0, "desaccords": 0, "types_non_resolus": 0}
    for t in d.messages:
        if t.assembly not in assemblies:
            continue
        d.controles["messages"] += 1
        consts, champs_bruts, props = [], [], []
        for no, brut in t.membres:
            l = depurer(brut)
            mc = _RE_CONST.match(l)
            if mc:
                consts.append((mc.group("nom").lstrip("@"), int(mc.group("val")), no))
                continue
            mp = _RE_PROP.match(l)
            if mp:
                props.append((mp.group("type").strip(), mp.group("nom").lstrip("@"),
                              bool(mp.group("setter")), no))
                continue
            mf = _RE_CHAMP.match(brut)
            if mf:
                champs_bruts.append((mf.group("mods"), mf.group("type").strip(), mf.group("nom")))
        groupes, cases = _groupes_oneof(t)
        donnees = []
        for typ, nom, setter, no in props:
            if any(typ.startswith(p) or p in typ for p in PLOMBERIE):
                continue
            if typ == "bool" and not setter:
                # `HasXxx` de proto3 `optional` : pas un champ, mais la MARQUE de présence
                # explicite du champ juste au-dessus (protoc les émet accolés). Sans elle, le
                # serveur n'écrit pas une valeur par défaut que le client attend.
                # / Not a field: the explicit-presence marker of the field right above it.
                d.controles["props_has"] += 1
                if donnees:
                    donnees[-1] = donnees[-1][:3] + (True,)
                continue
            if typ in cases:                      # `XxxCase` d'un oneof : pas un champ
                d.controles["props_case"] += 1
                continue
            donnees.append((typ, nom, no, False))
        d.controles["consts"] += len(consts)
        d.controles["props_donnee"] += len(donnees)
        if len(donnees) != len(consts):
            d.controles["desaccords"] += 1
            continue                              # message non apparié : il ne portera aucun champ
        for i, (cst, num, no) in enumerate(consts):
            typ_cs, nom_prop, _, presence = donnees[i]
            c = _batir_champ(d, t, num, nom_prop, typ_cs, no, groupes.get(num))
            # Un `HasXxx` accolé à un membre SCALAIRE de oneof n'est PAS un `optional` de
            # proto3 : le membre d'un oneof a déjà une présence explicite par construction,
            # et protoc REFUSE `optional` à l'intérieur d'un oneof. Mesuré le 05/09 : les 386
            # `HasXxx` se partagent en 348 vrais `optional` et 38 accesseurs de oneof scalaire
            # (dans `hex`, les 4 bool suivent exactement les 4 membres `int`/`long`, et aucun
            # membre de type message n'en a). Sans cette distinction, on écrirait 38 `optional`
            # illégaux et le `.proto` cesserait de compiler.
            # / A `HasXxx` on a scalar oneof member is not proto3 `optional`; protoc forbids it there.
            if c.oneof:
                d.controles["props_has_oneof"] = d.controles.get("props_has_oneof", 0) + int(presence)
                presence = False
            c.presence = presence
            t.champs.append(c)


def _groupes_oneof(t: Type):
    """Rend ({numéro -> nom du groupe oneof}, {types d'enum de cas}) en PARCOURANT la section
    « Fields » dans l'ordre du fichier. Forme émise par protoc, mesurée le 05/09 : les
    `const int` d'un même oneof se suivent SANS champ de stockage entre eux, puis vient
    `private object <stockage>;` suivi de `private <EnumDeCas> <x>;`. Un champ ordinaire,
    lui, est suivi immédiatement de son propre champ de stockage.
    / Walks the Fields section in file order: a oneof shows as consecutive `const int`s
    followed by one shared `private object` storage plus its case-enum field."""
    tampon, groupes, cases = [], {}, set()
    attend_cas = False
    for no, brut in t.membres:
        l = depurer(brut)
        mc = _RE_CONST.match(l)
        if mc:
            tampon.append(int(mc.group("val")))
            attend_cas = False
            continue
        mf = _RE_CHAMP.match(brut)
        if not mf:
            continue
        mods, typ, nom = mf.group("mods"), mf.group("type").strip(), mf.group("nom")
        if "static" in mods:
            continue                              # codec de `repeated`/`map` : pas un stockage
        if attend_cas:                            # le champ qui suit un `object` est l'enum de cas
            cases.add(typ)
            attend_cas = False
            continue
        if typ == "object":
            for num in tampon:                    # tout le tampon appartient à ce oneof
                groupes[num] = nom
            tampon, attend_cas = [], True
            continue
        tampon = tampon[1:] if tampon else tampon  # champ ordinaire : consomme un const
    return groupes, cases


def _batir_champ(d: Dump, t: Type, num: int, nom: str, typ_cs: str, ligne: int,
                 oneof: Optional[str]) -> Champ:
    # (commentaire d'intention ci-dessous / intent comment below)
    """Construit un champ en résolvant son type ; `repeated`/`map` se lisent sur le type C#.
    / Builds a field, resolving its type; repeated/map are read off the C# generic."""
    label, cle = "singular", ""
    interne = typ_cs
    if typ_cs.startswith("RepeatedField<"):
        label, interne = "repeated", typ_cs[len("RepeatedField<"):-1].strip()
    elif typ_cs.startswith("MapField<"):
        label = "map"
        k, v = typ_cs[len("MapField<"):-1].split(",", 1)
        cle = d.resoudre(k.strip(), t) or k.strip()
        interne = v.strip()
    resolu = d.resoudre(interne, t)
    if not resolu:
        d.controles["types_non_resolus"] += 1
        resolu = "<INCONNU:" + interne + ">"
    c = Champ(numero=num, nom=nom, type_cs=typ_cs,
              label="oneof" if oneof else label, ligne=ligne, oneof=oneof)
    c.type_proto, c.cle_map = resolu, cle
    if oneof and typ_cs.startswith(("RepeatedField<", "MapField<")):
        c.label = label            # un oneof ne peut porter ni repeated ni map : on garde le vrai
    return c
