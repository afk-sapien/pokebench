# Gen 1 Red quests

Current catalog v0.52. Difficulty labels are estimates pending model calibration.

## Choose any starter in Oak's Lab

`objectives-starter-selection`

Controls: assisted-gameplay-v1. Estimated difficulty: easy.

### What this tests

Complete a basic NPC handover and choice. This is an easy baseline, not a strong-model discriminator.

### Agent instruction

Choose Bulbasaur, Charmander or Squirtle and complete the starter handover. Keep its default name.

### Starting situation

Oak's Lab, immediately after Oak's opening escort and explanation, before any starter ball has been selected.

### Setup

- Party empty, all three starter choices available, no ball selected yet.
- Money: 3000. Bag empty. This task does not require winning the rival battle.

### Success

- Acquire the first starter and reach the existing starter-completion predicate. Any of the three species counts.

## Collect Oak's Parcel in Viridian and return it

`objectives-parcel-roundtrip`

Controls: assisted-gameplay-v1. Estimated difficulty: medium.

### What this tests

Complete a pickup and delivery sequence. Travel is incidental and does not award a second navigation score.

### Agent instruction

Collect Oak's Parcel from Viridian Mart and deliver it to Professor Oak to receive the Pokedex. Keep default Pokemon names.

### Starting situation

Pallet Town, immediately outside Oak's Lab after the first rival battle and free recovery.

### Setup

- Party: Squirtle level 10 with Tackle, Tail Whip and Bubble. Full HP, no status and full PP. No other Pokemon.
- Bag: 5 Potions, no parcel or Pokedex. Money: 3000.
- No parcel-collection or delivery flags set. Starter and first rival sequence completed.

### Success

- Collect the parcel after the start, deliver it to Oak and receive the Pokedex outside battle.

## Help Bill and receive the S.S. Ticket

`objectives-npc-instruction`

Controls: assisted-gameplay-v1. Estimated difficulty: medium.

### What this tests

Follow an NPC instruction, operate the requested object, and return for the reward.

### Agent instruction

Speak to Bill, help him with his problem and collect his reward. Follow what he tells you.

### Starting situation

Bill's house on Route 25, entrance tile before speaking to transformed Bill.

### Setup

- Party: Wartortle level 20, Tackle, Tail Whip, Bubble and Water Gun, full HP and PP.
- Bag: 5 Potions. At least two free bag slots. Bill has not been helped and the S.S. Ticket is absent.
- The agent learns the requested PC interaction from the original in-game conversation. No rewritten NPC dialogue.

### Success

- Use the cell separator to restore Bill and receive the S.S. Ticket during the attempt.

## Rescue Mr. Fuji and obtain the Poke Flute

`objectives-prerequisite-chain`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Complete a rescue and reward sequence involving required encounters and NPC interactions.

### Agent instruction

Rescue Mr. Fuji and obtain the Poke Flute. Do not use the Poke Doll ghost bypass.

### Starting situation

Lavender Town, directly outside the Pokemon Tower entrance.

### Setup

- Party: Kadabra level 35 with Psybeam, Confusion, Recover and Disable. Wartortle level 35 with Water Gun, Bite, Bubble and Withdraw. Both fully healed with full PP.
- Bag: Silph Scope, 10 Super Potions, 3 Revives, 5 Antidotes. Money: 0. No Poke Doll.
- Tower rival already defeated. Ghost Marowak and 7F Rockets unbeaten. Mr. Fuji not rescued and Poke Flute absent.

### Success

- Complete the native Pokemon Tower rescue, then receive the Poke Flute from Mr. Fuji.

## Find and catch a wild Pikachu from Viridian City

`objectives-find-capture-species`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Locate a target species and manage a limited capture budget. Walking through the forest alone does not pass.

### Agent instruction

Catch a wild Pikachu and keep it in your party. You start in Viridian City with 10 Poke Balls. Do not buy more balls or use stored Pokemon. Keep default names.

### Starting situation

Viridian Pokemon Center, first controllable tile after a full party heal.

### Setup

- Party: Squirtle level 10 with Tackle, Tail Whip and Bubble. Full HP, no status and full PP. No other Pokemon.
- Bag: 5 Potions, 2 Antidotes and 10 Poke Balls. Money: 300. No bicycle or field moves.
- Pokedex owned and parcel delivered. Northern Viridian exit open. No Pikachu in party or storage.
- The intended native encounter source is Viridian Forest. Species and ball budget are fixed across timing variants, not randomly changed. Healing at a Center is allowed.

### Success

- Capture a wild Pikachu after the start and retain it in the party outside battle.
- No purchased balls, gifted Pikachu, trades or storage withdrawals count.

## Catch level 30 Snorlax with 12 Great Balls

`objectives-constrained-valuable-capture`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Capture an encounter without knocking it out, using HP control, status and limited balls. This quest overlaps battle tactics and is scored only here.

### Agent instruction

Catch this Snorlax using your supplied team and 12 Great Balls. You may lower its HP or apply status. Do not flee, knock it out or black out. Keep its default name.

### Starting situation

The healthy-capture checkpoint at the opening command menu against the natural level 30 Snorlax, initially at full HP with no status.

### Setup

- Party: Parasect level 30 with Spore, Scratch, Stun Spore and Leech Life. Haunter level 30 with Hypnosis, Night Shade, Confuse Ray and Lick.
- Bag: 12 Great Balls and one Poke Flute, matching the healthy-capture source contract. No extra balls or healing items.
- Both party members begin fully healed with full PP. Full health describes Snorlax at the start, not a restriction against damaging it.

### Success

- Capture the initial Snorlax and finish the encounter outside battle.

## Obtain a Bicycle through the Fan Club quest

`objectives-infeasible-plan-alternate`

Controls: assisted-gameplay-v1. Estimated difficulty: medium.

### What this tests

Follow the Fan Club reward and Bicycle exchange quest. This tests finding the required NPC reward, not earning money.

### Agent instruction

Obtain a Bicycle. You have 3000 money, no Bike Voucher and cannot afford the displayed purchase price. Find another legal way to obtain one.

### Starting situation

Cerulean Bike Shop, in front of the clerk before opening a conversation.

### Expected solution for reviewers

Visit the Pokemon Fan Club chairman in Vermilion, hear his story to receive the free Bike Voucher, then exchange it at the Cerulean Bike Shop. Grinding money cannot unlock the purchase.

### Setup

- Party: Wartortle level 20 with Tackle, Tail Whip, Bubble and Water Gun, full HP and PP.
- Bag: 5 Potions. Money: 3000. Bike Voucher and Bicycle absent. Fan Club chairman has not given the voucher.
- Boulder and Cascade Badges owned. Route 5 and Route 6 path available and trainers cleared. No Fly.

### Success

- Obtain the Bicycle during the attempt using a voucher acquired after the start.

## Clear Rocket Hideout and defeat Giovanni for the Silph Scope

`objectives-quest-trainer`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Complete the hideout entry, key, boss and reward prerequisites in order. Traversing the rooms alone does not pass.

### Agent instruction

From Celadon City, enter the Rocket Hideout beneath the Game Corner, obtain the Lift Key, defeat Giovanni on B4F, and pick up the Silph Scope. Keep default Pokemon names.

### Starting situation

Celadon City overworld outside the Game Corner. Red has Boulder, Cascade, and Thunder Badges, Charmeleon level 31 with Ember, Leer, Rage, and Scratch at full PP, Kadabra level 29 with Teleport, Confusion, Disable, and Psybeam at full PP, Gyarados level 28 with Tackle, Bite, Leer, and Dragon Rage at full PP, Super Potion x4, Antidote x2, Escape Rope x1, and 6200 Pokedollars. The Rocket Hideout is unopened, the Lift Key is absent, Giovanni on Rocket Hideout B4F is unbeaten, and the Silph Scope is absent.

### Setup

- The quest location is Celadon Game Corner and Rocket Hideout B1F through B4F.
- The required trainer is Giovanni on Rocket Hideout B4F, not Giovanni in Viridian Gym.
- Required quest sequence is reveal hideout, obtain Lift Key, defeat Giovanni, then collect Silph Scope.
- This focused checkpoint test fixes the starting resources. Campaign progress does not automatically count as a pass on this task.

### Success

- The Rocket Hideout is entered and the Lift Key is obtained.
- Giovanni on Rocket Hideout B4F is defeated after the Lift Key event.
- The Silph Scope is collected and the final state is outside battle.

## Catch Abra on Route 24, train it, then defeat Misty

`objectives-capture-prepare-battle`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Maintain an ordered capture, training and gym objective, retaining the same captured Pokemon throughout.

### Agent instruction

From Cerulean City, catch a wild Abra on Route 24, raise it by at least one level without releasing it, then defeat Misty in Cerulean Gym for the Cascade Badge. Keep default Pokemon names.

### Starting situation

Cerulean City overworld at the Route 24 entrance. Red has the Boulder Badge but not the Cascade Badge. The Nugget Bridge rival is already defeated, so Routes 24 and 25 are accessible. Party slot 1 Ivysaur level 20 has Tackle, Growl, Leech Seed, and Vine Whip at full PP, slot 2 Pidgeotto level 18 has Gust, Sand-Attack, and Quick Attack at full PP, slot 3 Pikachu level 18 has ThunderShock, Growl, Tail Whip, and Quick Attack at full PP, and slots 4 through 6 are empty. The bag contains Poke Ball x8, Potion x2, Antidote x1, and 2400 Pokedollars. No Abra is owned and Misty is unbeaten.

### Setup

- The capture target is a wild Abra on Route 24.
- The captured Abra must remain in the party or PC and gain at least one level before the Gym battle.
- The required trainer is Misty in Cerulean Gym, not the already defeated Nugget Bridge rival.
- This focused checkpoint test fixes the starting resources. Campaign progress does not automatically count as a pass on this task.

### Success

- A wild Abra is captured after the start.
- That Abra gains at least one level and remains owned.
- Misty is defeated after the capture and level-gain events, the Cascade Badge is awarded, and the final state is outside battle.
