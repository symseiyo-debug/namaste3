# Obtenir le client — la bonne build, pas la dernière

*How to get the exact client build an emulator targets — not just the latest one.*

> Document public, pour la communauté Dofus 3 en général — pas seulement pour ce dépôt. Il répond à
> une question qui revient tout le temps et qui n'a, à notre connaissance, jamais été écrite : **où
> trouver une build précise du client, ancienne, quand le launcher officiel ne sert que celle du
> jour ?**

---

## 1. Pourquoi la build compte

Le client Dofus 3 est en Unity/IL2CPP. Chaque message de son protocole porte un nom **obfusqué de
trois lettres**, et ce nom **n'a aucune stabilité entre deux versions majeures**. Un émulateur écrit
pour une build donnée parle un vocabulaire qui n'a **pas de rapport** avec celui de la build
suivante.

Ce n'est pas une supposition : c'est mesuré dans ce dépôt. En confrontant des tables d'opcodes
tierces aux nôtres sur des versions majeures différentes, **596 opcodes comparables donnent 0
accord et 51 contradictions** (voir la section « Ce qui ne marche pas encore » du [README](../README.md)
et la partie 3 de [METHODE.md](METHODE.md)). Un nom qui désigne un message dans une build en désigne
un **autre** dans la suivante — un opcode faux produit du protobuf *parfaitement valide*, donc rien
ne plante, l'écran reste juste vide ou faux.

La bonne nouvelle est symétrique : entre deux versions **voisines** (mesuré sur 3.6.10.10 →
3.6.10.11), la rotation est **nulle sur 2 169 identités**. Un correctif ne casse rien ; c'est le
**saut de version majeure** qui coûte.

**Conséquence directe** : un émulateur ne fonctionne qu'avec le client de la build qu'il vise, à
l'exclusion de toute autre. Se tromper de build ne donne pas une erreur claire — ça donne un client
qui se connecte, envoie des messages, et un jeu qui ne répond pas comme attendu, ou pas du tout.

---

## 2. Pourquoi le launcher officiel ne suffit pas

Le launcher officiel d'Ankama télécharge la build **du jour**, point. Ce n'est pas un choix
arbitraire de leur part : c'est la seule chose que leur système de distribution expose facilement,
et pour un joueur qui veut juste jouer à Dofus, c'est très bien.

Le problème apparaît pour qui veut faire tourner un client contre un serveur communautaire ou un
émulateur : ce serveur vise presque toujours une build **antérieure** à celle du jour, souvent de
plusieurs versions majeures. Le launcher ne propose aucun moyen de choisir une build ancienne.

---

## 3. La méthode — deux instruments, deux rôles

La méthode documentée ici vient du dépôt **[JondoEmu](https://github.com/Keka-Bron/JondoEmu)**
(module `Jondo.Unity.Reversing/Cytrus.cs`), qui a le premier posé et outillé le problème pour Dofus
3. Ce qui suit est vérifié directement dans son code.

### 3.1 Le CDN d'Ankama sert encore les anciennes builds

Ankama distribue le jeu par un CDN public :

```
https://cytrus.cdn.ankama.com
```

*(`Jondo.Unity.Reversing/Cytrus.cs:34`)* — c'est le canal que suit le launcher officiel lui-même,
avec les paramètres suivants pour Dofus 3 sur Windows : `game=dofus`, `platform=windows`,
`release=dofus3` *(`Cytrus.cs:50`)*. Une build s'y demande sous la forme
`.../dofus/releases/dofus3/windows/<version>.manifest` *(`Cytrus.cs:163-164`)*, et les fichiers
eux-mêmes vivent dans des paquets adressables par plage d'octets sous `.../dofus/bundles/...`
*(`Cytrus.cs:343`)*. Ce même hôte est vérifié indépendamment dans ce dépôt, par un script qui n'a
aucun lien avec JondoEmu (voir §5) : `tools/community/chaine/obtenir_build.sh:87`.

Les manifestes anciens n'ont **pas été retirés**. Le CDN les sert toujours — le problème n'est donc
pas que les fichiers ont disparu, c'est de **savoir quoi leur demander**.

### 3.2 Le piège : le fichier des versions officielles ne connaît que le présent

Ankama publie un fichier `cytrus.json` qui liste, entre autres, les versions disponibles par jeu et
par plateforme. Sauf que ce fichier est **écrasé à chaque mise à jour** : à un instant donné, il ne
contient que la ou les versions **du jour**, autour de 3,5 Ko *(`Cytrus.cs:38-41`)*. Interroger ce
fichier ne donne donc **jamais** une build ancienne — il n'en garde pas la trace.

### 3.3 La clé : une archive communautaire qui, elle, se souvient

Le dépôt communautaire **[dofera/cytrus](https://github.com/dofera/cytrus)** résout exactement ce
problème : au lieu d'écraser le fichier à chaque publication, il le **fusionne**. Le résultat,
`cytrus.json` sur sa branche `main`, conserve la trace d'**environ 200 versions Windows publiées
depuis la 3.0.1.1** *(`Cytrus.cs:36-41`)* :

```
https://raw.githubusercontent.com/dofera/cytrus/main/cytrus.json
```

Sans cette liste, il est impossible de savoir quels noms de version demander au CDN — les fichiers
sont là, mais leurs noms exacts (`6.0_3.6.10.10`, par exemple, avec son préfixe de branche) ne se
devinent pas. Avec elle, on sait exactement quoi demander, et le CDN (§3.1) répond.

**La méthode complète tient donc en deux instruments** : l'archive dit *quelles versions ont existé
et comment elles se nomment* ; le CDN officiel sert *les fichiers eux-mêmes*. Ni l'un ni l'autre seul
ne suffit.

---

## 4. Ne pas télécharger le client entier

Un client Dofus 3 installé pèse environ 12 Go. Un émulateur, pour tourner, n'a besoin que du binaire
et de ses métadonnées — trois fichiers, environ 130 Mo au total, sur les 12 Go de l'installation
complète *(`Jondo.Unity.ProtocolBuilder/Program.cs:537-541`)*. Le manifeste d'une build décrit
précisément dans quel paquet et à quel décalage d'octets vit chaque morceau de chaque fichier ; les
paquets acceptant les requêtes par plage, on peut demander exactement ces octets et rien d'autre.

C'est ce que fait, dans JondoEmu, la commande outillée :

```
bajar --lista                    # quelles versions le CDN sert encore, parmi celles de l'archive
bajar <depuis> <jusqu'à> [dossier]   # les clients intermédiaires de la chaîne, sans rien de trop
```

*(`Jondo.Unity.ProtocolBuilder/Program.cs:40-41` pour l'aide, `:65` pour le point d'entrée,
`:568-569` pour l'usage exact, `:544-597` pour l'implémentation.)* `bajar --lista` interroge le CDN
version par version (une requête `HEAD` sur le manifeste, `Cytrus.cs:156-161`) pour dire lesquelles
sont encore servies ; `bajar <depuis> <jusqu'à>` télécharge, pour chaque version de la plage, un
dossier séparé ne contenant que `GameAssembly.dll`, `global-metadata.dat` et `UnityPlayer.dll`
*(`Program.cs:549-551`)*.

---

## 5. Cet outil, dans ce dépôt

Ce dépôt a son propre script pour la même famille de problème :
`tools/community/chaine/obtenir_build.sh`. Il ne réinvente pas la roue de JondoEmu — il s'appuie sur
un autre outil communautaire, **[cytrus-v6](https://github.com/ledouxm/cytrus-v6)**, et sait déjà lui
seul appliquer le préfixe de branche que le CDN exige (mesuré le 05/09/2026 : une version nue comme
`3.6.4.3` rend `403`, `6.0_3.6.4.3` rend `200` — voir le script pour le détail).

**La différence entre les deux, et pourquoi les deux sont utiles** : `obtenir_build.sh` sait
télécharger une build **dont on connaît déjà le numéro exact** — c'est le cas courant pour ce dépôt,
qui cible en permanence 3.6.10.10. Mais il ne résout pas, seul, la question de départ de ce document :
« quelles builds anciennes ont existé, et sous quel nom exact ? » — sa propre documentation renvoie,
pour ça, au `cytrus.json` **du jour**, donc au même piège qu'en §3.2. C'est l'archive `dofera/cytrus`
(§3.3), consultée ici par JondoEmu, qui répond à cette question précise. Un débutant qui ne connaît
que le nom de l'émulateur qu'il veut essayer commence donc par l'archive, pas par ce script.

---

## 6. Cadre légal et éthique

Dofus est un jeu accessible gratuitement, dont le client se télécharge et s'installe librement via le
launcher officiel d'Ankama. La méthode décrite ici emprunte **le même canal officiel** — le CDN public
d'Ankama — pour obtenir une build antérieure plutôt que la plus récente ; elle ne contourne aucune
protection et n'accède à rien qu'Ankama ne serve pas déjà publiquement.

**Ce dépôt ne contient, et ne contiendra, aucun fichier du client** — ni binaire, ni dump, ni donnée
extraite (voir le README). Ce document explique une méthode et cite ses sources ; il ne redistribue
rien.

Dofus et son client appartiennent à Ankama. Ce projet reste technique et communautaire, sans marque
détournée ni ambition commerciale.

---

## 7. Crédits

La méthode décrite ici — CDN officiel + archive communautaire des versions, téléchargement par
plage — vient du dépôt **[Keka-Bron/JondoEmu](https://github.com/Keka-Bron/JondoEmu)**
(`Jondo.Unity.Reversing/Cytrus.cs`, `Jondo.Unity.ProtocolBuilder/Program.cs`). Voir aussi
[CREDITS.md](../CREDITS.md) pour l'ensemble des projets et outils tiers cités dans ce dépôt, dont
**[dofera/cytrus](https://github.com/dofera/cytrus)** et **[ledouxm/cytrus-v6](https://github.com/ledouxm/cytrus-v6)**.

---

## English summary

Dofus 3 emulators only work against the exact client build they target: message opcodes are
obfuscated three-letter names, **fully reshuffled between major versions** — measured in this
repository at **0 agreement and 51 contradictions across 596 comparable opcodes** — while rotation
between *adjacent* builds is **zero across 2 169 identities**. Ankama's official launcher only ever
serves **today's** build, so a beginner who downloads through it gets a client that cannot speak the
emulator's protocol, with no clear error to explain why.

The fix, documented in **[Keka-Bron/JondoEmu](https://github.com/Keka-Bron/JondoEmu)**
(`Jondo.Unity.Reversing/Cytrus.cs`): Ankama's CDN (`cytrus.cdn.ankama.com`) still serves old build
manifests, but Ankama's own `cytrus.json` is overwritten on every release and only ever lists
**today's** versions (~3.5 KB). The community-maintained archive
**[dofera/cytrus](https://github.com/dofera/cytrus)** merges rather than overwrites, preserving
roughly **200 published Windows versions since 3.0.1.1** — the only way to know which version names
to ask the CDN for. With that list in hand, a client build's few required files (~130 MB out of a
~12 GB install) can be fetched directly, by byte range, rather than downloading the whole client.
JondoEmu exposes this as `bajar --lista` (which versions the CDN still serves) and
`bajar <from> <to> [folder]` (fetch a range of intermediate builds, only the necessary files).

This repository ships its own build-fetch script,
`tools/community/chaine/obtenir_build.sh`, built on a different community tool
([cytrus-v6](https://github.com/ledouxm/cytrus-v6)) — but it expects the version number already, and
falls into the same "today only" trap if you ask it to discover old versions on its own. The archive
is what actually answers "which old builds exist," which is the beginner's real starting question.

No client file, binary dump, or extracted game data is distributed by this repository or this
document — this explains a method and cites its sources, nothing more. Dofus and its client are the
property of Ankama; downloads described here go through Ankama's own official CDN.
