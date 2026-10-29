# Third-party components

## tkwry 0.1.9

Native Tk WebView binding by mashu3: https://github.com/mashu3/tkwry ; MIT license.
Pinned Windows x64 wheel: `tkwry-0.1.9-cp310-abi3-win_amd64.whl`, SHA256 `4874a6f778d473feb4aed3f68caab52446e0e2c7b376514a98d4510b49ecb390`.
The reviewed wheel includes its license and dependency notices in the installed distribution. Web content is rendered by the separately installed Microsoft Edge WebView2 Runtime. Upstream marks tkwry alpha; native integration was checked on this Windows machine, not certified across platforms.

## Falstad / CircuitJS v115

Original authors: Paul Falstad and Iain Sharp, with contributors credited upstream.

License: GNU GPL version 2 or, at your option, any later version. The original license text is included at `app/vendor/circuitjs/COPYING.txt`.

Upstream project: https://github.com/pfalstad/circuitjs1

Published application: https://www.falstad.com/circuit/

The JavaScript/CSS/fonts and selected official example circuits are copied from the public v115 deployment. Local entry HTML removes optional remote Dropbox and analytics scripts; the local example menu is narrowed to shipped examples. The simulator JavaScript is unmodified. Asset URL, size and SHA256 records are in `app/vendor/circuitjs/PROVENANCE.json`.

Source API files were inspected at upstream commit `8ac55f22a03606579b822b3dccd4dc10de1ddc5b`; exact source-to-published-binary build equivalence has not been established. For public redistribution, retain upstream notices and provide the corresponding source and build information required by the applicable license; the API review commit alone is not a verified source release for the published binary.

The app-owned RLC step demonstration is a separate illustrative circuit. It is not a manufacturer MOSFET model or a reproduction of the thesis P6 Buck simulation.

## REA (development tooling)

REA by morluto, package `rea-agents@6.8.0`, MIT license: https://github.com/morluto/rea

REA is installed separately for Codex and Claude Code. It is not bundled into the snubber application or required to run its interactive circuit companion. Dependencies retain their own licenses in the installed tool package.
