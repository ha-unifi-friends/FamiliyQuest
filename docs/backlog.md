# Backlog

Ideas and planned work for Family Quest, roughly in order. Done items move to the changelog.

## Next

1. **Detailed canton coats of arms** – the quiz uses simplified pixel symbols; detailed drawings would need a source that allows it

## Ideas

- **Ping-Pong on two devices** – needs a live connection (WebSocket) instead of polling; one tablet works already.

### Hitparade – music game with a timeline (in the style of Hitster, own name and look)

- Parents choose a playlist and a speaker; on «Play» the speaker plays a random song of the playlist.
- Players choose a group (guests too, via QR code). The group on turn places the song in its timeline
  (by year) and types artist and/or title (rule), within a time limit (default 2 minutes per song).
- The other groups see the answer right away and can **challenge** with coins (cost set in the rules).
- Spelling not quite right → everybody votes whether it was close enough.
- Every group sees the tiles of its songs (guessed or won by a challenge). Default: 10 songs win.
- **Song lists as tables** (title, artist, year, Spotify link) – edit in the parent area, download and upload
  (CSV). Ready-made templates to start from: 80s, rock, general hits, Swiss hits, children's songs, classics …
  The year is checked once in the list, so the game does not depend on the album year of the streaming service.
- Like «Errate den Song» (done) it can steer a speaker of Home Assistant; open: how a single song of the list is played
  (Spotify, Music Assistant, Spotcast).

### Social deduction game (Mafia; themes for children)

The app is the narrator: everybody plays on their own phone (guests via QR code), nobody has to lead.
- **Roles:** villagers and a hidden group (mafia). Only the mafia knows each other. Optional: detective (checks one
  player per night: mafia or not), protector (protects one player per night, not the same twice in a row).
- **Night:** the mafia votes secretly whom to remove; no majority → random. Everybody else also taps something on
  their phone at night (e.g. «whom do you suspect?»), so nobody can tell the mafia by watching the screens.
- **Day:** the app tells who is out; discussion with a timer, then a vote who goes to prison; tie → random
  (or: nobody / run-off – setting).
- **Win:** the village when all mafia members are out; the mafia when they are as many as the others.
- **Settings:** theme, number of mafia (auto: about one per 3–4 players, at least 5 players), special roles on/off,
  show the role of who is out (yes/no), discussion and vote time, tie rule, open or secret day vote, first night with
  or without a victim, players who are out see all roles (yes/no), announcements over a Home Assistant speaker.
- **Themes:** classic Mafia; «Wolves in the village»; for children «Cake thieves» (thieves steal cakes at night,
  the village sends suspects to the naughty corner) or «Ghost castle» (ghosts scare someone away). No bots.

### Arcade and classic games (own names and looks)

Game ideas are free, names, characters, graphics, sounds and level layouts are not. Candidates with own names:
- **Snake**-style («Schlange»), **Mauerbrecher** (ball and paddle, like Breakout), **Tischtennis** (two players,
  like Pong – one tablet or two phones), **Vier in einer Reihe**, **Code knacken** (like Mastermind),
  **Minensucher**, **Schiffe versenken** (two phones). (Tic-Tac-Toe, Sudoku, Patience, Ping-Pong and Pairs are done.)
- Avoid look-alikes of Pac-Man (character, ghosts, maze), Tetris (falling blocks in its look) and Space Invaders
  (alien figures) – their owners defend them actively.

