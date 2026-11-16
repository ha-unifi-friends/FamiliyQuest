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
| `anthropic_api_key` | Optional. Enables *photo or PDF → draft pack* in the import. The file is sent to the Claude API; the result is always a draft. |
| `anthropic_model` | Model for that import (default `claude-opus-5-5`). |
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

### Internet budget and block times

In the profile of a child (parent area › ✏️ › Internet minutes) **Internet budget and block times**:

- **Default budget:** minutes per day or per week and when it starts again (time; for a week also the weekday).
- **Other budget on these days:** e.g. 120 minutes on Saturday and Sunday (empty = default budget).
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

## Community: family quiz and family council

- **Family quiz** (learning app › Family › Quizzes, or parent area › Community): everybody – children too – makes
  quizzes (2–4 answers, one right, time per question) or copies a template (Swiss waters, geography of Europe,
  capitals of Europe and the world, flags, food of the world, Swiss specialities, cantons, animals, space,
  inventions, Switzerland). Whoever starts a game leads it (a parent may always step in); everybody joins on their
  own device. Quick right answers give more points (1000 down to 500). Places go into everybody's history; the
  reward events *Played the family quiz* and *Won the family quiz* can give coins (Rewards › Rules).
- **Bingo** (learning app › Family, or parent area › Community): whoever starts sets the rules (speed, one line /
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

Family › **🎵 Guess the song** (or parent area › Community): the game leader chooses a **speaker** of Home Assistant
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

### Games per game and person

Settings › **Games**: every game on its own – *for everybody*, *only chosen children* (tick the children) or *off*:
family quiz, bingo, Tschau Sepp, Kartenkarussell, Domino, Texas Hold'em and each game of the game corner. Parents can always
play; the family council and polls stay open for everybody. Switched-off games disappear from the children's app.

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

### Game corner

Family → **🕹️ Game corner**: small games that run on the device itself (only a duel on two devices goes over
the server; best times stay in this browser), shown when family games are on for the child:

- **Tic-Tac-Toe** – against the app (easy, medium, unbeatable), two players on one device, or on **two devices**:
  invite somebody of the family – the invitation pops up in their app; a tally of the rounds.
- **Sudoku** – 4×4 for beginners, 6×6, 9×9 easy / medium / hard; every puzzle has exactly one solution, wrong
  numbers turn red, best time per level.
- **Patience** – the classic solitaire: sort all cards by suit onto four piles, draw 1 or 3, undo, «Finish» when
  only open cards are left. Tap a card and it moves where it fits.
- **Ping-Pong** – against the app (easy, medium, hard) or face to face on one tablet; first to 7 points.
- **Pairs** – turn over two cards and find the pairs: animals, fruit, vehicles, sea animals or **your own photo
  sets**; alone (fewest moves), against the app (it remembers more or less well) or 2–4 players on one device.
  Card back: four patterns or the **family crest**.

**Photo sets and family crest** (parent area › Settings › Pairs game): upload photos into named sets (every photo
becomes a pair; a set needs at least 3 photos), and design the family crest – name, an emoji, two colours and a
pattern (plain, split, quartered, diagonal band, chevron). Photos no set uses any more are deleted when you save.

### Guests

Whoever leads a family quiz or a bingo game can tap **👥 Invite guests**: a QR code appears. Friends or
grandparents scan it with their phone in the home network (direct access must be on), type a name and play along
– nothing else of the app is open to them. Guests are deleted with everything they did after 12 hours. Parents can
switch guests off under Settings → Games.

**Guest networks** (Settings → Access from the network): devices in these address ranges – e.g. your guest
Wi-Fi – can only open the guest page and play with an invitation; no family login, no app, no parent area.

### Picture questions: cantons

Quiz templates **«Kantone erkennen (Umrisse)»** (which canton has this shape?) and **«Kantone auf der Karte»**
(which canton is marked?) – outlines from the FSO / swisstopo generalised boundaries – and **«Kantonswappen
erkennen»** (simplified pixel symbols of the coats of arms, ch-canton-symbols by NZZ, CC BY-SA 4.0).

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
