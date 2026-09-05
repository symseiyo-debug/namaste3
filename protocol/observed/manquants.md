# Ce que le client demande et qu'un serveur doit fournir

> **La partie la plus utile de ce dossier, et la plus rare.**
> Ces opcodes sont envoyés par le client officiel et restent **sans réponse**
> sur l'émulateur de référence. Chacun désigne donc une fonctionnalité qu'un
> serveur doit implémenter — avec son adresse exacte.
> Obtenus en cliquant méthodiquement sur ce qui ne fonctionne pas.

## Méthode
Une action à la fois. Quand le client **envoie** un message et que rien ne
revient dans les secondes qui suivent, la fonction est absente côté serveur.
Le client, lui, fait son travail : il demande correctement.

## Trois natures de « ça ne marche pas » — à ne pas confondre
| Observation | Diagnostic |
|---|---|
| le client **envoie**, rien ne revient | fonction **absente du serveur** → à implémenter |
| le client **n'envoie rien** | écran **purement local**, ou **prérequis non rempli** |
| le client envoie et **insiste** (répétitions) | il attend une réponse, l'absence est anormale |

## Fonctions absentes, par famille
| Famille | Opcodes envoyés sans réponse |
|---|---|
| Carte du monde | `lzh` |
| Stockage — tout transférer | `kez` |
| Poser un objet au sol | `iur` |
| Kolizéum | `lux` `lww` `kjx` `kke` |
| Recherche de groupe | `kxh` `jmu` `jpr` `jnv` `jop` |
| Boutique / codes cadeaux | `jwm` `jth` `lrf` |
| Profil du personnage | `jlk` `jlu` `jjm` `hvx` `ibr` `hym` |
| Succès | `jlh` `mfe` `mfp` `mff` |

**`kke` (recherche de groupe)** est confirmé par répétition : 4 clics → 4 envois
de 44 o exactement. Aucune ambiguïté possible.

## Écrans qui ne parlent JAMAIS au serveur — mesuré à 0 trafic
Grimoire de sorts et ses filtres · guide d'aventure · encyclopédie complète
(bestiaire, équipement, consommables, ressources, cosmétiques) · composition
d'une annonce (type, donjon, succès ciblés) · fermeture de fenêtre.

**Conséquence de conception** : les données de référence sont **embarquées dans
le client**. Le serveur n'envoie jamais de contenu de jeu — seulement l'état de
la partie. Cela réduit d'autant ce qu'un émulateur doit implémenter.

## Une mesure qui révèle une structure sans décoder
Quatorze catégories de succès, cliquées **une par une avec 3 secondes
d'intervalle**, produisent toutes un `mff` :

| Catégories (dans l'ordre d'affichage) | Taille |
|---|---|
| général, exploration, donjons, monstres, quêtes, métiers, élevage, événements | **40 o** |
| kolizéum, anomalies temporelles, songes, guilde, compagnons, La Source | **41 o** |

La coupure tombe exactement entre la 8ᵉ et la 9ᵉ catégorie. En protobuf, un
entier gagne un octet en franchissant **127** : les huit premières catégories
portent donc un identifiant ≤ 127, les six suivantes > 127.
**La structure du message se déduit de sa taille, sans jamais le décoder** — à
condition d'espacer les gestes pour que l'appariement soit certain.
