# Gen 1 Red resource preparation

Revision 3 assigns each task a primary skill. Counts reflect useful scenarios rather than a ten-task quota. These are proposed specifications with save validation and calibration pending.

## Brock lead selection with Squirtle and Pidgey

`preparation-lead-selection`

**Agent goal:** Choose the lead for the Brock battle.

**Start:** Target fight: Brock, Geodude level 12 then Onix level 14.

**Concrete setup**

- Target fight: Brock, Geodude level 12 then Onix level 14.
- Roster: Squirtle level 15 with Bubble, Tackle, Tail Whip, and Water Gun. Pidgey level 12 with Gust, Sand-Attack, and Quick Attack.
- Bag: Potion x2. Cash: 0 Pokedollars. Allowed preparation: choose Squirtle or Pidgey as lead only.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Calibrate the automated controller threshold.

## Brock Pokémon Center recovery

`preparation-recovery-before-continuing`

**Agent goal:** Use the free Pokémon Center recovery before fighting Brock.

**Start:** Pewter City before Brock with a damaged party and the Pokémon Center available.

**Concrete setup**

- Target fight: Brock, Geodude level 12 then Onix level 14.
- Roster: Squirtle level 15 with Bubble, Tackle, Tail Whip, and Water Gun at half HP. Pidgey level 12 with Gust, Sand-Attack, and Quick Attack at half HP.
- Bag: Potion x1. Cash: 0 Pokedollars. Pokémon Center recovery is available.
- Allowed preparation: visit the Pokémon Center, use the listed Potion, choose lead, and reorder party.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Validate that the private start permits Center use before the Brock checkpoint.

## Lorelei roster assembly from storage

`preparation-assemble-storage-roster`

**Agent goal:** Assemble a party for Lorelei from the stated active party and PC box.

**Start:** Target fight: Lorelei, Dewgong level 54, Cloyster level 53, Slowbro level 54, Jynx level 56, Lapras level 56.

**Concrete setup**

- Target fight: Lorelei, Dewgong level 54, Cloyster level 53, Slowbro level 54, Jynx level 56, Lapras level 56.
- Active party: Charizard level 50 with Flamethrower, Slash, Fly, SmokeScreen, Pidgeot level 48 with Wing Attack, Fly, Quick Attack, Sand-Attack.
- PC box: Jolteon level 50 with Thunderbolt, Thunder Wave, Double Kick, Pin Missile, Jynx level 50 with Psychic, Ice Beam, Lovely Kiss, Rest, Snorlax level 50 with Body Slam, Rest, Amnesia, Earthquake, Lapras level 50 with Surf, Ice Beam, Confuse Ray, Body Slam.
- Bag: Hyper Potion x2. Cash: 0 Pokedollars. Allowed preparation: transfer and order up to six listed Pokémon.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Validate PC menu operations and automated controller handling of submitted order.

## Misty shopping with Pikachu and Bulbasaur

`preparation-shop-for-challenge`

**Agent goal:** Buy supplies for the Misty battle within the listed cash and stock.

**Start:** Target fight: Misty, Staryu level 18 then Starmie level 21.

**Concrete setup**

- Target fight: Misty, Staryu level 18 then Starmie level 21.
- Roster: Pikachu level 20 with ThunderShock, Quick Attack, Thunder Wave, Growl, Bulbasaur level 20 with Vine Whip, Tackle, Leech Seed, Growl.
- Cash: 900 Pokedollars. Mart stock: Potion 300 Pokedollars, Antidote 100 Pokedollars, Parlyz Heal 200 Pokedollars, Burn Heal 250 Pokedollars, Poké Ball 200 Pokedollars. Bag initially empty.
- Allowed preparation: buy listed stock in whole quantities, reorder the party, and set the lead.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Calibrate cash accounting, bag capacity, and controller threshold.

## Kadabra TM choice for Lorelei then Bruno

`preparation-move-replacement-across-fights`

**Agent goal:** Choose one Kadabra move replacement for consecutive Lorelei and Bruno fights.

**Start:** Target fights: Lorelei followed by Bruno.

**Concrete setup**

- Target fights: Lorelei followed by Bruno.
- Roster: Kadabra level 50 with Psychic, Recover, Reflect, and Kinesis. Poliwrath level 50 with Hypnosis, Amnesia, Surf, and Rest.
- Teaching options: TM06 Toxic or TM45 Thunder Wave, each usable once by Kadabra. Bag: Elixer x1. Cash: 0 Pokedollars.
- Allowed preparation: teach at most one listed TM to Kadabra, replace one listed Kadabra move if taught, choose lead, and reorder party.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Verify Gen 1 TM compatibility and the shared controller sequence.

## TM24 Thunderbolt allocation for Lorelei

`preparation-scarce-tm-allocation`

**Agent goal:** Choose a legal recipient for the only Thunderbolt TM.

**Start:** Target fight: Lorelei, Dewgong level 54, Cloyster level 53, Slowbro level 54, Jynx level 56, Lapras level 56.

**Concrete setup**

- Target fight: Lorelei, Dewgong level 54, Cloyster level 53, Slowbro level 54, Jynx level 56, Lapras level 56.
- Roster: Pikachu level 45 with ThunderShock, Thunder Wave, Quick Attack, Agility, Jolteon level 45 with Thundershock, Thunder Wave, Double Kick, Pin Missile, Lapras level 45 with Surf, Ice Beam, Confuse Ray, Body Slam.
- Bag: TM24 Thunderbolt x1 and Elixer x1. Cash: 0 Pokedollars. Allowed preparation: teach TM24 to Pikachu or Jolteon, replace one move on its recipient, choose lead, and reorder party.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Verify TM24 legality and fixture menu behavior.

## Lance damaged team rescue

`preparation-damaged-team-rescue`

**Agent goal:** Allocate scarce recovery supplies before Lance.

**Start:** Target fight: Lance, Gyarados level 58, Dragonair level 56, Dragonair level 56, Aerodactyl level 60, Dragonite level 62.

**Concrete setup**

- Target fight: Lance, Gyarados level 58, Dragonair level 56, Dragonair level 56, Aerodactyl level 60, Dragonite level 62.
- Roster: Jynx level 55 with Ice Beam, Psychic, Lovely Kiss, and Rest at 35 HP with Ice Beam PP 0, Snorlax level 40 with Body Slam, Amnesia, Rest, and Headbutt fainted, Jolteon level 55 with Thunderbolt, Thunder Wave, Pin Missile, and Agility fainted.
- Bag: Revive x1, Max Potion x2, Elixer x1. Cash: 0 Pokedollars. Allowed preparation: use listed bag items and reorder the party.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Confirm registered team-rescue move labels and exact item counts.

## Champion Blue lineup preparation

`preparation-uncertain-opponent`

**Agent goal:** Prepare for any of the three disclosed Champion Blue rosters before the variant is selected.

**Start:** Target fight: Champion Blue from one of three equally weighted native starter-dependent parties.

**Concrete setup**

- Target fight: Champion Blue from one of three equally weighted native starter-dependent parties.
- Party A: Pidgeot level 61, Alakazam level 59, Rhydon level 61, Arcanine level 61, Exeggutor level 63, Blastoise level 65. Party B: Pidgeot level 61, Alakazam level 59, Rhydon level 61, Gyarados level 61, Arcanine level 63, Venusaur level 65. Party C: Pidgeot level 61, Alakazam level 59, Rhydon level 61, Exeggutor level 61, Gyarados level 63, Charizard level 65.
- Roster: Jolteon level 55 with Thunderbolt, Thunder Wave, Double Kick, Pin Missile. Lapras level 55 with Surf, Ice Beam, Confuse Ray, Body Slam. Snorlax level 55 with Body Slam, Earthquake, Rest, Amnesia.
- Bag: Hyper Potion x2 and Full Restore x1. Cash: 0 Pokedollars. Allowed preparation: choose lead, order party, and allocate listed items.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Validate authentic saves for all three native Blue party branches and equal-weight scheduling.

## Lorelei and Bruno Elixer allocation

`preparation-pp-allocation-gauntlet`

**Agent goal:** Allocate one Elixer before the Lorelei to Bruno gauntlet.

**Start:** Target fights: Lorelei followed by Bruno.

**Concrete setup**

- Target fights: Lorelei followed by Bruno.
- Roster: Poliwrath level 50 with Hypnosis, Amnesia, Surf PP 4, and Rest. Kadabra level 50 with Psychic, Recover, Reflect, and Kinesis with Psychic PP 5.
- Bag: Elixer x1. Cash: 0 Pokedollars. Allowed preparation: choose the party member that receives Elixer, choose lead, and order party.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Define controller handling when a selected Elixer target has full PP.

## Elite Four resource preparation

`preparation-scarce-resource-league`

**Agent goal:** Prepare fixed resources for Lorelei, Bruno, Agatha, Lance, and Champion Blue.

**Start:** Target sequence: Lorelei, Bruno, Agatha, Lance, then Champion Blue.

**Concrete setup**

- Target sequence: Lorelei, Bruno, Agatha, Lance, then Champion Blue.
- Roster: Jolteon level 55 with Thunderbolt, Thunder Wave, Double Kick, Pin Missile, Lapras level 55 with Surf, Ice Beam, Confuse Ray, Body Slam, Snorlax level 55 with Body Slam, Earthquake, Rest, Amnesia.
- Cash: 3000 Pokedollars. Shop stock: Hyper Potion 1200 Pokedollars, Full Restore 3000 Pokedollars, Revive 1500 Pokedollars. Bag initially has Hyper Potion x1 and Elixer x1.
- Allowed preparation: buy listed items within cash, choose lead, order party, and allocate bag items.

**Success**

- Submit a legal frozen configuration using only the stated roster, moves, items, TMs, cash, and allowed decisions.
- The automated controller grades the frozen submission against the named target fight or sequence.

**Remaining work**

- Build a private preparation checkpoint with the stated facts and validate submission legality.
- Calibrate the automated controller and threshold before scoring any model.

**Still to verify**

- Validate shop access before the League and controller completion criterion.

