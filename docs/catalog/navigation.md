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

## Cross all of Victory Road

`navigation-victory-road`

Controls: assisted-gameplay-v1. Estimated difficulty: hard. Scored by milestones, see [milestone tasks](README.md#milestone-tasks).

### What this tests

Push boulders onto switches on three floors, including a boulder dropped through a 3F hole, and keep the route when floors reset.

### Agent instruction

Cross Victory Road and leave by its far exit onto Route 23, toward Indigo Plateau. Normal backtracking and room resets are allowed. Trainers on this route are already defeated and wild encounters are disabled.

### Starting situation

Victory Road 1F, first controllable tile after entering from Route 23. Every boulder switch on all three floors is unsolved.

### Setup

- Party: Nidoking level 50 with Strength, Surf, Double Kick and Horn Attack. Full HP, no status and full PP. Empty bag. No Escape Rope, Dig or Fly.
- All eight badges owned. Every boulder switch on 1F, 2F and 3F is unsolved. All Victory Road trainers already defeated.
- A documented emulator ROM override disables random wild encounters for the entire trial.

### Scored milestones

1. Reach 2F.
2. Reach 3F.
3. Put a boulder on the 3F switch, which opens the way to the south room.
4. Push a boulder into the 3F hole so it lands on 2F.
5. Put the dropped boulder on the second 2F switch, which opens the ladder to the east side.
6. Leave by the 2F exit onto Route 23 toward Indigo Plateau.

## Reach Articuno in Seafoam Islands

`navigation-seafoam-islands`

Controls: assisted-gameplay-v1. Estimated difficulty: hard. Scored by milestones, see [milestone tasks](README.md#milestone-tasks).

### What this tests

Find a four-floor ladder route, push two B3F boulders into its holes to slow the B4F current, then surf from the one tile the current blocked.

### Agent instruction

Find Articuno on Seafoam Islands B4F, the lowest floor, and stand on a tile next to it. You do not need to battle or catch it. Normal backtracking and room resets are allowed. Wild encounters are disabled.

### Starting situation

Seafoam Islands 1F, first controllable tile after entering from the west side of Route 20. No boulder has been pushed into any hole on any floor.

### Setup

- Party: Nidoking level 50 with Strength, Surf, Double Kick and Horn Attack. Full HP, no status and full PP. Empty bag. No Escape Rope, Dig or Fly.
- All eight badges owned. Both currents run. Articuno has not been met. Route 20 trainers are already defeated.
- A documented emulator ROM override disables random wild encounters for the entire trial.

### Scored milestones

1. Reach B1F.
2. Reach B2F.
3. Reach B3F.
4. Push a boulder into the west B3F hole.
5. Push a boulder into the east B3F hole, which slows the B4F current.
6. Stand next to Articuno on B4F.

Only the two B3F holes gate Articuno. The boulder puzzles on the upper floors are optional, so they earn no milestone. The B3F milestones count in order, so a run that fills the east hole first earns that point only after it also fills the west hole.

## Reach Giovanni in Silph Co.

`navigation-silph-co`

Controls: assisted-gameplay-v1. Estimated difficulty: hard. Scored by milestones, see [milestone tasks](README.md#milestone-tasks).

### What this tests

Find the Card Key on a 5F corridor whose ends are blocked by beaten trainers, then follow the warp pads through a locked 3F room and 7F to the sealed west hall of 11F and open the door into Giovanni's room.

### Agent instruction

Find Giovanni in Silph Co. and step into the room on 11F, the top floor, where he waits. You do not need to battle him. Normal backtracking is allowed. Wild encounters are disabled.

### Starting situation

Silph Co. 1F, just inside the front door. Every Card Key door is locked, the Card Key has not been picked up and Giovanni has not been beaten.

### Setup

- Party: Nidoking level 50 with Strength, Surf, Double Kick and Horn Attack. Full HP, no status and full PP. Empty bag. No Escape Rope, Dig or Fly.
- All eight badges owned. The rival on 7F has already been beaten and has left. Every Silph Co. trainer is already defeated.
- A documented emulator ROM override disables random wild encounters for the entire trial.

### Scored milestones

1. Reach the 5F bottom corridor where the Card Key lies.
2. Pick up the Card Key.
3. Open a locked 3F door into the room with the pad to 7F.
4. Reach the sealed west hall of 11F through the 7F pad.
5. Open the 11F door and step into Giovanni's room.

Beaten trainers stand at both ends of the 5F corridor that holds the Card Key. The only way in is the 5F pad at (9, 15): ride it to 9F and back, then step off it downward. The text map shows warp pads as exits with no destination, as the screen does, and Card Key doors as `D`.

## Travel from Pewter City to Lavender Town

`navigation-pewter-to-lavender`

Controls: assisted-gameplay-v1. Estimated difficulty: hard. Scored by milestones, see [milestone tasks](README.md#milestone-tasks).

### What this tests

Cross Mt. Moon through its basement, taking a fossil to open the way north on B2F, use Cut on the small trees in Cerulean City and on Route 9, then use Flash in the dark Rock Tunnel and follow its ladders to Route 10 and Lavender Town.

### Agent instruction

Travel from Pewter City to Lavender Town. Normal backtracking is allowed. Wild encounters are disabled.

### Starting situation

Pewter City Pokemon Center, just inside the door, early in the story. Lavender Town has not been visited and Snorlax still blocks Route 12.

### Setup

- Party: Charmeleon level 28 with Cut, Scratch, Ember and Leer, and Pikachu level 25 with Flash, Thundershock, Quick Attack and Thunder Wave. Full HP, no status and full PP. Empty bag. No Escape Rope, Fly, Dig or Teleport.
- Boulder and Cascade badges owned, so Flash and Cut work outside battle. The Saffron City gates are shut and Snorlax blocks Route 12, so Rock Tunnel is the only way in. No S.S. Ticket, so a guard still blocks the robbed house in Cerulean City.
- Every trainer on Route 3, Mt. Moon, Route 4, Route 9, Route 10 and Rock Tunnel is already defeated. Trainers off that route still battle. A documented emulator ROM override disables random wild encounters.

### Scored milestones

1. Reach Mt. Moon B2F.
2. Leave Mt. Moon onto Route 4 east of the mountain.
3. Cut the small tree at the west end of Route 9 and walk past it.
4. Reach Rock Tunnel B1F.
5. Leave Rock Tunnel onto Route 10 south of the tunnel.
6. Reach Lavender Town.

On Mt. Moon B2F the two fossils fill the only gap north, and taking one makes the Super Nerd take the other. Cut clears the small trees in Cerulean City at (19, 28) and on Route 9 at (5, 8). The text map shows them as `T`. Rock Tunnel shows no terrain until Flash, as the screen shows none.
