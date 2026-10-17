# Gen 1 Red navigation

Current catalog v0.52. Difficulty labels are estimates pending model calibration.

## Cross Viridian Forest and reach Pewter City

`navigation-forest-crossing`

Controls: assisted-gameplay-v1. Estimated difficulty: medium.

### What this tests

Follow a branching outdoor route to its exit while handling incidental encounters. No quest item or NPC sequence is required.

### Agent instruction

Reach Pewter City without blacking out.

### Starting situation

Viridian Forest, first controllable tile after entering through the southern gate.

### Setup

- Party: Squirtle level 10 with Tackle, Tail Whip and Bubble. Full HP, no status and full PP. No other Pokemon.
- Bag: 5 Potions, 2 Antidotes and 10 Poke Balls. Money: 300. No bicycle or field moves.
- Forest trainers have not been defeated. Wild encounters are enabled.

### Success

- Reach Pewter City outside battle without a blackout.

## Traverse Mt. Moon and reach Cerulean City

`navigation-branching-cave`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Navigate a multi-floor cave and distinguish exits from dead ends. Battles are incidental to reaching the destination.

### Agent instruction

Travel through Mt. Moon and reach Cerulean City without blacking out.

### Starting situation

Mt. Moon 1F, first controllable tile inside the Route 3 entrance.

### Setup

- Party: Wartortle level 20, Tackle, Tail Whip, Bubble and Water Gun. Full HP, no status and full PP.
- Bag: 10 Potions, 3 Antidotes and 1 Escape Rope. Money: 1000.
- Boulder Badge owned. Mt. Moon trainers and fossil encounter uncleared. No Dig, Fly or bicycle. Either fossil may be selected.

### Success

- Reach Cerulean City outside battle without a blackout.

## Reach Sabrina's room through Saffron Gym

`navigation-warp-puzzle`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Understand connected warp rooms and reach a specific destination without starting a battle.

### Agent instruction

Reach the tile directly south of Sabrina in Saffron Gym. Do not start her battle.

### Starting situation

Saffron Gym, first controllable entrance tile from Saffron City.

### Setup

- Party: Nidoking level 50 with Strength, Surf, Double Kick and Horn Attack. Full HP, no status and full PP. Bag: 20 Max Repels. No Escape Rope, Dig or Fly.
- Silph Co. rescued. Gym accessible. All seven ordinary gym trainers defeated, Sabrina unbeaten.
- The target tile is (9,9) in the upstream Saffron Gym coordinate system, below Sabrina at (9,8). Check the runtime coordinate convention before binding the grader.

### Success

- Stand on the walkable tile immediately south of Sabrina without starting a battle.

## Collect the Moon Stone in Rocket Hideout B2F

`navigation-spinning-floors`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Predict forced movement on spin tiles. The Moon Stone is a concrete marker that the puzzle was solved.

### Agent instruction

Collect the Moon Stone on Rocket Hideout B2F. You may backtrack, but do not use a saved-state reset.

### Starting situation

Rocket Hideout B2F, arrival tile from the B1F stairs at the northeast entrance.

### Setup

- Party: Nidoking level 50 with Strength, Surf, Double Kick and Horn Attack. Full HP, no status and full PP. Bag: 20 Max Repels. No Escape Rope, Dig or Fly.
- The B2F Rocket trainer is already defeated. Moon Stone uncollected and absent from the bag.
- Target is the native B2F Moon Stone at (1,11). No item relocation or custom floor layout.

### Success

- Acquire the Moon Stone that starts on B2F during this attempt.

## Solve Victory Road 1F and climb to 2F

`navigation-boulder-puzzle`

Controls: assisted-gameplay-v1. Estimated difficulty: stretch.

### What this tests

Push a boulder onto a switch without blocking the route, then reach the unlocked ladder.

### Agent instruction

Use the boulder puzzle to reach Victory Road 2F. Normal backtracking and room resets are allowed.

### Starting situation

Victory Road 1F, first controllable tile after entering from Route 23.

### Setup

- Party: Nidoking level 50 with Strength, Surf, Double Kick and Horn Attack. Full HP, no status and full PP. Bag: 20 Max Repels. No Escape Rope, Dig or Fly.
- All eight badges owned. The native 1F boulder puzzle is unsolved. 1F trainers already defeated.
- Target is the ladder at (1,1) on 1F. No pre-moved boulders or pre-activated switch.

### Success

- Reach Victory Road 2F through the ladder from 1F during this attempt.

## Reach Vermilion while the Saffron gate is closed

`navigation-blocked-route-alternative`

Controls: assisted-gameplay-v1. Estimated difficulty: hard.

### What this tests

Recognize a blocked route and use the available Underground Path instead of opening the guard gate.

### Agent instruction

Reach Vermilion City. The Saffron guards have not been given a drink. Find a legal route.

### Starting situation

Route 5, just outside the northern entrance of the Saffron gate building.

### Setup

- Party: Wartortle level 20 with Tackle, Tail Whip, Bubble and Water Gun, full HP and PP.
- Bag: 5 Super Potions and 2 Antidotes. No Fresh Water, Soda Pop, Lemonade, Fly or bicycle. Money: 0.
- Boulder and Cascade Badges owned. Route 6 trainers already defeated. Native Route 5 to Route 6 Underground Path available.

### Success

- Reach Vermilion City without a blackout or giving any Saffron guard a drink.
