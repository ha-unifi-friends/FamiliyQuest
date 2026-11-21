# Third-party notices

Family Quest itself is published under the Business Source License 1.1 from version 1.2.2 on (versions up to 1.2.1:
MIT) – see LICENSE and the README. It contains the following works of others, which keep their own licenses:

| Part | Where | License |
|---|---|---|
| **Family Planer** (UI and core), © 2026 magibuilds | `family_quest/app/web/planer/`, `family_quest/app/familyquest/planer/` | MIT – full text in `LICENSE.family-planer` in both folders |
| **Material Design Icons**, © Pictogrammers (Austin Andrews and contributors) | `family_quest/app/web/planer/mdi-icons.js` (the icons the planer uses) | Apache License 2.0 – <https://www.apache.org/licenses/LICENSE-2.0>, <https://github.com/Templarian/MaterialDesign> |
| **qrcode-generator** 1.4.4, © 2009 Kazuhiko Arase | `family_quest/app/web/shared/qrcode.js` | MIT – <https://github.com/kazuhikoarase/qrcode-generator> |
| **Canton outlines and lakes** (generalised boundaries) © FSO / swisstopo, prepared by **swiss-maps** © Interactive Things | `family_quest/app/web/geo/ch.json` (built with `tools/build_ch_geo.py`) | FSO geodata: free use with the source given; swiss-maps: BSD-3-Clause – <https://github.com/interactivethings/swiss-maps> |
| **Country outlines of Europe** – Natural Earth (public domain), prepared by **world-atlas** © Mike Bostock | `family_quest/app/web/geo/europe.json` (built with `tools/build_europe_geo.py`) | Natural Earth: public domain; world-atlas: ISC – <https://github.com/topojson/world-atlas> |
| **Country flags** – **country-flag-icons** 1.6.20, © 2020 @catamphetamine | `family_quest/app/web/flags/*.svg` (licence in `flags/LICENSE.txt`) | MIT – <https://gitlab.com/catamphetamine/country-flag-icons> |
| Translation runtime (`shared/i18n.js`, language picker) | taken over from [IP Manager for UniFi](https://github.com/ha-unifi-friends/ha-ip-manager-unifi) | MIT |

The Material Design Icons are used unchanged (only the SVG paths of the icons the planer needs are bundled).
«QR Code» is a registered trademark of DENSO WAVE INCORPORATED.

Family Quest is a hobby project for private use in families; commercial use needs a separate license (see LICENSE).

Names of other products that appear in descriptions (e.g. Home Assistant, UniFi, Spotify) are trademarks of their
owners; Family Quest is not affiliated with them.
