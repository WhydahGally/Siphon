## ADDED Requirements

### Requirement: JS runtime and challenge solver configuration
The download engine SHALL explicitly configure `js_runtimes` and `remote_components` in the yt-dlp options dict so that YouTube JS challenge solving (signature decryption and n-parameter throttling) works without relying on yt-dlp's built-in defaults. `node` SHALL be the primary runtime; `deno` SHALL be listed as a fallback. The EJS challenge solver script SHALL be fetched from GitHub (`ejs:github`) on first use and cached by yt-dlp.

#### Scenario: Node.js is installed
- **WHEN** `node` is on the system PATH and a download is started
- **THEN** yt-dlp SHALL use Node.js to solve YouTube JS challenges and no runtime or solver warnings SHALL be emitted

#### Scenario: Only Deno is installed
- **WHEN** `node` is not on PATH but `deno` is, and a download is started
- **THEN** yt-dlp SHALL fall back to Deno for challenge solving and no runtime warnings SHALL be emitted

#### Scenario: Neither runtime is installed
- **WHEN** neither `node` nor `deno` is on PATH and a download is started
- **THEN** yt-dlp SHALL emit a warning that no supported JS runtime was found; downloads SHALL still proceed but some formats or speed may be degraded
