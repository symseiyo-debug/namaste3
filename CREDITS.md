# Credits & Resources

Namaste 3 exists because a lot of other people published their work first.
This document lists every reference project, community tool, and piece of
open-source tooling this project learned from or was built with, and what
each one specifically contributed. Every link below was checked against the
live GitHub repository (or, for tools without a dedicated repo, our own
project documentation) while preparing this export — nothing here is
invented.

None of these projects are affiliated with Namaste 3, and this list does not
imply their endorsement of this project.

## Dofus 3.0 reference server

- **[Keka-Bron/JondoEmu](https://github.com/Keka-Bron/JondoEmu)** — the
  reference Dofus 3.0 emulator that proved a from-scratch 3.0 server was
  feasible at all. Used throughout this project as a second, independent
  instrument to cross-check our own protocol extraction (map walkability
  semantics, opcode-to-message correspondence, capture comparison) — never
  as a source of copied code.

## Dofus 3.0 community tools and repositories

- **[dofusdude/dofus3-main](https://github.com/dofusdude/dofus3-main)** —
  automatically updating Dofus 3 data feed from the game's main channel;
  cross-referenced for build/version tracking.
- **[dofusdude/ankabuffer](https://github.com/dofusdude/ankabuffer)** —
  client for Ankama's Cytrus/asset-manifest protocol; informed how our own
  build-fetching tooling (`tools/community/chaine/obtenir_build.sh`) talks
  to Ankama's public CDN.
- **[ledouxm/cytrus-v6](https://github.com/ledouxm/cytrus-v6)** — download
  tool for Ankama games via the Cytrus CDN; the name and approach our own
  build-fetch script explicitly reuses.
- **[dofera/cytrus](https://github.com/dofera/cytrus)** — community-maintained
  archive of Ankama's `cytrus.json`, merged on every publish instead of
  overwritten, preserving roughly 200 published Windows versions since
  3.0.1.1. Ankama's own live `cytrus.json` only ever lists today's version;
  this archive is what makes it possible to name an old build at all before
  asking the CDN for it. See
  [docs/OBTENIR-LE-CLIENT.md](docs/OBTENIR-LE-CLIENT.md) for the full method,
  sourced from JondoEmu's `Jondo.Unity.Reversing/Cytrus.cs`.
- **[tikkamasala/dofus3-sniffer-tui](https://github.com/tikkamasala/dofus3-sniffer-tui)**
  — passive TCP capture + protobuf `Any`/`typeUrl` pretty-printing TUI;
  studied for its framing, opcode-to-name mapping registry, and message
  decode/render approach.
- **[tikkamasala/dofus3-public-internal](https://github.com/tikkamasala/dofus3-public-internal)**
  — recovered client-side signatures/RVA/structures for the Dofus 3.x
  native binary; cross-referenced for internal client structure.
- **[tikkamasala/dofus3-classes-matcher](https://github.com/tikkamasala/dofus3-classes-matcher)**
  — semi-supervised structural-fingerprint matcher for obfuscated classes;
  the direct methodological ancestor of this project's own
  `tools/protocol-mapping/matcher/`.
- **[ledouxm/dofus3-gatherer](https://github.com/ledouxm/dofus3-gatherer)**
  — passive npcap sniffer building a live, community-maintained protocol
  mapping across two disjoint protocol generations; one of our independent
  cross-check sources for message names and field shapes.
- **[LuaxY/dofus-unity-protocol-builder](https://github.com/LuaxY/dofus-unity-protocol-builder)**
  and **[RuinedYourLife/dofus-deobfs](https://github.com/RuinedYourLife/dofus-deobfs)**
  — protocol-schema extraction and deobfuscation tooling; measured
  byte-identical `.proto` output against `dofus3-gatherer` on a shared
  ~2024-10 snapshot, confirming the three projects trace back to the same
  underlying instrument rather than three independent measurements.
- **[AlpaGit/Bubble.D3.Bot](https://github.com/AlpaGit/Bubble.D3.Bot)** and
  **[OtomAICLIP/otomai](https://github.com/OtomAICLIP/otomai)** ("BubbleBot")
  — a from-scratch Dofus 3 client reimplementation and automation toolkit,
  and its companion Unity/IL2CPP reverse-engineering tools. Cross-referenced
  for message field names and shapes; explicitly **not** used for opcodes —
  measured 0-of-27 semantic agreement with our own opcode table, since
  opcodes are re-shuffled per build.
- **[AnthoB-Dev/GPODofus3](https://github.com/AnthoB-Dev/GPODofus3)** —
  community Dofus 3 project studied alongside the above for protocol
  coverage.
- **[Sebasxs/dofus-parser](https://github.com/Sebasxs/dofus-parser)** — game
  data parsing tooling, referenced for data-format conventions.
- **[cjbrigato/dofhunt](https://github.com/cjbrigato/dofhunt)** — studied
  for its data format/provenance approach.

## Dofus 2.x reference emulators (architecture patterns, not code)

- **[Skinz3/Giny.NETCore](https://github.com/Skinz3/Giny.NETCore)** — a
  modern (.NET 6) Dofus 2.68 emulator. Studied purely for architectural
  patterns (how it structures handlers, sessions, map/movement validation)
  — no code copied.
- **[Skinz3/Symbioz-2.38](https://github.com/Skinz3/Symbioz-2.38)**
  (AGPL-3.0) — the same author's earlier (2018) Dofus 2.38 emulator,
  predecessor to Giny.NETCore; studied the same way, and specifically for
  `Symbioz.ProtocolBuilder`, the direct ancestor of the protocol-builder
  pattern this project's own tooling follows.

## Client/binary analysis tooling

- **[Il2CppInspector](https://github.com/djkaty/Il2CppInspector)** (AGPL-3.0)
  and its actively maintained continuation
  **[Il2CppInspectorRedux](https://github.com/LukeFZ/Il2CppInspectorRedux)**
  (AGPL-3.0) — automated IL2CPP metadata extraction and C# stub generation;
  the tool behind `tools/client-dump/gate-g0.py`'s expected input shape.
- **[Cpp2IL](https://github.com/SamboyCoding/Cpp2IL)** (MIT) — reconstructs
  usable pseudo-IL/C# from IL2CPP-compiled native code.
- **[MelonLoader](https://github.com/LavaGang/MelonLoader)** (Apache-2.0) —
  universal Unity (Mono and IL2CPP) mod-loader used for runtime
  instrumentation.
- **[Ghidra](https://github.com/NationalSecurityAgency/ghidra)**
  (Apache-2.0) — used on the native binary once metadata has been recovered
  by the tools above.
- **[JPEXS Free Flash Decompiler (ffdec)](https://github.com/jindrapetrik/jpexs-decompiler)**
  (GPL-3.0) — SWF/AS2/AS3 decompiler; used headless to recover the Dofus
  2.x (Flash/AS3) network protocol in the clear, which anchored the
  2.x-to-3.0 protocol evolution comparison.
- **[radare2](https://github.com/radareorg/radare2)** (LGPL-3.0 core; some
  plugins/dependencies under GPL) — general reverse-engineering framework.
- **[Frida](https://github.com/frida/frida)** (wxWindows Library Licence
  3.1) — dynamic instrumentation toolkit.
- **[mitmproxy](https://github.com/mitmproxy/mitmproxy)** (MIT) —
  interactive, scriptable TLS-capable proxy.
- **[AssetRipper](https://github.com/AssetRipper/AssetRipper)** (GPL-3.0)
  and **[UnityPy](https://github.com/K0lb3/UnityPy)** (MIT) — Unity asset
  bundle reconstruction/extraction tooling.

## A note on what's absent from this list

Several tools and reference emulators are cited only inside this project's
internal (French) research documents and are not reproduced here, because
either their content quotes proprietary Ankama structures at a level this
export deliberately excludes, or because we could not re-verify their
repository details while preparing this export. If you maintain a Dofus 3
tool or reference project that informed this work and isn't listed above,
please open an issue — we'd rather add you than have left you out by
omission.
