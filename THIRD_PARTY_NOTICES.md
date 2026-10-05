# Third-party notices

Shared RAM decoding and emulator primitives are provided by
[PokeSim Core](https://github.com/afk-sapien/pokesim-core), installed separately
under its MIT License. The original decoder was adapted from
[PokeSim](https://github.com/afk-sapien/PokeSim), copyright 2026 AFK Sapien,
under the MIT License reproduced in [LICENSE](LICENSE).

WRAM addresses and event indices correspond to the
[pret/pokered disassembly](https://github.com/pret/pokered/tree/a1a22aaf84d1675bcdbaeb194592379d586d838e).
No cartridge code, ROM, generated game tables, or disassembly source is
included in the application source distribution. The results website includes
selected gameplay screenshots as research evidence. Those images retain their
original rights and are not covered by this project's MIT license.

PyBoy and other Python dependencies retain their own licenses and are installed
separately by the package manager. This repository distributes application source
and a dependency lockfile, not a bundled emulator binary or container image.
Review dependency notices before creating a bundled distribution.

Pokemon and related names belong to their respective rights holders. This is an
unofficial research project with no affiliation or endorsement.

The optional manuscript workspace uses
[paper-scaffold](https://github.com/pgarrett-scripps/paper-scaffold), pinned to
commit c9cb1046d710b3fab851e9984b23254b82a031bc. Its generated support files
retain upstream notices, and its MIT license is in `paper/LICENSE.scaffold`.
It is installed in the manuscript's separate environment.
