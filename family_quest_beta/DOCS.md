# Family Quest

Learning in any subject with points, rewards and avatars – for the whole family, inside Home Assistant.

## First start

1. Open **Family Quest** in the sidebar and choose **Parent area** (or open `…/eltern`).
2. Create the parent profile. It is always protected by a PIN (4–8 digits).
3. **Profiles › Add child** – name, colour, PIN, daily goal (XP), exercises per lesson,
   new cards per lesson, learning hours (e.g. `07:00-20:00`), automatic logout. With the Family Planer installed,
   **Take over from Family Planer** creates a profile for every person and links it.
4. **Profiles › Add parent** – more parents (each with an own PIN for the parent area). Every parent can confirm
   chores and rewards and can learn along; enter a notify service per parent so approvals reach every parent's phone.
   The last parent profile cannot be removed.
   **PIN for children:** a *picture PIN* comes first – the child picks 4 of 12 symbols in its own order (tap them or
   draw a line; 🔀 brings other symbols). At login the same 12 symbols appear in a new order every time, so a
   watched pattern does not help. 12 × 11 × 10 × 9 = 11 880 combinations – more than a 4-digit PIN. A 4-digit PIN or
   no PIN can be chosen instead.
5. **Packs** – every child starts with all built-in packs; switch packs or whole level packs on and off per child.

## Options

| Option | Meaning |
| --- | --- |
| `direct_access` | Also serve the app in the home network on port 8099 (Family Quest Beta: 8098; can be changed under *Network*). Without it only Home Assistant ingress can reach the app. Parent area › Settings shows the link as a QR code. |
| `log_level` | Log detail. |

## Data

Everything lives in `/data/family_quest.db` (SQLite) and `/data/media/` – both part of Home Assistant backups.
Additional packs can be placed in `/share/family_quest/packs` (YAML files, folders with YAML + pictures, or ZIP files);
they are read at start. Packs changed in the parent area are not overwritten by the folder copy.

## The app: menu and season designs

The app has no bar at the bottom any more. At the top left **☰** opens the menu: Home, Learning, My card box, Shop,
**Me** (avatar, own bots, PIN), Family, Planner – and language, light/dark, sound, the season design and log out. The
header shows the clock and the buttons of the page you are on (e.g. «+ New deck»).

**Season designs:** like the Family Planer, the header shows an animated scene for the design of the day. Built in and
scheduled every year: spring, summer, autumn, winter, **Halloween** (20.10.–1.11.) and **Christmas** (1.12.–26.12.);
events win over the seasons. In the parent area under **Settings › 🎨 Season designs** you switch them on or off,
move their dates and add **own designs** (name, icon, colour, scene, from – to; e.g. a birthday week) – own designs
come first. Children can switch the scene off on their device in the ☰ menu.

## Points and rewards

- **Accounts:** XP (progress, never spent), Coins (spendable), Internet minutes (off by default) – add your own.
- **Rules:** event → amount → account, optional daily limit. Events: correct answer, card that was wrong before,
  fast answer in the quiz, lesson finished, daily goal reached, quiz without mistakes, new badge, chore done,
  7/30 day streak.
- **Shop:** vouchers (parents fulfil them), internet minutes (to the profile's *budget entity*, with a daily limit),
  Family Planer points, Home Assistant script (`script.xyz`, gets `profile`, `reward` as variables), avatar item.
  With *Parents must approve* the amount is reserved and booked back on decline.
- **Push approvals:** in *Settings* choose a notify service of the Companion app; the message has the buttons *OK* and *No*.

### Pets

The pets of the avatar shop (dog, cat, parrot, degu – the owl comes with the badge *Busy bee*) want to be looked after. Under
**Me › 🐾 My pets** every pet has a name (Bello, Minka, Coco, Krümel, Eulalia – tap it to rename), its age in days and three
bars: 🍖 hunger, 😊 mood, 🫧 cleanliness (0–100). Hunger and mood drop from full to empty in about 2 days,
cleanliness in about 3 days.

- **Feed** costs coins (*Settings › Learning › Pets: food costs*, default 2) and gives +40 hunger; **Play** (+35 mood)
  and **Wash** (+50 cleanliness) are free. Bars go up to 100.
- **Warnings:** a bar below 25 shows a banner on the start page («Bello is hungry»); when all three bars are empty a
  red banner shows how many days are left, and the parents get a message once (Home Assistant notification and the
  notify services of *Push approvals*).
- If all bars stay at 0 for **3 days**, the pet dies: it is taken off the avatar, the unlock is removed, a note goes
  into the coins history and the child sees a gentle message at the next login. The pet can be bought again in the
  shop as a new baby (an owl that died costs 120 coins).
- **Growth:** every pet starts as a baby (🍼, days 0–6), is young from day 7 and adult from day 30 – the badge on the
  avatar grows with it and shows the age in days.
- **Holiday care:** in *Overview* each child's card shows the pets; **⏸ Holiday care** stops the bars and the death
  timer until it is switched off. On days the built-in planner has the child away on holiday (holiday found in the
  calendars and decided as «away»), pet care pauses by itself.
- **Bots:** the living pets of a child play along as bots in the card games, Domino, Paarjagd and Texas Hold'em
  (only for their owner).
- **🛍️ Furnish & dress up:** every pet card on the Me page (above *My bots*) shows the pet at home – its house as a
  backdrop, the furniture around it and the pet in its outfit. The button opens the pet shop with three tabs:
  - **Clothes** (30–80): bow, collar, sweater, raincoat, little dress, sunglasses, party hat, crown. The pet wears one
    outfit; the child switches between the bought ones. The first time an outfit is worn the pet gets **+20 mood**
    (once per outfit). The outfit also shows on the pet badge of the avatar.
  - **House** (120–300): dog house, cat basket with scratching tree, bird cage, degu enclosure, castle – any pet may
    live in any house, «★ fits best» marks the one made for its kind. One house is in use at a time.
  - **Furniture** (20–60): bed, food bowl, toy ball, play wheel, cushion, lamp, plant, rug – up to **6** placed at a time.
  - A house makes the mood drop **25 % slower**, each placed piece of furniture another **5 %** (at most **50 %**). A
    house with at least 3 pieces of furniture shows ✨ *Happy home*. Bought items are put on / moved in / placed right
    away and can be changed at any time.
  - Everything belongs to that one pet and is **lost when the pet dies**.
  - **Paying:** *Settings › Learning › Pet shop: pay with* – coins (default), XP, or both (the child chooses coins or
    XP for each purchase; the price is the same number). XP spent in the pet shop lower the XP balance but **not the
    level** (nor the daily goal or the weekly XP): the level counts the XP earned.

## Behaviour weather

Parent area → **⛅ Weather**: one list with every child (avatar, name, today's weather). Tap a symbol in the list to
set it – its bonus or malus is booked right away. A small graph shows each child's weather of the last 30 days
(the worst weather of each day; grey dashes = nothing set).

Below the list you configure the symbols (default ☀️ +5, ⛅ 0, 🌧️ −5, ⛈️ −10 coins – best weather on top), the
account, the daily reset time (default 12:00) and the weather everybody is back at after the reset (the reset books
nothing). Each child sees only its own weather on its start page, never the weather of the others.

## Family calendar

Parent area → **📅 Calendar**: month view (a list on phones) with your own events – all day or with a time, with a
symbol. Below:
- **Templates:** school holidays and public holidays of every Swiss canton and year, from the free OpenHolidays
  service (openholidaysapi.org – Home Assistant needs internet for it). You see a preview first.
- **Import:** iCal files (.ics) or CSV with the columns title; start; end (dates like 04.07.2026 or 2026-07-04).
- **Duplicate check:** an event with the same title and dates (or the same iCal UID) is marked and not taken over.
- **Imports** can be removed again as a whole (e.g. the school holidays of a canton).
- **Calendars from Home Assistant** (Google, school, waste collection …) can be shown in the family calendar – read only.
The kiosk dashboard shows today's and tomorrow's events of the family calendar too.

**Weather alarm:** in Dashboard → *Weather alarm* choose a weather entity of any Home Assistant weather integration.
Rain (from a chosen chance), thunderstorm, snow, strong wind, cold or heat in the next hours → the dashboard (and,
if wanted, the children's start page) shows what to take along – «take your rain jacket or umbrella» …

### The family calendars in the planner

The row **«Events»** of the planner's week shows the events of the Family Quest calendar and of the Home Assistant
calendars chosen in the parent area (Calendar › Calendars from Home Assistant), next to the persons' own calendars.
Tap a calendar in the legend at the top left to switch it off or on – on this device.

### FamilyTime and OfflineTime

Calendar › **+ 👨‍👩‍👧 FamilyTime** / **+ 📵 OfflineTime** (or the kind in the event window):
- **FamilyTime** is highlighted in the calendar, on the start page of the children and on the kiosk dashboard, with a
  countdown («starts in 2 h», «still 45 min – until 20:00»).
- **OfflineTime** can switch off, for all or chosen children: the **internet** (a running internet time stops, it
  cannot be started) and the **games of the app** (learning stays open). Without a tick it is only a notice.

### FamilyTime games: wishes, vote, fix a game for coins

Which game do we play at the next FamilyTime? In the app on the **Family** page (and in the parent area › Family) the
section **🎲 FamilyTime games** lists the FamilyTime events of the next 60 days:
- **Wishes**: every family member (children and parents – never guests) wishes **one** game per FamilyTime: one of the
  app's family games (the ones this person may play, parent area › Games) or a **board game** typed in (free text, max.
  60 letters, e.g. «Monopoly»). The wish can be changed or taken back until the wishes close. The start page shows
  «Wish a game for FamilyTime on Saturday!» until you wished.
- **The wishes close** when a parent taps **Start the vote**, or by themselves *N* hours before the start (setting,
  default 24 h). Only one game wished (also when several people wished the same): it is **set directly**.
- **The vote**: one vote per family member, it can be changed. It ends when everybody voted, when a parent taps **End
  the vote**, or when the FamilyTime starts. The start page shows **Vote now!** until you voted. A **tie**: the parents
  choose one of the leaders or tap **🎲 Random**; a tie still open when the FamilyTime starts is drawn at random.
- **Parents** can also **set a game** directly (one of the wishes or any game), **skip the vote** (no game from the
  wishes this time – they can still set one, a child can still buy one), **clear the wishes** (start over) and
  **remove the game**.
- **Fix a game for 150 coins**: a child pays the price (setting, default 150, 0 = off) and sets the game of a
  FamilyTime that has **no game yet** firmly – the wishes and the vote of that FamilyTime end. Refused when a game is
  set already. If a parent removes a bought game (or deletes the FamilyTime, or makes it an ordinary event), the child
  gets the coins back (ledger events `familytime_game` / `familytime_refund`).
- The game shows on the FamilyTime: «🎲 Game: Tschau Sepp – chosen by vote / bought by Mia / set by Papa» in the
  calendar of the parent area, in the planner's calendar row, on the FamilyTime banner of the start page (from 24 h
  before) and in the section. Everybody of the family gets a history entry when the game is set.
- **Settings** (parent area › Family › FamilyTime games › ⚙️, and the same under Settings › FamilyTime games):
  switch the whole feature on/off (off: children see nothing of it), the coin price, the hours before the start when
  the wishes close.

## Kiosk dashboard

Parent area → **🖥️ Dashboard**: a read-only page for a wall tablet, TV or old phone – any browser, no login.
Choose the children and what it shows: clock, crown, each child's weather, learning progress, streak, coins, open
chores, the family goal, open Planer to-dos and today's events of Home Assistant calendars. Moods and messages to
the parents are never shown. The link contains a secret key (🔄 «New link» makes a new one and the old screens stop);
`&lang=fr-FR` fixes the language. The page refreshes itself and keeps the screen awake where the browser allows it.

## Chore plan (Ämtliplan)

Parent area › **Chores**: add chores with icon, points and account, how often (every day, on certain weekdays, once a
week, once on a date), who (several children) and the assignment – *fixed* (every chosen child does it) or *rotating*
(one child after the other, changing every day or every week). *Duty* chores usually give few or no points, *bonus*
chores the full points. With *Parents confirm* a ticked-off chore waits for *OK* (points are booked) or *Once more*
(back to open). The week plan shows who does what on each day; the rule *All chores of the week done* gives a bonus
(20 coins by default). In *Settings* a chore reminder time announces open chores (via the Family Planer announcement
queue) and fires `family_quest_aemtli_erinnerung`. Chores from the Family Planer appear on the dashboard next to them.

## Shopping list (Bring!)

Parent area › Settings › **Shopping list (Bring!)**: the to-do lists of Home Assistant are listed – Bring! lists
first (from the Bring! integration of Home Assistant). *Show in the planner* makes one of them a smart list of the
built-in planner, sorted by shop sections. It stays one list: what you add or tick in the planner shows up in the
Bring! app and the other way round (Home Assistant syncs it with Bring!).

## Home Assistant

Per child profile (name in lower case, e.g. `mia`):

| Entity | |
| --- | --- |
| `sensor.family_quest_mia_xp_heute` | XP today, attribute `daily_goal` |
| `sensor.family_quest_mia_<account>` | balance of each spendable account, e.g. `_coins` |
| `sensor.family_quest_mia_streak` | days in a row with the daily goal |
| `sensor.family_quest_mia_level` | level, attributes `xp`, `next_level_at` |
| `binary_sensor.family_quest_mia_tagesziel` | on once the daily goal is reached |
| `sensor.family_quest_mia_aemtli_offen` | number of open chores today, attribute `chores` (names) |

When a child sets its avatar to the sad face, the parents get a quiet note (Home Assistant notification and a push
without buttons, once per day) and the parent overview shows «feels sad (since …)». Event: `family_quest_stimmung`.

Events: `family_quest_lektion_fertig`, `family_quest_aemtli_erledigt`, `family_quest_abzeichen`, `family_quest_erinnerung`,
`family_quest_aemtli_erinnerung`
(each with `profile` and `profile_id`). The sensors are written through the REST API, so they are recreated when the app
starts and do not have a unique id.

### Family Planer

Family Quest reads the persons and their chore lists (`todo.*`) from the Family Planer's entity registry. Link a profile
with a person (profile dialog) and the child sees today's chores on its dashboard and can tick them off; a chore ticked off
in Family Quest, the Family Planer or the Home Assistant to-do list books the rule *Chore done* once per day. Chores that
were already done when the app started are remembered without points.

### Internet time

**Managed by Family Quest (recommended):** in the child's profile choose the UniFi firewall/traffic rule (the switch the
UniFi Network integration creates for it) and whether the rule blocks the internet while the switch is on. The budget is
the account *Internet minutes* (filled by the shop, rules such as the 7 day streak, or parents with *Book points*). The
child starts and stops the internet time on its dashboard; one minute is booked per started minute and the rule blocks
again at zero. Parents see the remaining minutes in the overview and can stop it. At start of the app every idle rule is
set to «blocked»; running sessions continue. Sensor: `sensor.family_quest_<name>_internetminuten` (attribute `running`).

**Budget entity (optional):** minutes bought in the shop can also be written to an `input_number` in Home Assistant,
e.g. for your own automations.

### Time per day: games, learning, internet

In the profile of a child (parent area › ✏️ › **⏱️ Time per day**) three sliders stand on top of each other:
🎮 **Games per day**, 📚 **Learning per day** and 🌐 **Internet**. A slider starts in minutes (0, 5, 10 … 45 min)
and goes on in hours (1 h … 12 h); far right is **∞ = not limited** – the default for games and learning.

- **📅 Days** next to a slider opens the 7 weekdays (Mon – Sun) below it, each with its own slider. A weekday is
  *docked* (🔗, pale): it moves with the slider above. Move a weekday slider yourself and it is *undocked* (🔓, in
  colour) with its own time; move it back to the value of the slider above and it docks again (or tap 🔓). The number
  on the Days button counts the undocked days; the days open by themselves when one has its own time.
- **Games:** every minute in which a child uses a family game (any game request, also waiting in a running game) or
  the game corner (a heartbeat every minute) counts once – several games at the same time do not count twice. When the
  time is used up the child can start or join no new game, the game corner closes and the Games page says «Game time
  for today is used up – see you tomorrow!». A game already running may be played to the end.
- **Learning:** the learning time of today (finished lessons) counts. When it is used up no new lesson starts; a
  lesson already running can be finished.
- The kid app shows the minutes left today («🎮 25 min left today») on the Games page, the start page / the subject
  page (learning) and in the tiles of «Me». Parents are never limited. A new day starts at midnight.
- **Internet:** the slider is the free budget of the internet time (needs the UniFi rule above); with **per week**
  it is the weekly budget (other steps, no weekdays). **0** = no free budget, only minutes from the shop or rewards
  (the behaviour without a plan); **∞** = the internet may run the whole period (block times and OfflineTime still
  apply).

### Internet budget and block times

Below the internet settings of the child (parent area › ✏️ › Internet minutes) **Internet budget and block times**:

- **Reset:** when the budget starts again (time; for a week also the weekday). The budget itself is the 🌐 slider
  under *Time per day*.
- **Block times:** days and a time from – to (also over midnight, e.g. Mon–Fri 20:00–07:00). The internet stays off
  and you choose what Family Quest still allows: *works normally*, *without games*, or *only a message: OfflineTime*
  (the app shows a full-screen message with a countdown until the block time ends).
- Minutes from the shop or rewards come on top: the budget of the period is used first and is not carried over.

The child sees in the app how much of the budget is left and when it starts again; start / pause is in the card
«Points and goodies».

## Languages

The flag button switches the language (English, Deutsch, Schwiizerdütsch, Français, Italiano, Español, Nederlands,
Polski, Português, Svenska; *Auto* follows the browser). Learning content is never translated.

### Own texts and languages

Settings → **🌐 Own texts and languages**: overwrite single texts of any language (English included) or create your
own language – e.g. your dialect – that starts from a base language and appears in the language picker with its own
symbol. Export a language as CSV (`key;standard;translation`, opens in Excel), translate it and import it again; an
empty translation goes back to the standard. Learning content is not translated here.

## Addresses

- **Home Assistant** («Open Web UI», the sidebar entry): opens the **parent area**.
- **The app** for children: `…/app` – inside Home Assistant as well as on the direct port (`http://<IP>:<port>/app`;
  on the direct port `/` still opens the app too). «Family Quest App» in the parent menu, «Open in the app» and the
  planner link there.

## Security in the parent area

The add-on runs with its own **AppArmor profile** (`apparmor.txt`): it reads its program files but writes only to
`/data`, `/share` and temporary folders, and may not mount or debug other processes. Together with Ingress this
gives the security rating 8 in Home Assistant.

**Log in with Home Assistant:** when a parent opens Family Quest from the Home Assistant sidebar, the app knows the
Home Assistant user (the Supervisor tells it – only trusted for requests that really come through Home Assistant).
After the first PIN login the app offers to link this user with the parent profile; from then on the parent area
opens without PIN there. Settings → *Log in with Home Assistant* can also close the parent area for PIN logins
completely (then it opens only through Home Assistant; the PIN still works in the app for learning along).

**One port for the children, the parent area only in Home Assistant:** no second port is needed. Home Assistant
reaches the app through its own way (ingress, from the Supervisor), the app port (e.g. `http://192.168.x.y:8099`)
is for tablets and phones. With *Parent area only through Home Assistant* switched on, the app port offers no parent
area at all: the link is gone, `/eltern` only shows a hint, and every request of the parent area that does not come
through Home Assistant is refused – even with an old session.

**Look:** the parent area uses the shapes of Home Assistant (Roboto, flat cards, the HA sidebar) with the colours of
Family Quest (as in the chore planner); opened in Home Assistant it follows the light or dark mode of the HA theme.
Buttons that add something («+ Add child», «+ New topic», «+ Add account» …) are always top right.

**Parents and their Home Assistant user:** in the profile of a parent you choose the Home Assistant user (all persons of
Home Assistant with a login). With it the parent area opens in the HA sidebar without PIN. The PIN is optional – it is
only the login in the app, e.g. to join a game or learn along on another device; a parent without PIN does not
appear in the app's profile list. Without Home Assistant parents need a PIN as before.

- **Overview › Failed logins:** every wrong PIN of the last 30 days with time, profile, IP address, MAC address and
  device name (from the UniFi device trackers in Home Assistant, when available) and who normally logs in
  successfully from that address. Requests refused by the network filter are listed as well.
- **Settings › Access from the network:** the networks (e.g. `192.168.35.0/24`) from which the app may be used, and –
  stricter – from which the parent area may be opened (e.g. only the parents' network). Empty = every network.
  A list that would lock out the device you are saving from is refused.

## Family (parent area, formerly «Community»): family quiz and family council

- **Family quiz** (learning app › Family › Quizzes, or parent area › Games): everybody – children too – makes
  quizzes (2–4 answers, one right, time per question) or copies a template (Swiss waters, geography of Europe,
  capitals of Europe and the world, flags, food of the world, Swiss specialities, cantons, animals, space,
  inventions, Switzerland). Whoever starts a game leads it (a parent may always step in); everybody joins on their
  own device. Quick right answers give more points (1000 down to 500). Places go into everybody's history; the
  reward events *Played the family quiz* and *Won the family quiz* can give coins (Rewards › Rules).
- **Bingo** (learning app › Family, or parent area › Games): whoever starts sets the rules (speed, one line /
  two lines / full card – the rules used last are the default); everybody joins with a 5 × 5 card (B-I-N-G-O, 1–75,
  free star). A ball carousel spins, stops and shows the new ball for about 5 seconds. Players mark the numbers
  themselves and press «BINGO!» – the app checks it; a false «Bingo!» blocks the button for 10 seconds. Everybody can
  show the rules any time (📜).
- **Family council** (learning app › Family): anybody asks the family something, everybody adds ideas, then the vote
  starts – secret, one vote each, changeable until the vote ends. The result goes into the history of everybody who
  took part.

### Polls

Below the family council: **📊 Polls** – a question with 2 to 12 answers, one or several answers allowed,
anonymous or with names, optionally with a closing time. Everybody sees the result after answering; who asked (or a
parent) can close or remove the poll. A banner on the start page reminds who has not answered yet.

### Bulletin boards (Schwarzes Brett)
Under the polls: **📌 Bulletin boards** – endless pin boards, one per topic («Summer holidays», «Birthday party», …).
Everybody of the family makes boards (title + emoji) and works on every board; guests (QR invitation) never see them.
Who made a board, or a parent, renames, **archives** (still readable, no more changes) or removes it with **⋯**.

A board opens full screen (✕ closes it):
- **Pan** with one finger or the mouse on an empty spot, **zoom** with two fingers, the mouse wheel or **+ / −**
  from 5 % to 400 %; **⤢** shows everything. The last view of each board is remembered on the device.
- **🗒️ Sticky note** in 8 colours: choose a colour, tap the board, write. **🔤 Text** in 8 ink colours (A− / A+ for
  the size). **✏️ Pen** with 8 colours and 3 widths, **🔷 shapes** (rectangle, ellipse, arrow, line), **🧽 eraser**
  (wipe over lines and shapes).
- **👆** moves items, a tap selects one (write, colour, bring to front, remove, the round handle resizes notes and
  texts), a double tap writes. Every note shows who made it. **↶** undoes the own last steps (also Ctrl+Z; Delete
  removes the selected item).
- **Live:** changes of the others appear within about a second; the avatars at the top show who is on the board (tap
  one to jump to what they see), their pointer appears with their name, and an item somebody is moving or writing has
  an outline in their colour. Last change wins per item.
- A badge «New: n» on the board list and a banner on the start page show what the others changed since you last
  looked.

Limits: 200 boards, 2000 items and about 3 MB per board, 1000 characters per note, 2000 per text, lines are thinned out
to 600 points. Everything is in the database, so the backup contains the boards.

### Wichteln (secret gift giving)
Under the polls, everybody can start a **Wichteln**: enter the occasion (e.g. «Christmas 2026»), choose who takes part
(whole family or single members) and the rules – *parents not among each other*, *children not among each other*, or
nothing ticked for completely open. On **Draw** the app draws at random who gives a present to whom (never to
oneself). Everybody sees only whom **they** give to – behind a «Show» button, so nobody looks over the shoulder. The
whole list is shown to nobody, not even to who made it. Who made it or a parent can delete it.

With a **date**, every participant gets a to-do in the Family Planer («🎁 Wichteln: occasion · 24.12.» – without the
name of the receiver, the planner may hang on the wall). Tick it off in the planner or with **Present ready** in the
Wichteln card – both count. Deleting the Wichteln removes the open to-dos.

The parent menu has **📝 Release notes** below «Log out»; the version number there opens the add-on page in Home Assistant.

### Texas Hold'em

Community → **🃏 Texas Hold'em**: everybody plays on their own device (guests too), **only with play chips** – they
have nothing to do with coins or points. Who opens the table sets the rules (remembered for the next game): start
chips, small and big blind, ante, blinds doubling every N minutes, time per move (then the app checks or folds),
players at most, and the mode: **everybody starts with the same chips** (who has none is out, the last one wins) or
**game leader with a bank** (players ask for chips, the leader gives a buy-in; with a limit of re-buys).
No-limit rules with side pots; heads-up the dealer posts the small blind.

### Texas Hold'em alone against bots

Family › Texas Hold'em › **🤖 Alone against bots**: 1–5 animal bots (easy, normal, hard), start chips and blinds –
the cards are dealt right away, on your own table (the family table stays free). The bots decide by the strength of
their cards and the pot odds; easy bots bluff and call more often. When you have no chips left the game is over.

### Errate den Song

Family › **🎵 Guess the song** (or parent area › Games): the game leader chooses a **speaker** of Home Assistant
(a media player that already has a playlist) and the rules – what who buzzes says (artist and title, artist or
title, only one of them), the others judge by majority or unanimous, points to win (e.g. 10) and songs at most (e.g.
40). The app switches shuffle on and only steers the speaker: play, pause, next song.
Everybody has a big **buzzer** on their device; the first one stops the song and says the answer out loud, then
«Show the solution» shows cover, artist and title from the speaker and the others vote 👍 / 👎. Right +1, wrong −1.
«Nobody knows it» shows the solution without points. Guests can join with the QR code.
The game leader turns the speaker up or down (🔉 − / 🔊 +, 5 % each). After a buzz a **countdown** (setting, default
5 s) runs before «Show the solution» can be tapped – first the answer, then the solution.

**Open in the app:** in the parent area every game has «↗ Open in the app» (top right) – the app opens in a new tab,
logged in as this parent, right in the game.

**Ping and brrr:** after the verdict everybody's device plays a game-show sound for right or a buzzer for wrong (own sounds of the app, made by `tools/make_sounds.py`). With «also on the
speaker» (start dialog, on by default) the speaker plays it too – as an *announcement*: speakers that support it
(e.g. Sonos) lower or pause the playlist for a moment and go on where they were; the queue is not changed. The speaker
fetches the sound from the app's direct access (Options › direct access with its port) – without it only the
devices play the sound.

### Own bots

Avatar › **My bots** (top right **+ New bot**): children make their own bots – name, a look (emoji), a colour and how
well it plays (easy, normal, hard). With *Share with the family* siblings can play with it too. In the start window of
Tschau Sepp, Kartenkarussell, Domino and Texas Hold'em (alone against bots) you tap your bots to put them at the table; free
seats are filled with the animal bots.

### Light and dark

The button ☀️ / 🌙 (top right in the app, next to the language in the parent area) switches between light and dark and
is remembered on the device; without a choice the system (or the Home Assistant theme) decides.

### Games per game and person (parent area › 🎲 Games)

The parent area has two pages: **Family** (family council, polls, bulletin boards, Wichteln, history) and **🎲 Games** (every game:
the family quiz, bingo, guess the song, all live games with their start buttons, coins and photo sets, the running
games, and the game corner). A **search field** at the top filters the games by name; «⚙️ For all games» holds
*All on / All off*, who begins a game and whether guests may join.

Every game has a **status**: *active*, *active without bots* or *inactive* (= off), and while active *for everybody* or
*only chosen children* (tick the children). Parents can always play – and are not bound by «without bots» either.
Switched-off games disappear from the children's app.

**Active without bots** is offered for the games that can be played with bots: Texas Hold'em, Tschau Sepp,
Kartenkarussell, Domino, Paarjagd, Kartenlauf, Fünf Würfel, Heimwärts, Jump, Snack Rush, Klatsch den Beat, Jass, Werwölfe, Chess,
Dorfmarkt, Tic-Tac-Toe and Ping-Pong. Then the app hides «alone against bots», the bot fields of the start dialogs and
the games against the app, and the server refuses every start with bots («Playing with bots is switched off for this
game»): family tables get no bots (Kartenlauf plays with the people there, Jass needs 4 people, Werwölfe needs 5), chess
only against the family or two on one device, Ping-Pong doubles only with people. Jump, Snack Rush and Klatsch den Beat can still be
played alone, without practice bots. A table where a parent plays along may still be filled with bots.
Stored per game in the setting `games_access` (`{"mode", "profiles", "bots"}`, `PUT /api/parent/games`).

**The children's Games page** shows the running tables on top, then the family quiz, then two groups of small tiles
(icon + name): **🎲 For a game night** (Tschau Sepp, Kartenkarussell, Domino, Jass, Texas Hold'em, Dorfmarkt, Heimwärts,
Kartenlauf, Werwölfe, Escape Room, Wer bin ich?, Verbotene Wörter, Zeichnen & Raten, Stadt-Land-Fluss, Guess the song,
Bingo, Chess) and **⚡ Quick games for in between** (Paarjagd, Fünf Würfel, Jump, Klatsch den Beat, Star Runner, Snack
Rush, Traffic Cadet, duels for two), and the game corner at the end. A tile with a running table has a pulsing dot; a
tap opens the game's card in a sheet with its usual buttons (family table, alone against bots, join, rules).

### Family council: new topic

**+ New topic** (top right) opens a window: the question, a few words more, the first ideas, the rule of the vote
(simple / absolute majority / unanimous, and «at least one parent and one child») and how it goes on – collect ideas
first or vote right away.

### Card games: Tschau Sepp and Kartenkarussell

Community → **🂡 Tschau Sepp** (Swiss or French cards) and **🎠 Kartenkarussell** (own cards in violet, raspberry,
orange and petrol): shed your cards by suit/colour or value. Play **alone against bots** (animals with their own
name – private) or open a **family table** (with bots if you like, guests via QR code). Who starts sets the rules
(remembered): cards in the hand, rounds, bots and how well they play, the special cards (7 draw 2, 8 skip,
Under/Jack wish, Ace again, 10 reverse; Kartenkarussell +2, skip, reverse, wish, +4), whether draw cards add up,
penalty cards for a forgotten «Tschau»/«Sepp» («Letzte!»/«Fertig!») and the card back. After the last round the
fewest points win.

### Domino

Community → **🁫 Domino**: lay a tile with a matching number on one of the two open ends of the line. Tap a tile in
your hand – if it fits on both ends you choose **◀ left / right ▶**, otherwise it is laid by itself. Play **alone
against bots** or open a **family table** (bots and guests via QR code like the card games). Who starts sets the rules
(remembered):

- **Set:** double-6 (28 tiles) or double-9 (55 tiles – every number 0–9 has its own colour, easy to tell apart).
- **Cuban** (default): double-9, 10 tiles each, teams of two (partners sit opposite: seats 1 + 3 against 2 + 4), no
  drawing – who cannot play must pass. The round winner scores the pips left in **all** other hands, the partner's
  too (the common Cuban scoring).
- **Simple:** double-6 with 7 tiles each (10 with double-9), everybody for themselves unless teams are chosen;
  optionally draw from the boneyard when nothing fits (pass only when it is empty). The round winner scores the pips
  left in the opponents' hands.
- Teams need 4, 6 or 8 players; otherwise everybody plays for themselves.

When nothing fits, the app says so («No tile fits – you must pass») and shows a big **Pass** button; the others see a
«passes» bubble on that seat. The first round starts with the holder of the highest double; later rounds the winning
side starts – with teams any player of that team may lay the first tile. **Blocked** (nobody can play any more): the
side with the fewest pips wins the round (Cuban: scores all pips left, simple: the opponents' pips); a tie gives no
points and the round is repeated with the same starters. The match goes to **100** points (150 or 200 selectable).
Won while the other side still has 0 points: **🏆 Pollona!** – highlighted in the result and on the score sheet.
**📊** next to the 📜 rules opens the score sheet (round, winner, points, domino or blocked, running totals).

### Paarjagd

Games → **🧠 Paarjagd**: the pairs game live – everybody turns the cards on their own device. Play **alone against
bots** or open a **family table** (bots and guests via QR code like Domino). Who starts chooses (remembered): the
cards (the emoji sets or the parents' photo sets from Settings › Pairs game), **6, 8, 12 or 18 pairs**, the bots and
how well they remember cards (easy / normal / hard) and the **card back** (tap one; the family crest when there is
one). On your turn you turn two cards: a **pair** is yours and you go again; **no pair**: everybody sees both cards
for a moment, then they turn back and the next player goes. When all pairs are found the most pairs win – a tie
shares the place. The board always fits the screen, also on a phone.

**Coins for places 1–3:** the parents set them in Games › Paarjagd («🪙 Coins for place 1 / 2 / 3», default
10 / 5 / 2). They are paid once at the end of a game, and only at a **family table with at least two people of the
family**: no coins alone against bots, none for guests and none for bots. The result shows «+10 🪙» next to the place.
The existing Pairs game in the game corner (one device, take turns) stays as it is.

### Wer bin ich?

Games → **🎭 Wer bin ich?**: the guessing game live – everybody on their own device. Who opens the **family table**
chooses a category (animals, jobs, food & fruit, countries, Swiss places & mountains, fairy tales & legends, things at
home, sports, famous people – the characters are German names, fixed in this version). Only people play: the family
and guests via QR code – no bots, and at least two players. At the start everybody gets a different character at
random. Each device shows the characters of **all the others**; your own stays «❓» until you found it or gave up
(the server never sends it to you before).

It goes round in seat order (finished players are skipped). On your turn you can:

- **ask a yes/no question** – type it or just say it aloud, then «Ask question». The others answer ✅ yes / ❌ no /
  🤷 don't know (finished players too – they know). When all have answered the question closes; the asker (or who
  leads) can close it earlier once there is an answer. A **majority of yes**: you ask again; otherwise (no, don't know,
  a tie) the next player goes.
- **guess** «I am …» – checked against the name and a few other names (no matter capitals, umlauts / accents,
  articles, punctuation; one typo is fine from 5 letters, two from 9). Right: you are finished and get the next place
  (a short reveal for everybody). Wrong: the next player goes.
- **give up** («🏳️», any time, with a confirmation) – your character is shown, you are finished without a place.

Everybody sees the open question with the live counts and the last answered question; «My questions» lists your own
questions with their answers. The game ends when everybody is finished; who leads can also pass the turn on (⏭, e.g.
somebody left) or end the game at any time – then all characters are shown and only who found theirs has a place.
The result shows every character, the places and the coins.

**Coins for places 1–3:** set by the parents in Games › Wer bin ich? (default 10 / 5 / 2), paid once, only at a
table with **at least two people of the family** – never to guests. Every person gets a history entry (place, players,
their character).

### Kartenlauf

Games → **🏁 Kartenlauf**: a race board game with cards, played live – everybody on their own device. Play **alone
against bots** or open a **family table** (guests via QR code; bots fill the free seats when the game starts). Who
starts chooses (remembered): **2, 3 or 4 players**, **teams of two** (only with 4; partners sit opposite, on by
default), how well the bots play (easy / normal / hard), their reaction time and two house rules: «a 7 may move the
partner's marbles too» (off: only once your own are all home) and «the joker may be the card that wins» (on).

The board is always the 4-seat board: a ring of 64 fields, every seat with a start field, a kennel with 4 marbles and
4 home fields that branch off just before its start field. Two players sit opposite each other. Every round deals
**6, 5, 4, 3, 2** cards, then again 6 (two French decks with 6 jokers, a fresh deck with every 6); the dealer moves
on each round. With teams, every round starts with each player passing one card to the partner.

- **A** 1 or 11 forward or bring a marble out · **K** 13 or bring out · **Q** 12 · **4** 4 forward or 4 backward ·
  **2, 3, 5, 6, 8, 9, 10** that many forward · **Joker** any card.
- **J** swaps one of your marbles on the ring with another player's marble on the ring (not a protected one).
- **7** is split among your marbles (all 7 steps must be used); every marble passed over goes back to its kennel.
- A marble that just came out is **protected** on its start field: nobody may pass it or land on it until it moves.
- Landing exactly on a marble sends it back to its kennel (partner's and own marbles too).
- Into the **home** only forward, once the marble has left its start field, with the exact number and without
  jumping over marbles in the home (never backwards with the 4). Entering is optional – you may go round again.
- Who cannot play any card throws the cards away for this round.
- Alone: the first with all 4 marbles home wins (the others are ranked by marbles home and progress). Teams: with your
  4 home you play your partner's marbles; the team with all 8 home wins.

On the phone: tap a card, then the marble (the possible ones pulse; a choice like A 1/11/out or «into the home / on
along the ring» opens a small menu); the jack asks for the second marble; the 7 is split by tapping your marbles
(step counter, «−» per marble, then «Play»); the joker first asks which card it stands for. Moves are animated along
the track; the last move, the played card and the dealer are shown.

**Coins for places 1–3:** set by the parents in Games › Kartenlauf (default 10 / 5 / 2), paid once, only at a
family table with **at least two people of the family** – never alone against bots, to guests or to bots. With teams
both winners get place 1, the other team place 2. Every person gets a history entry.

### Stadt-Land-Fluss

Games → **🏙️ Stadt-Land-Fluss**: the classic word game live – everybody writes on their own device. Only people play
(the family and guests via QR code, no bots), at least two. Who opens the **family table** chooses (remembered):

- **3 to 8 categories**: Stadt, Land, Fluss, Tier, Name, Beruf (the default) and Pflanze, Essen, Gegenstand, Sportart,
  Schweizer Ort, Farbe, Musikinstrument, Körperteil, Spielzeug, Getränk – plus up to **2 own categories** (typed text);
- **3, 5, 8 or 10 rounds**; **time per round** 60 / 90 / 120 / 180 seconds or «until somebody calls Stopp!»;
- **«Stopp!»** on / off: who has filled every field (each answer starting with the letter) may call it – the others
  get **10 more seconds** (always on without a time limit);
- **difficult letters** C, Q, X, Y (off by default). Umlauts are never drawn, no letter comes twice in a game.

A round: the letter spins and lands, a countdown ring runs. One field per category (Enter jumps to the next field, a
✓ shows an answer that starts with the letter); answers are **saved while typing**, the server takes them until two
seconds after the end, so nothing is lost when the time runs out. «x of y finished» shows how many filled every field
– the answers of the others are never sent before the round is closed. Who leads can close the writing early.

**Checking:** an answer counts when it starts with the letter – capitals, accents and a leading article do not matter
(«die Aare» → A, «Écosse» → E, «Ägypten» → A). Empty or wrong-letter answers score 0. Then every device shows all
answers per category: tap **👎** on an answer of somebody else you find invalid – it is out when a **strict majority of
the other players** rejected it (with two players one 👎 is enough). Who leads can decide an answer with **✓ / ✗**
(this wins over the votes, also for a wrong letter). The review closes when everybody pressed «Done» or who leads goes
on. **Points per category:** the only valid answer 20, a valid answer nobody else gave 10, the same valid answer as
somebody else 5 (same text after the normalisation), invalid / empty 0. A scoreboard follows each round (with the
answers of the round); after the last round the result shows the ranking (a tie shares the place) with confetti for
the winner. Who leads can end the game any time: the rounds so far count (a round in its review is scored as it stands,
a round still being written is dropped).

**Coins for places 1–3:** set by the parents in Games › Stadt-Land-Fluss (default 10 / 5 / 2), paid once, only at
a table with **at least two people of the family** and only when at least one round was played – never to guests.
Every person of the family gets a history entry (place, points, rounds).

### Zeichnen & Raten

Games → **🎨 Zeichnen & Raten**: one draws, the others guess – live, everybody on their own device. Only people play
(the family and guests via QR code, no bots), 2 to 8 players. Who opens the **family table** chooses (remembered):

- **the words**: Animals, Jobs, Food & fruit, Things at home, Sports or **Mixed** (the default) – about 40 simple,
  drawable German words each (`zeichnen_data.py`);
- **how often everybody draws**: 1, 2 or 3 times (in seat order); **time to draw** 60 / 80 / 120 seconds;
- **hints** on / off: some letters of the word appear at 50 % and 75 % of the time (at most a third of the letters).

A turn: the drawer gets **3 words** to choose from (10 seconds, then one is taken at random) and draws on a square
canvas (touch or mouse): 10 colours, 3 brush sizes, eraser, undo of the last stroke, clear. The strokes go to the
server in small batches (normalised coordinates, every ~120 ms); the others see the drawing appear live – their app
asks only for what is new (a cursor), at most 30 000 points per drawing. The guessers see the word only as a mask
(«_ _ _ _», the number of letters, the hint letters) and type guesses. A guess is right when it matches the word or an
alias – capitals, accents, umlauts (ä = ae = a), ß, der / die / das / ein …, spaces and hyphens do not matter; words of
five letters or more allow **one typo**. One or two letters off: only the guesser sees «Close!». Wrong guesses appear in
the chat for everybody – except guesses that contain the word (only the guesser sees them); a right guess is never
shown, the chat says «Mia guessed it! ✅».

**Points:** a right guess gets 50 + 50 × the part of the time left, less 10 % for each player who found it before (at
least 10) – the first and fastest gets the most; the drawer gets **10 points per player who found the word**. The turn
ends when everybody found it or the time is up; the word is shown to all for 3 seconds, then the next drawer. Who leads
can **skip** a turn (the points so far stay) and **end** the game (a drawing in progress counts as it stands). After the
last turn the result shows the ranking (a tie shares the place) with confetti for the winner and the list of words.

**Coins for places 1–3:** set by the parents in Games › Zeichnen & Raten (default 10 / 5 / 2), paid once, only at a
table with **at least two people of the family** and only when at least one turn was played and somebody scored – never to guests. Every
person of the family gets a history entry (place, points, words drawn).

### Fünf Würfel

Games → **🎲 Fünf Würfel**: the dice game with five dice and a score sheet (after the public-domain «Generala / Yacht»
family), played live – everybody rolls **at the same time** on their own device. Play **alone against 1–5 bots**
(levels easy / normal / hard, reaction time as in the other games) or open a **family table** (up to 6 players,
optionally with bots; guests via QR code). The dice are rolled on the server, the app only animates them.

A game has **13 rounds**. In every round each player rolls up to **3 times**; between the rolls tap dice to **hold**
them (they are not rolled again). Then the player fills **one free box** of their sheet – the app shows the points every
free box would give – or crosses one out with 0. When everybody has filled a box, the next round starts (meanwhile the
app shows who is still rolling). Everybody sees all sheets; nobody can touch somebody else's dice.

| Box | Points |
|---|---|
| Ones … Sixes | the sum of the dice with that number – **35 bonus** with 63 or more in this upper section |
| 3 of a kind / 4 of a kind | 3 / 4 alike: the sum of all dice |
| Full house | 3 + 2 alike (two different numbers): 25 |
| Small straight / Large straight | 4 / 5 in a row: 30 / 40 |
| Fünfling | 5 alike: 50 |
| Chance | the sum of all dice |

House rule (start dialog, on by default): **+50 for every further Fünfling** when the Fünfling box already holds 50.
The highest total wins (a tie shares the place); the result shows the ranking with confetti and every sheet. Who
leads may **end** the game early: the sheets count as they stand, but without coins.

**Coins for places 1–3:** set by the parents in Games › Fünf Würfel (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone against bots, to
guests or to bots. Every person of the family gets a history entry (place, points).

### Heimwärts

Games → **🏠 Heimwärts**: the classic cross-and-circle race board game (public-domain mechanics of the Pachisi / Ludo
family) with its own board. Play **alone against 1–3 bots** (levels easy / normal / hard, reaction time as in the other
games) or open a **family table** (2 to 4 players, optionally with bots; guests via QR code). Everybody plays on their
own device; the die is rolled on the server, the app only animates it.

The board has a shared track of **40 fields** (10 per colour), clockwise, each colour with a yard of **4 pieces**, a
start field (★) and **4 home fields**; each player sees their own colour at the bottom. On your turn tap the die, then
tap one of the glowing pieces – only legal moves glow, the target fields are marked. With only one possible move the
piece moves by itself after a moment; with none the turn passes by itself.

- A **6** brings a piece out of the yard onto your start field (if no own piece stands there) – and **every 6 rolls again**.
- No piece out on the board (all in the yard, or the rest settled in the home)? **Three tries** to roll a 6.
- Landing on another player's piece sends it **back to its yard**; two own pieces never share a field.
- The **start fields are safe**: a piece there cannot be hit, pieces of different colours may share it.
- After a full round a piece goes into its **home** – never jumping over a piece in the home.

Rule options (start dialog, remembered):

| Option | Default | Effect |
|---|---|---|
| Benches (Eile mit Weile) | off | 4 more safe benches halfway along the arms. A piece on a start field or a bench cannot be hit, and **no other piece may pass or land there** – only the owner of a start field coming out of the yard sends a piece sitting on it back home |
| Exact number into the home | on | off: a piece goes as deep into the home as the number and the free fields allow |
| Play on for places 2 and 3 | on | off: the game ends when the winner is in, the others are ranked by how far they are |

The first with all 4 pieces home wins; with «play on» the game ends when one player is left (or only bots are left).
Bots: easy moves mostly at random, normal prefers hitting, coming out and the leading piece, hard also weighs safe
fields and the danger from pieces up to 6 fields behind. Who leads may **end** the game early: ranked as it stands,
but without coins.

**Coins for places 1–3:** set by the parents in Games › Heimwärts (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone against bots, to
guests or to bots. Every person of the family gets a history entry (place, pieces home).

### Jump

Games → **🦘 Jump**: a live jumping race. Every player has their **own lane** – all lanes are stacked on the screen, your
own one big at the bottom with your avatar on the right, the others small above it (with their small avatars). The
obstacles come from the left; tap the **big jump button** (or your own lane, or press the space bar) to jump over them.
Play **alone** (high score: run as far as you can – your **personal best** is kept; optionally with 1–5 practice bots)
or open a **family table** (1 to 6 players, optionally with bots; guests via QR code). Everybody plays on their own device.

- **Same obstacles for everybody:** the server picks a seed, every app builds the same course from it, and all lanes
  run on the same game clock (a 3-second countdown after the start).
- **It gets faster:** the speed grows steadily (the maximum after about 2 ½ minutes); from medium speed there are also
  double crates, at high speed long hedges.
- **Crates are safe to land on:** come down on top of a crate and you stand on it and run along (you can jump on from
  there, or just walk off its end). Only running into its **side** costs a life (a little landing grace: feet a bit
  below the top still land on it).
- **Cacti** (green, with spikes and a flower) and hedges sting: touching one – also landing on it – costs a life.
- **Cloud parcours:** after about **45 seconds** (and then again about a minute after the end of the last one) a
  signpost and a blinking banner «Cloud course ahead!» announce it (about 3 seconds of free ground before it). Then
  come 4–6 crates floating on clouds (heights a little above a normal jump over a crate, never more than a small step
  up or down from one to the next), a short jump apart, over a **dense cactus field**: jump from crate to crate.
  Falling down onto the cacti costs a life (one per piece of the field, then you hop up and blink – you can jump back up
  onto the next cloud crate from the ground). After the last crate there is free ground to land on, then the normal
  course goes on. The jumps are fair for children: about half a second of good jump times for each crate.
- **Jumping:** only from the ground or a crate (no double jumps in the air); a jump just after walking off an edge
  still counts.
- **Lives:** everybody starts with 3 (start dialog: 1 / 3 / 5). Every hit costs a life, then you hop up a little and
  blink for a moment (invulnerable). Without lives you are out – the lane shows how far you came.
- **The others:** their jumps and lives show in their lanes – drawn a moment late, from the jump times their apps report.
- **The end:** at a family table the **last one still running wins** (the game ends when one is left or no person is
  left); alone you run until you are out. Places: who stayed in longest; the distance (m) is the score.
- **Bots** (easy / normal / hard) run the same physics: they look ahead for the jump times that get them past the next
  danger (over a cactus, onto a crate, onto the next cloud crate) and aim for the middle with a small timing error, and
  now and then forget to jump – the faster the game, the more they miss.

The jump physics run in the app (no waiting for the network), step by step 120 times a second – the same code in the
app and on the server (for the bots), so every app draws the others' lanes exactly from their jump times. The app
reports its jumps and hits to the server, which keeps the lives and the state per player and checks only sane values (a
time near the game clock, an obstacle that really passes then – never a cloud crate –, one life per obstacle). An app that stays silent for 12 seconds is out (left the game). Who leads
may **end** the game early: ranked as it stands (the ones still running by their lives), but without coins.

**Coins for places 1–3:** set by the parents in Games › Jump (default 10 / 5 / 2), paid once, only for a game played
to the end at a family table with **at least two people of the family** – never alone, to guests or to bots. Every
person of the family gets a history entry (place, distance, new personal best).

### Star Runner

Games → **🌠 Star Runner** (Sternschnuppen-Lauf): a live endless runner with its own little story – at night the big
lantern of the village went out; the children run as forest messengers along a forest path and catch the falling
**star sparks ✨** to light it again. The path has **three lanes**; you run with **your own avatar** (face, hair,
outfit and worn items on running legs), seen from the front, the village with its lantern on the horizon – the more
sparks you catch, the brighter it glows.

- **Controls:** swipe **left / right** to change the lane, **up** to jump, **down** to duck. On a computer the arrow
  keys or W A S D (space jumps); four buttons ◀ ▲ ▼ ▶ below the path work everywhere.
- **On the path:** fallen **logs** and **puddles** (jump), **low branches** with hanging vines (duck), **rocks** and
  **tree stumps** that block a lane (change the lane), sparks on the ground and high above some logs (jump for them).
  Every row of obstacles leaves at least one lane open; the speed grows (the maximum after about 2 minutes), the rows
  come closer together.
- **Everybody at the same time:** alone (high score, optionally with 1–7 practice bots) or at a **family table** (1 to
  8 players, optionally with bots; guests via QR code). Everybody runs the **same course** (a seed of the server) on
  their own device; the others run along as **translucent ghosts** with their avatars and name tags – the ones with
  more sparks a little ahead, a player who is out stays behind. Ghosts never collide with you. Above the path a live
  **mini ranking** (points, 💥 for who is out).
- **Lives:** 3 (start dialog: 1 / 3 / 5); a hit costs one, then you blink for a moment. **Time:** 2 / 3 / 5 minutes
  (default 3). The run ends when no person is running any more or the time is up.
- **Points:** every metre 1, every spark 10. Places by points (the same points share the place). Personal best (points)
  is kept.
- **Bots** (easy / normal / hard) play by the same rules: they plan their swipes a moment ahead with a timing error and
  now and then a mistake (forget to jump or duck, swerve too late) – the faster, the more mistakes.

**What the server decides:** the app runs the game at 60 fps by itself, but reports only its **inputs** (each swipe with
its game time). The server replays them on the course with the same rules and decides **itself** which obstacle hit
and which spark was caught – an app cannot report a distance, sparks or "no hit". An input counts only when it arrives
in time: not before the previous one, not ahead of the server's clock and not for a part of the course the server
already settled (1.5 s behind the game clock), so nobody can dodge afterwards. An app that stays silent for 10 seconds
is out. Who leads may **end** the game early: ranked as it stands, without coins.

**Coins for places 1–3:** set by the parents in Games › Star Runner (default 10 / 5 / 2), paid once, only for a game
played to the end at a family table with **at least two people of the family** – never alone, to guests or to bots.
The winner gets the «No. 1» hat. Every person of the family gets a history entry (place, points, metres, sparks, new
personal best). In the parent area › Games the runner can be active, active without bots or inactive.

### Snack Rush

Games → **🍔 Snack Rush** (German «Imbiss-Express»): a live snack-stand race. Every player runs their **own snack stand**
on their own device, all at the same time, and **all stands get the same customers**. Play **alone** (high score: your
**personal best** till is kept; optionally with 1–5 practice bots) or open a **family table** (1 to 6 players,
optionally with bots; guests via QR code).

The screen (one phone screen, no scrolling): on top the **till 💰**, your stars ⭐, angry customers 😡 and the time left;
below it a chip for every other player with **their till and their angry customers** (updated about every second);
then the **counter** with up to 4 customers (their order, their mood 😊 → 😐 → 😠 → 😡 and a patience bar; more customers
wait in the line «+2 🚶»), the **shelf** with the ready food and the **bin**, and the **kitchen** with its stations.

- **Foods and steps** (each step takes its time – a ring runs round; the stations have 2 places, the prep counter 3):
  burger = grill 4 s → assemble 2 s · hot dog = pot 3 s → into the bun 1.5 s · fries = fryer 5 s → salt 1 s ·
  drink = fill 3 s · pizza = oven 6 s · ice cream = machine 2 s. Who opens the table chooses the foods on the menu.
- **Playing:** tap an empty place of a station to start its food; tap the done food to move it on (to the prep
  counter, or onto the shelf). **Take it off in time:** grill and fryer burn it 4 s after it is done, the oven after
  5 s, the ice cream melts after 6 s – tap it into the bin. Tap a **customer** to hand over what they ordered from the
  shelf (or tap a food on the shelf: it goes to the customer who has waited longest for it). When the whole order is
  there, the customer pays.
- **Money (the game's own pretend money 💰, not the coins of the app):** every step costs its ingredients when it starts
  (burger 2 + 1, hot dog 2 + 1, fries 1, drink 1, pizza 3, ice cream 1 – half on «easy»). A served customer pays the
  prices (burger 8, hot dog 6, fries 4, drink 3, pizza 7, ice cream 4) plus a **tip** for fast service: 3 stars (more
  than 60 % patience left) +3, 2 stars +1, 1 star nothing. The till = earnings − ingredients.
- **Angry customers** walk away without paying. What was already handed to them goes back onto the shelf for the next
  customer who wants it. Food on the shelf gets **cold after 25 seconds** and goes into the bin (the money is lost –
  the app shows «🗑️ −💰…»).
- **It gets harder:** customers come more often, order more (1 → 3 foods) and are less patient – the full rush after
  about 4 minutes. Level easy / normal / hard: how often customers come and how patient they are.
- **Duration:** 3, 5 (default) or 8 minutes – the **most money in the till wins** (then more served customers, more
  stars, fewer angry ones; the same shares the place). Optional «Out after angry customers» (off by default, or 3 / 5 /
  8): with that many angry customers you are out (your till stays); the game ends early when no person is left in.
- **Bots** (easy / normal / hard, the level of the table) work through the customers in order: a reaction time, some
  seconds of work per food, sometimes they forget a part (costs time and ingredients) and they let hopeless customers
  go – so they fall behind when it gets busy.

The kitchen runs in the app (no waiting for the network). The server makes the customer stream from a secret seed (the
apps only get the customers of the next seconds), and the app reports its serves, the customers it saw leave angry and
the money spent. The server checks every serve: each customer only once, not before they came, not after their patience
ran out, not in the future – and the stand must have been able to make the food: every serve books its foods step by
step on the earliest free place of each station (food made ahead at most 90 seconds before), the last step must be done
by the serve. A customer without a valid serve is angry – the server decides that itself 4 seconds after the patience
ran out. The money spent counts at least the ingredients of every served food. When «Out» is on, an app that stays silent
for 20 seconds is out. Who leads may **end** the game early: ranked as it stands, but without coins.

**Coins for places 1–3:** set by the parents in Games › Snack Rush (default 10 / 5 / 2), paid once, only for a game
played to the end at a family table with **at least two people of the family** – never alone, to guests or to bots. The
winners get the «No. 1» hat. Every person of the family gets a history entry (place, till, served customers, new
personal best). In Games the parents can switch the game on, off or to «active without bots».

### Traffic Cadet (Verkehrskadett)

Games › **🚦 Traffic Cadet**: a live traffic game. Every player regulates the traffic lights of **their own map** on
their own device – all maps get the **same streets and the same cars** (from the server). Alone (optionally with
practice bots), at the family table (1–6 players, bots fill up, guests via QR code).

- **Switching:** tap a traffic light on the map (or its big button below the map) – it switches its whole group (e.g.
  «1 ↓↑» = north and south together): green → **amber** (1.5 s) → red, red → green at once. At the start of every
  world all lights are red.
- **The cars:** cars, buses (slower, longer), bikes (slow) and now and then an ambulance 🚑. They stop at red (and at
  amber when they still can), go at green, keep their gap and turn as their route says. Cars queue outside the map when
  there is no room («+3» at the edge).
- **Accidents 💥:** two cars of crossing or merging routes in the junction at the same time crash; both block the way
  for 4 seconds (the others wait), then they are towed away. So: switch one direction red, wait until the crossing is
  empty, then the other green.
- **Moods:** waiting makes drivers annoyed (😐 → 😠) and then angry 😡 (difficulty normal: after 10 / 20 seconds of
  waiting; easy 12 / 24, hard 7 / 14). The ambulance is in a hurry: angry after 6 seconds. Angry drivers honk.
- **Out:** too many accidents or angry drivers, counted over all worlds – easy 5 / 15, normal 3 / 10, hard 3 / 8. Who
  is out watches the others' live stats.
- **Worlds** (start dialog: 1–5), each 5 s intro («World 2: T-junction») + 90 s of traffic, the traffic grows during a
  world: 1 **simple crossing** (only straight on, 2 groups) → 2 **T-junction** with a left-turn lane (3 groups) →
  3 **crossing with turning lanes** (straight/right and left separately, 4 groups) → 4 **two connected crossings** (the
  road between them can fill up and block the crossing behind) → 5 **roundabout** (the drivers yield to the ring by
  themselves; you have a stop/go light at every entry to give the others a gap). Everybody still in moves on together.
- **Difficulty** (easy / normal / hard): how many cars come, how patient the drivers are, how many accidents / angry
  drivers put you out.
- **Live bar:** at the top every other player's accidents 💥, annoyed 😠 and angry 😡 drivers and cars through 🚗
  (updated about every second), below my own stats, the world and the time left in it.
- **Points:** every car through 1 (bus 2, ambulance 3), minus 5 per accident and 2 per angry driver. **Places:** who is
  still in after the last world by points; who is out after them (who lasted longer first). At a family table the
  game ends when only **one is left standing**. Alone your best points are kept.
- **Bots** (easy / normal / hard) run the same simulation on the server: they give green to the set of groups with the
  most waiting cars, switch with a clearance pause (amber, then until the crossing is empty) – easier bots forget the
  pause more often (crash risk) and leave a direction green too long.

The map is simulated in the app (10 steps per second, integer arithmetic only) from the server's world (layout + the
stream of cars from the game's seed) and the player's switches; the app reports only its switches (with their tick).
The server runs **the same simulation** about 1.5 s behind (identical in Python and JavaScript – tested) and its result
counts: accidents, angry drivers, cars through, out. A switch for a moment the server simulated already is refused and
the app rebuilds its map from the server's snapshot. An app silent for 15 seconds is out. Who leads may **end** the
game early: ranked as it stands, no coins. Parents › Games: active, active without bots (no practice bots, no bots at
the table) or inactive.

**Coins for places 1–3:** set by the parents in Games › Traffic Cadet (default 10 / 5 / 2), paid once, only for a game
played to the end at a family table with **at least two people of the family** – never alone, to guests or to bots;
the winner gets the «No. 1» hat. Every person of the family gets a history entry (place, points, cars, accidents, angry
drivers).

### Klatsch den Beat

Games → **👏 Klatsch den Beat**: a live rhythm game – **everybody plays at the same time**, each on their own device.
Every round the app plays a short beat with its own drum sounds (kick, clap, hi-hat – made in the browser, no sound
files), then everybody **claps it back** on the big clap button. Play **alone** (personal best; optionally with 1–7
practice bots) or open a **family table** (1 to 8 players, optionally with bots; guests via QR code). Turn the sound on!

- **A round** (call and response): a **count-in** of four clicks, then **listen** – the pattern sounds over the groove and
  its dots light up on a bar of 16 steps; then the **clap bar** – the same dots stay, a playhead sweeps over them, clap
  when it reaches a dot. A short pause shows your points and the live ranking, then the next round starts by itself.
  We chose this variant over notes sliding to a hit line: you hear the beat first (the fun part of clapping along) and
  the dots still help children who cannot remember the whole pattern.
- **It gets harder:** the tempo rises from 80 to 140 BPM over the rounds (5–8, start dialog); first quarters and eighths
  on the «one», then syncopes (off-beat eighths, a missing «one»), at the end sixteenth syncopes and pauses. Notes are
  always at least an eighth apart. The server makes the patterns (random), everybody gets the same ones.
- **Points:** every note takes the nearest clap – within **±60 ms perfect** (100 points), within **±130 ms good** (50),
  else missed; a clap that hits no note costs 25 points (no drumming through), never below 0 per round. Most points
  win; the same total shares the place. The result also shows the accuracy (perfect = 1, good = ½ of a note).
- **Fair timing:** every app knows the server clock (it estimates the offset from the server's answers, the one with
  the shortest round trip counts), plans the sounds on the audio clock and reports its claps as game times; the server
  judges them a second after each clap bar for everybody at once. Phones and Bluetooth headphones play sounds late:
  **calibrate** once (🎚️ – tap along to 8 clicks); the delay is kept on this device and subtracted from your claps.
  A tap vibrates the phone where the browser supports it; the space bar claps too.
- **Bots** (easy / normal / hard) clap every note with a timing error and now and then miss one or clap once too much.

Who leads may **end** the game early: the rounds already played count, ranked as it stands, but without coins. The
accuracy of a game played to the end is your **personal best** (alone or at a table).

**Coins for places 1–3:** set by the parents in Games › Klatsch den Beat (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone, to guests or to
bots. The winners get the «No. 1» hat; every person of the family gets a history entry (place, points, accuracy).

### Verbotene Wörter

Games → **🚫 Verbotene Wörter**: the explaining game – one explains a word **without saying the forbidden words**, the
others guess aloud. Everybody has the app on their own device; the talking happens at the table. Only people play (the
family and guests via QR code, no bots), 2 to 8 players. Who opens the **family table** chooses (remembered):

- **the cards**: Easy (younger children), Normal or Mixed – about 370 built-in German cards, each with a word and
  5 forbidden words (`verboten_cards.json`);
- **time per turn**: 30 / 45 / 60 / 90 / 120 seconds (default 60); **how often everybody explains**: 1–4 times;
- **«Skip» costs** nothing or 1 point; **two teams with 4 or more players** on / off.

**Teams** (4 or more players, on by default): every second seat is in team A, the others in team B (who leads can mix
the seats in the lobby). The teams take turns, the members of a team explain in turn (a smaller team's members explain
a little more often, so both teams get the same number of turns). With 2 or 3 players – or teams off – **everybody
plays for themselves**.

A turn: the explainer taps **Go!** and the clock runs (kept by the server). Only the explainer sees the card – with
teams also the **other team** (the classic rule: they watch for forbidden words); the explainer's own team never gets
the card on their device, they see the clock, the score and how many cards are done. The explainer taps:

| Button | Points |
|---|---|
| ✅ Got it | +1 for the team – alone: +1 for who guessed it (the explainer taps the name) **and** +1 for the explainer |
| 🚫 Forbidden word | −1 for the explainer's team (alone: the explainer) |
| ⏭ Skip | 0 or −1 (start dialog) |
| 🔔 Buzz (the other team) | −1, like «Forbidden word» |

Then the next card comes. Every tap names its card, so a buzz and a tap at the same moment count only once. When the
time is up, the card on the table does not count; everybody sees the cards of the turn and the next explainer gets
ready. Who leads can **skip** a turn (e.g. the explainer left) and **end** the game (a turn in progress counts as it
stands). The result shows the ranking (a team shares its place, a tie shares the place), confetti for the winners and
every card of the game.

**Coins for places 1–3:** set by the parents in Games › Verbotene Wörter (default 10 / 5 / 2), paid once, only at
a table with **at least two people of the family** and only when at least one turn was played and somebody scored –
never to guests. Every person of the family gets a history entry (place, points, team, cards explained); the winners
get the «No. 1» hat.

### Jass

Games → **♣️ Jass**: the Swiss card game **Schieber** (traditional rules). **4 players in 2 teams** – partners sit
opposite. Play **with 3 bots** (levels easy / normal / hard, reaction time as in the other games) or open a **family
table**: any mix of the family, guests (QR code) and bots – free seats are taken by bots (alone with 3 bots, 2 children
with 2 bots, …). With two people and two bots the people play together as partners (start dialog; off: against each
other); who leads can **mix the seats** in the lobby. Everybody plays on their own device, the server deals (with
`secrets`) and checks every card – the app only shows your own cards.

The screen: your hand fanned at the bottom (only the cards you may play light up – tap one to play it), your partner on
top, the opponents left and right with their number of cards, the trick in the middle, the trump and the score of both
teams on top (with the points of the running round). 🕘 shows the last trick, 📋 the score sheet (every round).

- **Cards**: Swiss (Schellen, Schilten, Rosen, Eicheln; 6–9, Banner, Under, Ober, König, Ass) or French (♠ ♥ ♦ ♣;
  6–10, J, Q, K, A – the J counts as Under, the Q as Ober). 36 cards, 9 each.
- **Choosing the game**: who is on turn chooses **Trumpf** (one of the 4 suits), **Obenabe** (no trump, the Ass is
  highest) or **Undeufe** (no trump, the 6 is highest) – or **pushes** («schieben») to the partner, who must then
  choose. In the first round the holder of the Schellen 7 (♦ 7) chooses, then the next player to the right. The player
  who chose (or pushed) leads the first trick; the winner of a trick leads the next one.
- **Following**: follow suit if you can; you may always **trump in** instead – but never **under-trump** (play a trump
  lower than one already in the trick) unless you only hold trumps. Trump led: you must follow with trump – except when
  the **Buur** is your only trump (he may always be held back).
- **Ranking**: trump Buur (Under / J) > Nell (9) > Ass > König > Ober > 10 > 8 > 7 > 6; other suits and Obenabe
  Ass > König > Ober > Under > 10 > 9 > 8 > 7 > 6; Undeufe the other way round.
- **Points**: trump Buur 20, Nell 14, Ass 11, König 4, Ober 3, 10 10; other suits Ass 11, König 4, Ober 3, Under 2,
  10 10; Obenabe and Undeufe: the 8 counts 8 (Undeufe: the 6 counts 11, the Ass 0). The last trick **+5** – always
  157 per round; all 9 tricks to one team (**Match**) **+100**.

Rule options (start dialog, remembered):

| Option | Default | Effect |
|---|---|---|
| Cards | Swiss | Swiss or French cards (the card backs as in Tschau Sepp) |
| Game to | 1000 points | 500 / 1000 / 1500 / 2500 points (checked at the end of a round – both teams over it: more points wins) or 1 / 2 / 4 / 8 / 12 rounds |
| Weis | on | declared with the first card (automatically): 3 in a row 20, 4 in a row 50, 5 in a row 100, 6 / 7 / 8 / 9 in a row 150 / 200 / 250 / 300; 4 Under 200, 4 Nell 150, 4 Ass / König / Ober / 10 100. Only the team with the **best single Weis** (more points, then more cards, then the higher card – Undeufe the lower –, then trump, then who played first) writes **all** of its Weis; the cards are shown after the first trick |
| Stöck | on | König and Ober of trump in one hand: 20 points, announced with the second of them, always counted |
| Multipliers | off | Rosen / Schellen (♥ ♦) ×1, Schilten / Eicheln (♠ ♣) ×2, Obenabe / Undeufe ×3 – the whole round counts that many times |
| Partners | on | two people with two bots play together |

After a round the result stays on the table for a moment (cards, Match, Weis, Stöck) – **Next round** deals at once.
Bots: easy plays mostly at random, normal follows simple rules (take a trick with points, give points to the partner),
hard counts the cards, pulls trumps, gives points («schmieren») when the partner's card is safe, chooses the trump by
the strength of its hand and pushes a weak hand. Who leads may **end** the game early: ranked as it stands, but without
coins.

**Coins:** the members of the **winning team** get the coins for place 1 (set by the parents in Games › Jass,
default 10), paid once, only for a game played to the end at a family table with **at least two people of the family**
– never alone against bots, to guests or to bots. Every person of the family gets a history entry (won / lost, the
points, the partner); the winners get the «No. 1» hat (not on a tie).

### Werwölfe

Games → **🐺 Werwölfe**: the classic social deduction party game, played in **one room** – the app is the game
master. Everybody has the app on their own phone (the family and guests via QR code), **2 to 12 people** – a game
has 5 to 12 players: with **fewer than 5 at the table, bots fill it up to 5** when who leads begins (the animal bots
of the card games, with their emoji). Who opens the **family table** chooses (remembered; also changeable in the lobby
once everybody is there):

- **the roles**: *by the number of players* (recommended) – 5: 1 werewolf + seer · 6: + witch · 7: 2 werewolves ·
  8: + hunter · 9–10: + Amor · 11–12: 3 werewolves – or by hand: 1–3 werewolves and seer / witch / hunter / Amor on or
  off (fewer werewolves than half of the players); everybody else is a villager;
- **time to talk by day**: 1, 2, 3 (default), 5 or 10 minutes;
- **fill with bots up to**: 5 (default) to 12 players – more bots for a bigger game (no bots when enough people are
  there).

**Bots** play every role and act by themselves after a short «thinking» time (at night 4–10 seconds, so the length of
a step does not give away who holds the role; in the vote one after the other): Amor links two random players, a bot
werewolf bites the choice of a human werewolf (else a random non-werewolf – the bot werewolves always agree), the
seer looks at a random player, the witch heals the victim about every second time and rarely poisons somebody, the
hunter shoots a random player; in the vote a bot werewolf votes for a non-werewolf, the other bots for a random
player – a bot seer votes for a werewolf she saw, and while she lives the other village bots lean the same way. A
bot's role stays as secret as a person's. The talk timer runs as before; who leads still lets the night fall and
opens the vote.

| Role | Power |
|---|---|
| 🐺 Werewolf | at night chooses a victim together with the other werewolves (they know each other) |
| 🧑‍🌾 Villager | none – talk, listen, vote |
| 🔮 Seer | every night sees the role of one living player (only she sees it) |
| 🧪 Witch | sees the werewolves' victim; one healing potion and one poison potion for the whole game (both in one night is allowed, she may heal herself) |
| 🏹 Hunter | when he dies (night or vote) he shoots one living player |
| 💘 Amor | in the first night links two players (himself allowed) as lovers: when one dies, the other dies of grief |

**The game:** everybody looks at their secret role (tap the card to reveal, tap again to hide – the 🎭 button shows
it again later). Who leads lets the **night** fall: all phones show a dark «eyes closed» screen, only the active role
gets its buttons, in this order: **Amor** (first night) → **werewolves** → **seer** → **witch** (a role that is dead
is not called). The werewolves see each other's choice; when **all living werewolves agree**, the victim is chosen.
If who leads moves on, the target with the most werewolf votes counts – a tie: nobody dies. **Day:** the village
learns who died and their role (not how – poison and werewolves look the same), then the talk timer runs (who leads
may skip it). **Vote** on every phone (or abstain; a vote can be changed until everybody voted): the player with the
**most votes is out** and their role is shown – a **tie (or no vote): nobody is out**. A dying hunter shoots first.

**Win:** the **village** when all werewolves are dead (everybody who is not a werewolf wins, dead or alive); the
**werewolves** when at least as many werewolves as others are alive; the **lovers** – a werewolf and a non-werewolf –
when they are the last two alive (only the two win). **Dead players** are spectators: they see every role and the
werewolves' choice and cannot act. **Secrecy:** every phone gets from the server only what this player may know –
the own role, fellow werewolves (for werewolves), the lover (for the lovers and Amor), the seer's results (seer),
the victim and the potions (witch).

**The narrator:** the phone of who leads (who opened the table, or a parent) shows the narration in big text and
plays a sound at every step; it also reads it aloud with the voice of the device (🔊 / 🔇 in the leader bar). Who
leads can **move on** when somebody is idle (every step has a default: no lovers, the most werewolf votes, no look,
no potion, no shot, close the vote) and **end** the game (no winner, no coins).

**Coins:** set by the parents in Games › Werwölfe (the amount of place 1, default 10): every person of the
family on the **winning side** – only at a table with **at least two people of the family**, only for a game played
to the end, paid once, never to guests or bots. The winners get the «No. 1» hat; every person of the family gets a
history entry (won or lost, the role) – bots none.

### Schach (chess)

Games → **♟️ Chess**: chess with the full standard rules. The card lists **your games** (running and paused – tap
one to continue), the **invitations** to you and the open seats, and three ways to start:

- **🤖 Against the bot** – easy (mostly random moves, captures preferred), normal (looks two half-moves ahead:
  material and mobility) or hard (thinks 3–4 half-moves deep with piece-square tables; answers within about 2 s).
  Choose your colour (white, black or random).
- **👥 Against the family** – invite one person of the family (the invitation shows up on their start page and in
  their chess card; they join or decline) or leave the seat **open for anybody** of the family – guests join via QR
  code (👥 Invite guests). The game starts when the second player joins; each plays on their own device.
- **📱 Two on one device** – pass and play: the board turns to whoever is to move.

**Clock** (optional): 5, 10 or 15 minutes per side, no increment. Who runs out of time loses – a draw if the other
side has nothing left to mate with.

**Playing:** tap a piece, then one of the marked squares (dots; a ring for a capture). The last move is highlighted,
a king in check glows red, captured pieces and the material lead show next to each player, the move list (in
standard notation) folds out under the board. A pawn on the last rank asks which piece it becomes. The server
checks every move: check, castling (not out of, through or into check), en passant, promotion.

**The end:** checkmate, stalemate, the same position for the third time (automatic draw), 50 moves without a capture
or a pawn move (automatic draw), not enough material to mate (K–K, K+B–K, K+N–K, bishops all on one colour),
resignation (🏳), a draw by agreement (½: the other player accepts or declines; the bot accepts only when it stands
clearly worse; on one device the draw is agreed at once), or time.

**Pausing:** either player taps **⏸ Pause** – the clock stops, nobody can move, the game waits in the database
(also over a restart) until a player taps **▶ Continue**. Several games per person at a time (up to 12 unfinished).
A game alone (bot or one device) with a clock pauses by itself when you leave it. Who started a game or a parent
can **delete** a paused game (🗑) or an open invitation. The parent area lists every chess game (Games › Chess)
and **Running games** lists them too (paused ones marked ⏸) – «End» there ends a game without a result, no coins.

**Coins:** set by the parents in Games › Chess (three numbers, default 10 / 5 / 2): the winner of a game
between **two people of the family** / a win against the **hard bot** / against the **normal bot**. Only the winner,
only after at least **10 own moves**, paid once – never against the easy bot, never on one device, never against
guests. The winner of a game between two people of the family gets the «No. 1» hat; everybody of the family who
played gets a history entry (won / lost / draw, against whom, how it ended).

### Dorfmarkt

Games → **🏘️ Dorfmarkt**: a property-trading board game in a Swiss village – generic mechanics of the genre with its
own board, names, cards and look. Play **alone against 1–5 bots** (levels easy / normal / hard, reaction time as in the
other games) or open a **family table** (2 to 6 players, optionally with bots; guests via QR code). Everybody plays on
their own device; the server rolls the two dice and checks every rule. Money is counted in **Taler** – the game's own
play money, not the coins of the app.

**The board** is a square ring of 36 fields: the corners **Markttag** (start – passing or landing brings 200 Taler),
**Gemeindehaus** (just visiting, or sitting in the «Gemeindeversammlung»), **Dorfplatz** (a free rest) and «Ab in die
Gemeindeversammlung»; 20 village shops and places in **8 colour groups** of 2–3 (from the farm shop and the bee house
up to the chocolate workshop and the watchmaker), **4 village bus stops**, 2 works (Wasserwerk, Elektrizitätswerk),
2 **Zufall** and 2 **Dorfkasse** card fields with own, kid-friendly cards, and 2 fees (Gemeindesteuer 100,
Vereinsbeitrag 75). Tap a field for its card (price, rents, owner); 🔎 zooms into the board (scrolling only inside the
board).

- On your turn tap the dice. A **double** rolls again; the third double in a row goes straight to the meeting.
- A free field: **buy** it at its price, or leave it (option **auction**: then everybody may bid once – sealed, 30
  seconds, the highest bid wins).
- A field of another player: pay the **rent** – double for an unbuilt field when the owner has the whole colour
  group. **village bus**: 25 / 50 / 100 / 200 for 1–4 stops of the owner; **works**: 4 × the dice (10 × with both).
- With a whole colour group (no mortgage in it) build **Marktstände** (1–4, evenly across the group) and then a
  **Markthalle**; buildings sell back for half. Option **mortgages** (on): a field without buildings in its group
  gives half its price, no rent while mortgaged; paying back costs 10 % more.
- **Gemeindeversammlung**: pay 50 Taler, use a free pass card, or try to roll a double (3 tries; after the third:
  pay and go).
- **Trading**: offer own fields (without buildings in their group) and Taler for fields and Taler of another
  player; they accept or decline (bots decide by the value, harder bots are stricter).
- **Debts**: who cannot pay raises the money (sell, mortgage, «sell automatically») – or is **bankrupt**: everything
  goes to the creditor (to the bank: the fields are free again).

**Game length** (start dialog, remembered): **30 rounds** by default (10 / 20 / 30 / 50), or a time limit (30 / 45 /
60 / 90 minutes), or classic until one is left – with rounds or time the **richest** wins (Taler + fields at their
price, mortgaged at half + buildings). The game is always over when only one player (or no person) is left. Taler at
the start: 1000 / 1500 / 2000. Who leads may **pause** the game (nothing moves, the time stops) and **end** it early
(ranked as it stands, without coins). The whole game is stored in the database and survives a restart of the add-on.

**Coins for places 1–3:** set by the parents in Games › Dorfmarkt (default 10 / 5 / 2), paid once, only for a
game played to the end at a family table with **at least two people of the family** – never alone against bots, to
guests or to bots. The winners get the «No. 1» hat; every person of the family gets a history entry (place, worth).

### Escape Room

Games → **🗝️ Escape Room**: the live riddle game for the family – solve the riddles of every room to find the door
code and get out. Everybody plays on their own device (the family and guests via QR code, **no bots**). Every room is
a world of its own with its own look (the wizard's tower, the pirate cabin, the space station, the treehouse, the clock
workshop, the ice castle, the jungle temple, the dragon's cave): its **objects hide riddles** – tap one to open its
riddle – and a little animal has a tip. Who opens the **family table** chooses (remembered):

- **rooms**: 1 to 5;
- **difficulty**: easy (2 riddles per room), medium, hard (3 riddles per room) or **mixed** – the rooms get harder one
  after the other (2 or 3 riddles);
- **kinds of riddles** (several): logic & codes, words & letters, pictures & observation, patterns & sequences, maths,
  memory, maps & directions, mechanical puzzles, knowledge – with the number of riddles not played yet per kind;
- **play**: all together (one team, everybody sees the same room and may try) or **two teams** (every second seat;
  who leads can mix the seats in the lobby);
- **time limit**: none, 15, 30 or 45 minutes.

**The combined lock:** every solved riddle reveals a part of the door code, shown to the whole team – a digit with a
symbol (⭐ 3), a number, or a coloured gem with its position (🔴 #2). The door needs all parts together: the digits in
the order of the symbols shown on the door, the sum of all numbers, or the gems in the order of their positions. Then
the next room opens; after the last door the team is out.

**Hints and time:** up to 3 hints per riddle (the whole team sees them); a hint costs **60 seconds**, a wrong answer
(also at the door) **10 seconds**. The team's time is the real time plus these seconds. Memory riddles show their
picture only for a moment after «Peek» (as often as you like). Mechanical puzzles (rune lamps, sliding tiles, turning
rings, water pipes, lever board) are played on the device; the moves go to the server, which checks them.

**Two teams** play the same rooms with the same riddles, each with its own progress; you see the other team only as a
progress bar. The first team out wins – counting its hint and error seconds: the game ends as soon as the other team
cannot be faster any more. With a time limit the game ends when the time is up (then nobody escaped). Who leads (or a
parent, also in Games › running games) can end the game – then nobody escapes.

**The riddles** are made new for every game by the server (random numbers, words, pictures) – the app never gets a
solution, the server checks every answer. 56 riddle kinds (level in brackets: e easy, m medium, h hard):

| Kind | Riddles |
|---|---|
| Logic & codes | The clue lock (m h) · Number detective (e m) · Three chests (m h) · The animal bench (m h) · The big scales (e m h) · The number square (m h) |
| Words & letters | Mixed-up letters (e m h) · Secret writing (m h) · Rune alphabet (m h) · The worn-out sign (e m) · Mirror writing (e) · Hidden animal (m h) · Letters as numbers (m h) · The vowel thief (h) |
| Pictures & observation | Count carefully (e m) · The odd one (e m) · Two pictures (m h) · The stopped clock (e m) · The book shelf (e m) · Coloured candles (m) · The magic mirror (m h) |
| Patterns & sequences | Number row (e m h) · The bead necklace (e m) · The tile floor (m h) · Growing towers (e m) · Letter row (m h) · The cuckoo clock (m h) · Turning arrows (e m) |
| Maths | Fruit sums (e m h) · The coin purse (e m) · The magic square (m h) · Story sums (e m) · Number pyramid (m h) · The dice tower (e m) · The number machine (m h) |
| Memory | Glowing crystals (e m h) · The magic tray (m h) · Where was it? (e m) · Flashing numbers (m h) · Past the window (e m) |
| Maps & directions | The treasure map (e m) · The compass (e m) · Bridges and paths (m h) · The robot program (m h) |
| Mechanical puzzles | Rune lamps (e m h) · Sliding tiles (m h) · Turning rings (m h) · Water pipes (m h) · The lever board (e m) · Gear chain (e m h) |
| Knowledge | Counting legs (e m) · Mixing paint (e m) · The planets (e m) · Eggs or not? (e m) · The calendar (e m) · Corners (e m) |

The **word riddles** use 45 words in all 9 languages of the app (and English): every device shows the riddle in its
own language, the answer counts in any of them (without accents).

**Already played:** the family keeps a counter per riddle kind (setting `escape_played`). A new game takes the kinds
played least – the fresh ones first – so every kind comes once before one comes again; the **round** (shown in the
start dialog and in Games › Escape Room, e.g. «32 of 56 riddles not played yet – round 2») is the lowest counter + 1.
With few chosen kinds (e.g. only memory, 5 rooms) a kind can come twice in one game – with other numbers.

**Coins:** set by the parents in Games › Escape Room (default 10): every person of the family in the team that escaped
and won gets them (together: everybody, when out; two teams: the winning team) – only at a table with **at least two
people of the family**, never to guests, paid once. Every person of the family gets a history entry (out or not, rooms,
time, hints, team); the winners get the «No. 1» hat.

### Game corner

Family → **🕹️ Game corner**: small games that run on the device itself (only a duel on two devices goes over
the server; best times stay in this browser), shown when family games are on for the child:

- **Tic-Tac-Toe** – against the app (easy, medium, unbeatable), two players on one device, or on **two devices**:
  invite somebody of the family – the invitation pops up in their app; a tally of the rounds.
- **Sudoku** – 4×4 for beginners, 6×6, 9×9 easy / medium / hard; every puzzle has exactly one solution, wrong
  numbers turn red, best time per level.
- **Patience** – the classic solitaire: sort all cards by suit onto four piles, draw 1 or 3, undo, «Finish» when
  only open cards are left. Tap a card and it moves where it fits.
- **Ping-Pong** – against the app (easy, medium, hard) or face to face on one tablet; first to 7 points. Also on
  **two devices** (a duel) and as **doubles on up to four devices**: two teams of two, each with a paddle at the
  baseline and a short paddle (55 %) near the net that only moves along its line. Whoever opens the table plays the
  back paddle of team A and chooses who sits on the three other seats – a family member (the invitation pops up in
  their app) or a bot (easy, normal, hard) – and the points to win (5, 7 or 11). A seat whose person says «no thanks»
  can be given to somebody else or a bot; the match starts once everybody is ready. Every player moves only their own
  paddle and always sees their own team at the bottom. If somebody leaves, a bot plays on for them; if the host
  leaves, the match ends. Like the duels, doubles pay no coins and are kept in memory only.
- **Pairs** – turn over two cards and find the pairs: animals, fruit, vehicles, sea animals or **your own photo
  sets**; alone (fewest moves), against the app (it remembers more or less well) or 2–4 players on one device.
  Card back: four patterns or the **family crest**.
- **🧊 Cube solver** – helps to bring a mixed-up puzzle cube back to one colour per side. Choose **2×2** or **3×3**
  (4×4 is shown as «coming later»), then paint the colours you see on a **3D cube**: drag it with a finger or the
  mouse, or jump to a side with the six side buttons; pick a colour and tap a sticker. On small phones the flat
  **net** (▦) is easier. The 3×3 centres are fixed – hold the cube with **yellow on top and green in front**. 🧽 clears
  everything, ✨ fills in a solved cube, 🎲 mixes one to try it out. The colours stay in this browser, so a refresh
  loses nothing. **Solve** first checks the colours and says in plain words what is wrong – a colour used too often,
  stickers without colour, «This corner cannot exist: white-yellow-red», two colours of a corner swapped, a piece
  that is there twice (the stickers blink), or «one corner is twisted / one edge is flipped / two pieces are
  swapped» (a cube that cannot be solved like this – usually one sticker is painted wrong). Then a **step-by-step
  guide**: the move in standard notation (U D L R F B, ' = anticlockwise, 2 = twice) plus a sentence and an arrow
  («Turn the RIGHT side up ↑»), the 3D cube turns the layer and shows the result; ◀ Back, Next ▶, 🔁 show again,
  «Step 12 of 110», the next moves, and confetti at the end. The 3×3 is solved **layer by layer** like in the
  beginner's method, in seven phases with a short explanation each (white cross, white corners, middle layer,
  yellow cross, yellow edges, yellow corners to their place, turn the yellow corners) – about 135 moves on average,
  never more than about 200; the cube is never turned as a whole. The 2×2 is solved the **shortest way** (at most
  11 moves); the corner at the back, bottom left never moves. Everything runs on the device (the search in a Web
  Worker); nothing is sent to the server. Parents switch it on or off in Settings › Games like the other games.

**Photo sets** (parent area › Games › Paarjagd › «Own pictures: photo sets»): upload photos into named sets (every
photo becomes a pair; a set needs at least 3 photos) – used by the Paarjagd and the pairs game. **Family crest**
(parent area › Settings): design the family crest – name, an emoji, two colours and a
pattern (plain, split, quartered, diagonal band, chevron). Photos no set uses any more are deleted when you save.

### Guests

Whoever leads a family quiz or a bingo game can tap **👥 Invite guests**: a QR code appears. Friends or
grandparents scan it with their phone in the home network (direct access must be on), type a name and play along
– nothing else of the app is open to them. Guests are deleted with everything they did after 12 hours. Parents can
switch guests off under Settings → Games.

**Guest networks** (Settings → Access from the network): devices in these address ranges – e.g. your guest
Wi-Fi – can only open the guest page and play with an invitation; no family login, no app, no parent area.

### Pet sitting, pet hotel and the hamster

Away for some days (camp, holidays at the grandparents)? On the pet card, **🧳 Pet sitting**: hand the pet to a family
member until a day – they find it under «Pets in my care» and feed (paying the food), play and wash it; the bars keep
dropping as usual. Or book the **Family Quest pet hotel** for 1–30 days (Settings → «Pet hotel: coins per day», default
10, paid at once): no decay, no death, the pet comes back fed, happy and clean; fetched early, full unused days are paid
back. The **hamster** 🐹 (shop, 300 coins) runs in its wheel while it is healthy (every bar at least 50) and mines coins
for its owner – Settings → «Hamster: coins per day», default 15 (5 more than a day in the pet hotel).

### Pairs game: photos from Home Assistant Media and the crest as a picture

Settings → «Pairs game: photo sets and family crest»: every photo set takes its pictures either **from Home Assistant
Media** (Media → My media, the `/media` folder – the app reads it, nothing is changed there) or as an upload from the
device (iPhone photos in HEIC are turned into JPEG by the browser). Chosen pictures are copied into Family Quest and saved
right away. The **family crest** can be an own picture too (upload or Home Assistant Media); it is shown in the shield,
on the card backs and on the dashboard. After the update that adds the media folder, restart the app once.

### Picture questions: cantons

Quiz templates **«Kantone erkennen (Umrisse)»** (which canton has this shape?) and **«Kantone auf der Karte»**
(which canton is marked?) – outlines from the FSO / swisstopo generalised boundaries – and **«Kantonswappen
erkennen»** (simplified vector drawings of the coats of arms, drawn for Family Quest – `tools/build_arms.py`).
Flags in the flag quizzes are shown as sharp SVG pictures (country-flag-icons, MIT) instead of emoji.

### Estimation and map questions

- **Estimate:** everybody sets a number with a slider or types it (between minimum and maximum, with a unit) –
  e.g. «How high is the Matterhorn?». The closest answer gets 1000 points, the second 500, the third 250.
- **Map:** everybody taps a pin on the map of Switzerland (cantons, lakes) or Europe (countries) – e.g. «Where is
  Berlin?». The distance is measured in km; the closest pin wins the same way. The solution shows all pins.
- Templates: **«Schätzfragen»**, **«Wo liegt das? (Schweiz)»** and **«Wo liegt das? (Europa)»**. In the quiz
  editor every question has a type: multiple choice, estimate a number or place on a map (tap the right place).

### Template collections by region

The templates can be filtered with **Show:** – general, Switzerland, Germany, Austria, the Netherlands (the choice is
remembered on the device). New: *Deutschland: Bundesländer*, *Deutschland allgemein*, *Österreich: Bundesländer*,
*Niederlande: Provinzen*, *Niederlande allgemein*.

## My card box (own flash cards)

Everybody (children and parents) keeps **own decks** – e.g. «French words». On the start page **📇 My card box**
shows how many cards are due.

- **Own cards:** «+ New card» with front and back; «Save and next» for typing many words in a row.
- **From the packs with one click:** in a lesson, after answering, **📇 To my card box** puts the word (or the
  pairs of that task) into the deck of its subject – the deck is made automatically (e.g. «French», «Geography»,
  «General knowledge»). In a pack, **📇** next to a unit adds all its cards. Cards already in the deck are skipped.
- **Repeating:** the Leitner boxes as in the packs – known → one box up, not known → box 1, «almost» → tomorrow
  again. «Repeat» takes the due cards and up to 15 new ones, «Practise all» every card in random order; ⇄ swaps the
  sides (e.g. French → German).
- **What sits and what not:** every card shows its status – ✅ known (box 3 and up), 📈 learning, 🔁 due (should be
  known by now), 🌱 new; the bar and the filter chips show the counts.

Repeating the own cards gives no points (own cards could be made very easy).

## Language courses and general knowledge

Learning app › **Language courses & more**: everybody (children and adults) chooses a language and a level and
starts it – German (for English speakers), French, English and Spanish (for German speakers), each in three levels
A1 Beginner, A2 Basics, B1 Advanced, plus **General knowledge** (inventions, buildings, history, science, space, art,
sport …). The units of a course unlock one after the other; the exercises mix choice, typing, pairs, listening, gap
sentences and flash cards. Courses are not switched on automatically (`standard: false`, `selbst: true` in the pack).
