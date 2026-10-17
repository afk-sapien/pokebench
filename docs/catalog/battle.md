# Gen 1 Red battle strategy

Revision 3 assigns each task a primary skill. Counts reflect useful scenarios rather than a ten-task quota. These are proposed specifications with save validation and calibration pending.

## Route 1 Rattata battle

`battle-wild-basics`

**Agent goal:** Defeat the wild level 3 Rattata on Route 1 without fleeing or catching it.

**Start:** Battle menu: wild Route 1 Rattata level 3 at full HP.

**Concrete setup**

- Battle menu: wild Route 1 Rattata level 3 at full HP.
- Party: Squirtle level 5 with Tackle and Tail Whip, at full HP.
- Bag: Potion x1.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement. The task rule forbids RUN and throwing Poké Balls.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Confirm the private checkpoint has a native Route 1 level 3 Rattata and only timing changes across variants.

## Brock with Squirtle and Pidgey

`battle-prepared-gym`

**Agent goal:** Defeat Gym Leader Brock and earn the Boulder Badge with Squirtle level 15 and Pidgey level 12.

**Start:** Pewter Gym battle menu: Brock leads Geodude level 12, then Onix level 14.

**Concrete setup**

- Pewter Gym battle menu: Brock leads Geodude level 12, then Onix level 14.
- Party: Squirtle level 15 with Bubble, Tackle, Tail Whip, and Water Gun, plus Pidgey level 12 with Gust, Sand-Attack, and Quick Attack.
- Both party members start at full HP with no status. Bag: Potion x2.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Verify this proposed team against the private Brock fixture and the exact battle-menu state.

## Lorelei recovery with registered bad-matchup team

`battle-unfavorable-lead`

**Agent goal:** Defeat Elite Four member Lorelei without any supplied Pokémon fainting.

**Start:** Lorelei battle menu: Dewgong level 54 is active against Graveler level 45.

**Concrete setup**

- Lorelei battle menu: Dewgong level 54 is active against Graveler level 45.
- Party: Graveler level 45 with Earthquake, Rock Slide, Defense Curl, and Self-Destruct, Poliwrath level 50 with Hypnosis, Amnesia, Surf, and Rest, Haunter level 45 with Hypnosis, Dream Eater, Night Shade, and Confuse Ray.
- All three party members begin healthy. Bag: Elixer x1.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Confirm move labels from registered private move IDs and verify all timing variants.

## Lorelei adaptation after a missed Hypnosis

`battle-ineffective-attack-adaptation`

**Agent goal:** Defeat Elite Four member Lorelei after Poliwrath misses Hypnosis against Dewgong.

**Start:** Lorelei battle menu: Dewgong level 54 is active after Poliwrath has missed Hypnosis.

**Concrete setup**

- Lorelei battle menu: Dewgong level 54 is active.
- Party: Poliwrath level 50 with Hypnosis, Amnesia, Surf, and Rest. Pikachu level 45 with ThunderShock, Thunder Wave, Quick Attack, and Agility. Haunter level 45 with Hypnosis, Dream Eater, Night Shade, and Confuse Ray.
- Poliwrath is the lead. The fixture records that Poliwrath used Hypnosis and it missed before this live battle menu. Bag: Elixer x1.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Build and validate the proposed authentic post-miss checkpoint without opponent or RNG editing.

## Bruno Machamp resource tradeoff

`battle-heal-switch-attack-tradeoff`

**Agent goal:** Defeat Elite Four member Bruno from the Machamp battle menu.

**Start:** Bruno battle menu: Machamp level 58 is active.

**Concrete setup**

- Bruno battle menu: Machamp level 58 is active.
- Party: Kadabra level 50 with Psychic, Recover, Disable, and Kinesis, Poliwrath level 50 with Surf, Hypnosis, Amnesia, and Rest, Pidgeot level 50 with Wing Attack, Fly, Quick Attack, and Sand-Attack.
- Kadabra starts at 35 percent HP, Poliwrath and Pidgeot start healthy. Bag: Hyper Potion x1 and Super Potion x1.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Validate legal move sets, HP values, and a fixture whose outcome distinguishes the choices.

## Lorelei tactical v2 Poliwrath team

`battle-underleveled-status-setup`

**Agent goal:** Defeat Elite Four member Lorelei using tactical team version 2.

**Start:** Lorelei battle menu: Dewgong level 54 is active.

**Concrete setup**

- Lorelei battle menu: Dewgong level 54 is active.
- Tactical team version 2: Poliwrath level 50 with Hypnosis, Amnesia, Surf, and Rest. Pikachu level 45 with ThunderShock, Thunder Wave, Quick Attack, and Agility. Haunter level 45 with Hypnosis, Dream Eater, Night Shade, and Confuse Ray.
- All party members are healthy. Bag: Elixer x1 and no healing or revival items.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Validate tactical team version 2 at the private Lorelei battle menu.

## Champion preserve Jolteon

`battle-preserve-specialist`

**Agent goal:** Defeat Champion Blue while Jolteon remains unfainted.

**Start:** Champion battle menu: Blue leads Pidgeot level 61.

**Concrete setup**

- Champion battle menu: Blue leads Pidgeot level 61.
- Blue party A: Pidgeot level 61, Alakazam level 59, Rhydon level 61, Arcanine level 61, Exeggutor level 63, Blastoise level 65.
- Party: Jolteon level 55 with Thunderbolt, Thunder Wave, Double Kick, and Pin Missile. Lapras level 55 with Surf, Ice Beam, Confuse Ray, and Body Slam. Snorlax level 55 with Body Slam, Earthquake, Rest, and Amnesia.
- All party members are healthy. Bag: Hyper Potion x2 and Full Restore x1. Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Implement private tracking that records whether Jolteon faints during the attempt.

## Agatha Gengar recovery

`battle-losing-midbattle-recovery`

**Agent goal:** Defeat Elite Four member Agatha from a damaged lead state.

**Start:** Agatha battle menu: Gengar level 56 is active.

**Concrete setup**

- Agatha battle menu: Gengar level 56 is active.
- Party: Jynx level 55 with Psychic, Ice Beam, Lovely Kiss, and Rest, Alakazam level 55 with Psychic, Recover, Thunder Wave, and Reflect, Rhydon level 55 with Earthquake, Rock Slide, Body Slam, and Substitute.
- Jynx is the lead at 30 percent HP. Alakazam and Rhydon are healthy. Bag: Hyper Potion x1 and Full Restore x1.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Validate the proposed active HP and whether the encounter produces a real recovery tradeoff.

## Lorelei and Bruno PP gauntlet

`battle-restricted-pp`

**Agent goal:** Defeat Lorelei and then Bruno without blacking out.

**Start:** Lorelei battle menu: Dewgong level 54 is active. Bruno follows immediately after Lorelei.

**Concrete setup**

- Lorelei battle menu: Dewgong level 54 is active. Bruno follows immediately after Lorelei.
- Party: Poliwrath level 50 with Hypnosis, Amnesia, Surf, and Rest. Kadabra level 50 with Psychic, Recover, Reflect, and Kinesis.
- Poliwrath begins with Surf PP 4. Kadabra begins with Psychic PP 5. Bag: Elixer x1.
- Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement between both battles.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Confirm the private pp-gauntlet party labels and the inter-battle transition.

## Champion Blue starter-dependent lineup

`battle-uncertain-opponent-lineup`

**Agent goal:** Defeat Champion Blue from a fixed authentic starter-dependent Champion lineup.

**Start:** Champion battle menu: Blue leads Pidgeot level 61 from a fixed authentic starter-dependent party.

**Concrete setup**

- Champion battle menu: Blue leads Pidgeot level 61.
- Blue party A: Pidgeot level 61, Alakazam level 59, Rhydon level 61, Arcanine level 61, Exeggutor level 63, Blastoise level 65.
- Blue party B: Pidgeot level 61, Alakazam level 59, Rhydon level 61, Gyarados level 61, Arcanine level 63, Venusaur level 65.
- Blue party C: Pidgeot level 61, Alakazam level 59, Rhydon level 61, Exeggutor level 61, Gyarados level 63, Charizard level 65.
- Party: Jolteon level 55 with Thunderbolt, Thunder Wave, Double Kick, and Pin Missile. Lapras level 55 with Surf, Ice Beam, Confuse Ray, and Body Slam. Snorlax level 55 with Body Slam, Earthquake, Rest, and Amnesia.
- Bag: Hyper Potion x2 and Full Restore x1. Each native Blue party is assigned equal weight. Allowed decisions: FIGHT, PKMN, BAG, and dialogue advancement.

**Success**

- Defeat the named initial opponent or complete the named gauntlet.
- Finish with at least one usable party Pokémon and no blackout.

**Remaining work**

- Create the stated authentic private checkpoint and validate every listed fact.
- Calibrate the evaluator and token limit without model runs in this specification.

**Still to verify**

- Validate all three native Blue party branches from authentic Red saves.

## Become Champion with Snorlax, Graveler, Charizard, Vileplume, Parasect, and Weezing

`battle-league-balanced`

**Agent goal:** From Indigo Plateau before Lorelei, defeat Lorelei, Bruno, Agatha, Lance, and the Champion, then complete Hall of Fame registration using the supplied party and bag. Do not nickname Pokemon.

**Start:** Indigo Plateau overworld at the League entrance before Lorelei. All eight badges are owned, no Elite Four member or Champion has been defeated, and Hall of Fame entries are 0. The healthy full-PP party is Snorlax level 58, Graveler level 53, Charizard level 55, Vileplume level 31, Parasect level 30, and Weezing level 41. The bag contains Full Restore x5, Revive x5, Max Potion x1, and Elixer x1.

**Concrete setup**

- Snorlax knows Double Edge, Hyper Beam, Rest, Surf. Graveler knows Earthquake, Explosion, Rock Throw, Selfdestruct.
- Charizard knows Cut, Slash, Strength, Flamethrower. Vileplume knows Absorb, Poisonpowder, Stun Spore, Sleep Powder.
- Parasect knows Scratch, Stun Spore, Leech Life, Spore. Weezing knows Tackle, Smog, Sludge, Smokescreen.
- This is an isolated battle gauntlet with a supplied team, not a second full-game campaign. Its results are separate from campaign milestones.

**Success**

- Lorelei, Bruno, Agatha, Lance, and the Champion are defeated.
- Hall of Fame registration completes in the Hall of Fame room.

**Remaining work**

- Reuse the League task only after its fixture start check and Hall of Fame completion evidence are replay-validated.
- Confirm the registered party and supplies for every selected variant.
- Record Elite Four victories and Champion battle entry as partial milestones.

**Still to verify**

- Confirm the archived League source still produces the documented party, moves, PP, and bag after its settle frames.

## Become Champion with Pidgeot, Charizard, Lapras, Vileplume, Raticate, and Beedrill

`battle-league-constrained`

**Agent goal:** From Indigo Plateau before Lorelei, defeat Lorelei, Bruno, Agatha, Lance, and the Champion, then complete Hall of Fame registration using the supplied difficult team. Do not nickname Pokemon.

**Start:** Indigo Plateau overworld at the League entrance before Lorelei. All eight badges are owned, no Elite Four member or Champion has been defeated, and Hall of Fame entries are 0. The healthy full-PP party is Pidgeot level 50, Charizard level 61, Lapras level 58, Vileplume level 44, Raticate level 33, and Beedrill level 38. The bag contains Revive x5, Elixer x1, and no HP-restoring Potions.

**Concrete setup**

- This is the documented natural archived difficult League team.
- All party members start healthy with full PP.
- The required end state is the same first Hall of Fame registration used by the existing Champion predicate.
- This is an isolated battle gauntlet with a supplied team, not a second full-game campaign. Its results are separate from campaign milestones.

**Success**

- Lorelei, Bruno, Agatha, Lance, and the Champion are defeated.
- Hall of Fame registration completes in the Hall of Fame room.

**Remaining work**

- Reuse the difficult League task only after fixture start and completion evidence are replay-validated.
- Document the fixed team and resources in the private fixture manifest.
- Record Elite Four victories and Champion battle entry as partial milestones.

**Still to verify**

- Confirm the archived difficult-team source preserves the documented team, full PP, and exactly five Revives plus one Elixer.

