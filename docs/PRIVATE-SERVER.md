# Running the development server

Requires Python 3.8+ and the original compatible client files for local play.

## Local host (supported)
```sh
python reborn/server/offline_server.py
```
Windows: launch using `Lancer hors ligne - Play Offline.bat` in the game directory.
TCP login 4000, game 4001, battle port defined in source, and HTTP 8000 listen on **127.0.0.1**.

## Config
```sh
CDR_LANGUAGE=fr
CDR_MAX_CONNECTIONS=16
CDR_BIND_HOST=127.0.0.1
```
On Windows PowerShell: `$env:CDR_LANGUAGE = "fr"`.

For isolated VPN experiments, `CDR_BIND_HOST` can be a private interface and `CDR_ALLOW_REMOTE=1` must be explicitly set. **Do not do this on a public interface.** In the current code the client receives localhost in its server discovery reply unless further endpoint work is completed, and there is no multi-user account/session isolation. Therefore remote-client gameplay is **not supported by this PR**.

## Language
`CDR_LANGUAGE`: en (default), fr, de, es, pt. This translates selected server/operator messages, not game UI strings.

## Security
No public TCP exposure, no router port forwarding, no production Docker deployment yet. The game protocol is currently unencrypted and the original offline server has a single shared player and game state. See `ROADMAP-MULTIPLAYER.md`.
