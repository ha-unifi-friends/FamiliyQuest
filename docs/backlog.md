# Backlog

Ideas and planned work for Family Quest, roughly in order. Done items move to the changelog.

## Next

1. **Detailed canton coats of arms** – the quiz uses simplified pixel symbols; detailed drawings would need a source that allows it

## Only in «Family Quest Dev» – rework before the beta

These games are in the code (with their tests), but only the dev app has them (`family_quest/app/familyquest/channel.py`,
`DEV_GAMES`; the dev app is written by `tools/publish_dev.py` with the marker `app/CHANNEL` = `dev`). Stable and beta
leave them out everywhere (games lists, access settings, FamilyTime, Facts, guests, API 404); old history entries
still show. Once reworked, take the game out of `DEV_GAMES` and it is in the next beta.

- ~~**🏎️ 24h Endurance** (`langstrecke`)~~ – done: reworked into the short version (a pit stop after every lap,
  automatic driver change, the crew prepares tyres / fuel / spare engine during the lap, rain and tyre choice, two
  chicanes with braking zones, team colour / country / number) and back in the beta.
- **🏛️ Beat the Bureaucracy** (`stempeljagd`) – too complex to play: rework before beta (fewer counters, rules and
  special cards; a game that explains itself while playing).

### 💡 Code Workshop – stages 2 and 3 (stage 1 is in the dev app)

Stage 1 (editor, engine, events / motion / looks / control / minimal sensing, 15 puzzles, own programs with templates,
visibility and remix) is only in Family Quest Dev (`channel.DEV_FEATURES`) – test it with children, then into the beta.

- **Stage 2:** 🔊 sound (play sound: bell, drum, meow, boing … · play note with a mini keyboard); 🔴 variables (new variable
  «points», «lives» · set / change by · show on the stage); more sensing (key pressed?, distance to, x / y position,
  direction, size, touching colour?, math + − × ÷, join texts); «repeat until», «when sprite touches …», colour effects;
  more puzzle levels (about 30 in 5 worlds: variables «count the apples», messages); 🤖 import / export in an AI-friendly
  JSON format with a prompt box (`aiPromptBox`, like the books); the avatar of the child as a sprite; templates «Maze» and
  «Ping-Pong»; a Facts question «Who solved most code levels?»; coins per shared program (parent setting).
- **Stage 3:** own blocks (functions with parameters), clones, lists; a «share as book page» link; a small gallery of the
  family with ⭐ ratings.

### «Fischen» – multiplayer fishing (simple)

User wishes (2026-11-18): keep casting / reeling **simple**; **many rarity levels**; **several fish per rarity**;
**no** two-person team catch. Open question to the user: variant A (tournament, everything resets) or B (persistent
gear and islands, with a «same gear for all» option at family tables) – proposed: **B**.

- **Simple controls:** one tap «Cast» (automatic throw), wait, one tap when the float dips (generous window, about
  1.5 s, Junior even longer), then hold a single «Reel» button until the fish is in (no tension balancing). Missed =
  the fish is gone, cast again.
- **Rarity levels (8):** Common ⚪, Uncommon 🟢, Rare 🔵, Very rare 🔷, Epic 🟣, Legendary 🟡, Mythic 🔴, Secret 🌈 –
  6–10 fish per level and island (plus funny junk catches: boot, rubber duck, message in a bottle).
- **Luck** = rod + bait + boat + island + time of day + weather: shifts the rarity chances up, never guarantees. Higher
  rarity = more money.
- **Shop** (in-game money): rods, baits, boat, islands (village pond, mountain lake, coral reef, ice hole, volcano
  lagoon, fog island).
- **Events:** day / night, weather, golden swarm. Fish encyclopedia, collection badges, records (Facts quiz).
- **Multiplayer:** everybody fishes at the same time on their own phone, avatars on the pier, a banner for rare
  catches. Coins for places 1–3, game battery, bots.

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

