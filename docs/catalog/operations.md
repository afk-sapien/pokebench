# Gen 1 Manual Menu Operations

Current catalog v0.52. Difficulty labels are estimates pending model calibration.

## Use one Potion on party slot 2 Pikachu

`operations-heal-potion-target`

Controls: manual-menu-v1. Estimated difficulty: easy.

### Agent instruction

Open the Bag and use exactly one Potion on Pikachu in party slot 2. Do not use any other item or change the party order.

### Starting situation

Route 1 overworld at the north grass edge. Party slot 1 Bulbasaur is 29/29 HP and healthy, slot 2 Pikachu is 12/35 HP and healthy, and slot 3 Pidgey is 23/23 HP and healthy. The bag contains Potion x1, Antidote x1, and Poke Ball x3.

### Setup

- Target is party slot 2 Pikachu at 12/35 HP.
- Potion x1 is the only HP-restoring item in the bag.
- The required final party order is Bulbasaur, Pikachu, Pidgey.

### Success

- Potion count changes from 1 to 0.
- Pikachu gains exactly 20 HP, ending at 32/35 HP.
- Bulbasaur and Pidgey retain stated HP, healthy status, moves, PP, and slots.
- The final screen is Route 1 overworld or the pause menu.

## Use one Antidote on party slot 3 Nidoran♂

`operations-cure-poison`

Controls: manual-menu-v1. Estimated difficulty: easy.

### Agent instruction

Open the Bag and use exactly one Antidote on the poisoned Nidoran♂ in party slot 3. Do not use any other item.

### Starting situation

Viridian City overworld outside the Pokemon Center. Party slot 1 Bulbasaur is 29/29 HP and healthy, slot 2 Pidgey is 23/23 HP and healthy, and slot 3 Nidoran♂ is 18/28 HP and poisoned. The bag contains Antidote x1, Potion x2, and Poke Ball x4.

### Setup

- Target is party slot 3 Nidoran♂, poisoned at 18/28 HP.
- Antidote x1 is the only status-curing item in the bag.
- Poison removal must not heal HP in Generation 1.

### Success

- Antidote count changes from 1 to 0.
- Nidoran♂ ends healthy at exactly 18/28 HP.
- Bulbasaur and Pidgey retain stated HP, status, moves, PP, and slots.
- The final screen is Viridian City overworld or the pause menu.

## Use one Ether on Squirtle Water Gun

`operations-restore-move-pp`

Controls: manual-menu-v1. Estimated difficulty: medium.

### Agent instruction

Open the Bag, use exactly one Ether on Squirtle in party slot 1, then select Water Gun. Do not restore Bubble PP.

### Starting situation

Route 24 overworld. Party slot 1 Squirtle level 15 is at full HP and healthy with Tackle 35/35 PP, Tail Whip 30/30 PP, Bubble 8/30 PP, and Water Gun 5/25 PP. Party slot 2 Pidgey is at full HP and healthy. The bag contains Ether x1, Potion x1, and Poke Ball x5.

### Setup

- Target is party slot 1 Squirtle, Water Gun in move slot 4 at 5/25 PP.
- Bubble in move slot 3 is deliberately also depleted at 8/30 PP.
- In Generation 1, Ether restores 10 PP to one selected move.

### Success

- Ether count changes from 1 to 0.
- Water Gun changes from 5/25 PP to 15/25 PP.
- Bubble remains 8/30 PP and Squirtle’s other move PP is unchanged.
- All party HP, status, moves, and order remain unchanged.

## Switch from Charmander to party slot 3 Pikachu

`operations-battle-switch`

Controls: manual-menu-v1. Estimated difficulty: medium.

### Agent instruction

At the trainer battle command menu, choose PKMN and switch from Charmander to Pikachu in party slot 3. Do not select FIGHT, ITEM, or RUN.

### Starting situation

Viridian Forest at the live second Bug Catcher trainer battle command menu. The opponent has native Weedle level 7, Kakuna level 7, and Weedle level 7. Party slot 1 Charmander is active at 30/39 HP and healthy, slot 2 Pidgey is 23/23 HP and healthy, and slot 3 Pikachu is 35/35 HP and healthy. No player command has been selected.

### Setup

- Requested switch is Charmander in slot 1 to Pikachu in slot 3.
- Pidgey in slot 2 is a legal but incorrect bench choice.
- Opponent damage after the requested switch is allowed.

### Success

- The player command ledger records PKMN followed by Pikachu slot 3.
- Pikachu becomes active before any player move, item, run attempt, or second switch.
- No player command other than the requested switch occurs before Pikachu is active.

## Move party slot 3 Pidgey to the lead

`operations-party-reorder`

Controls: manual-menu-v1. Estimated difficulty: medium.

### Agent instruction

Use the party menu’s SWITCH command as many times as necessary to change the party order from Bulbasaur, Pikachu, Pidgey to Pidgey, Bulbasaur, Pikachu.

### Starting situation

Pewter City overworld outside the Pokemon Center. Party order is slot 1 Bulbasaur 29/29 HP healthy, slot 2 Pikachu 35/35 HP healthy, slot 3 Pidgey 23/23 HP healthy. The bag contains Potion x1 and Poke Ball x3.

### Setup

- Required final party order is Pidgey, Bulbasaur, Pikachu.
- In Generation 1, moving slot 3 to the lead requires two pairwise SWITCH operations for this requested final order.
- All three Pokemon have full PP and no status condition.
- No bag use, map movement, or battle is needed.

### Success

- Final party slots are Pidgey, Bulbasaur, Pikachu.
- HP, status, moves, PP, bag counts, and Pewter City location are unchanged.
- The final screen is Pewter City overworld or the pause menu.

## Buy exactly ten Poke Balls at Viridian Poke Mart

`operations-buy-pokeballs`

Controls: manual-menu-v1. Estimated difficulty: easy.

### Agent instruction

Enter the Viridian Poke Mart and buy exactly 10 Poke Balls. Spend all 2000 Pokedollars and buy nothing else. Finish outside the Mart in Viridian City.

### Starting situation

Viridian City overworld one tile south of the Poke Mart entrance. The bag contains Poke Ball x0, Potion x1, and Antidote x1. Cash is exactly 2000 Pokedollars. Party slot 1 Bulbasaur is 29/29 HP and healthy.

### Setup

- Poke Balls cost 200 Pokedollars each at Viridian Poke Mart.
- Cash 2000 permits exactly ten Poke Balls and no other purchase after that.
- The existing purchase objective accepts extra Balls and therefore is not used.

### Success

- Poke Ball count changes from 0 to exactly 10.
- Cash changes from 2000 to exactly 0.
- Potion and Antidote counts remain 1 each.
- The final screen is Viridian City overworld.

## Deposit and withdraw party slot 2 Pikachu

`operations-deposit-withdraw`

Controls: manual-menu-v1. Estimated difficulty: hard.

### Agent instruction

At the Viridian Pokemon Center PC, deposit Pikachu from party slot 2 into the active box, withdraw that same Pikachu after it appends to party slot 3, then use the party menu SWITCH command to restore the order Bulbasaur, Pikachu, Pidgey.

### Starting situation

Viridian Pokemon Center overworld at the PC. Party order is Bulbasaur 29/29 healthy, Pikachu 35/35 healthy, Pidgey 23/23 healthy. The active Pokemon Storage System box contains Rattata 18/18 healthy and has 19 free slots. The bag contains Potion x1.

### Setup

- The target is Pikachu, initially party slot 2.
- After depositing Pikachu, withdrawing it appends it after Pidgey in party slot 3.
- The required final party order is Bulbasaur, Pikachu, Pidgey, so the agent must SWITCH party slots 2 and 3 after withdrawal.
- The active box must retain Rattata unchanged.

### Success

- The operation ledger records deposit of Pikachu, withdrawal of the same Pokemon identity, then a party SWITCH of slots 2 and 3.
- Final party order is Bulbasaur, Pikachu, Pidgey.
- Rattata remains in the active box and all stated HP, status, moves, PP, and bag counts remain unchanged.

## Teach TM34 Bide to Pikachu over Growl

`operations-teach-tm-replace-move`

Controls: manual-menu-v1. Estimated difficulty: hard.

### Agent instruction

Use TM34 to teach Bide to Pikachu in party slot 2. When prompted, replace Growl in move slot 2.

### Starting situation

Celadon City overworld. Party slot 1 Bulbasaur is 29/29 HP healthy, slot 2 Pikachu is 35/35 HP healthy with ThunderShock, Growl, Tail Whip, and Thunder Wave at full PP, and slot 3 Pidgey is 23/23 HP healthy. The bag contains TM34 x1, Potion x1, and Poke Ball x3.

### Setup

- TM34 is Bide in Pokemon Red Generation 1.
- Pikachu is the recipient in party slot 2 and has four moves, so move replacement is prompted.
- The selected replacement is Growl in move slot 2.

### Success

- TM34 count changes from 1 to 0.
- Pikachu move slot 2 changes from Growl to Bide.
- ThunderShock, Tail Whip, and Quick Attack remain in their original slots with their original PP.
- All non-target party state and non-TM bag counts remain unchanged.

## Withdraw one Potion and use it on Pikachu

`operations-withdraw-item-and-use`

Controls: manual-menu-v1. Estimated difficulty: hard.

### Agent instruction

At the Viridian Pokemon Center item PC, withdraw one Potion, then use it from the Bag on Pikachu in party slot 2.

### Starting situation

Viridian Pokemon Center overworld at the PC. Party slot 1 Bulbasaur is 29/29 HP healthy, slot 2 Pikachu is 10/35 HP healthy, and slot 3 Pidgey is 23/23 HP healthy. The item PC contains Potion x1 and Antidote x1. The bag contains Potion x0, Antidote x1, and Poke Ball x3.

### Setup

- Pikachu in party slot 2 is the only damaged Pokemon.
- Exactly one Potion starts in the item PC and none starts in the bag.
- A Potion restores 20 HP, so Pikachu should finish at 30/35 HP.

### Success

- Item PC Potion count changes from 1 to 0.
- Bag Potion count returns to 0 after one withdrawal and one use.
- Pikachu changes from 10/35 HP to 30/35 HP.
- All Antidote and Poke Ball counts and all non-target party state remain unchanged.

## Complete an inventory and party checklist

`operations-menu-checklist`

Controls: manual-menu-v1. Estimated difficulty: stretch.

### What this tests

Carry out a short inventory operation sequence. The full-bag exchange is an alternative case in this same task family.

### Agent instruction

At the Viridian Pokemon Center, withdraw one Potion from the item PC, use it on Pikachu in party slot 2, then reorder the party to Pidgey, Bulbasaur, Pikachu.

### Starting situation

Viridian Pokemon Center overworld at the PC. Party order is Bulbasaur 29/29 healthy, Pikachu 10/35 healthy, Pidgey 23/23 healthy. The item PC contains Potion x1 and Antidote x1. The bag contains Potion x0, Antidote x1, and Poke Ball x3.

### Setup

- Required operation order is withdraw Potion, use Potion on Pikachu, then party reorder.
- Required final order is Pidgey, Bulbasaur, Pikachu.
- Pikachu should finish at 30/35 HP after the Generation 1 Potion effect.

### Success

- The ledger records the required three operations in order.
- Item PC Potion ends at 0 and bag Potion ends at 0.
- Pikachu ends at 30/35 HP.
- Final party order is Pidgey, Bulbasaur, Pikachu, with all other stated state unchanged.

## Free a bag slot and exchange the Bike Voucher

`objectives-recover-earlier-mistake`

Controls: manual-menu-v1. Estimated difficulty: easy.

Inventory variant of `operations-menu-checklist`. Shares its task weight.

### What this tests

Recognize an inventory-capacity error and resolve it through manual menus while retaining the required quest item.

### Agent instruction

Exchange your Bike Voucher for a Bicycle. Your bag is full. Keep the voucher until the exchange and make room by any legal method.

### Starting situation

Cerulean Bike Shop, in front of the clerk with a Bike Voucher and all 20 bag slots occupied.

### Expected solution for reviewers

Discard, use or deposit a nonessential item to free one slot, then talk to the shopkeeper to exchange the already-owned voucher. No money or new voucher is needed.

### Setup

- Party: Wartortle level 20 with Tackle, Tail Whip, Bubble and Water Gun, full HP and PP. Money: 0.
- Exactly one of each occupies the 20 bag slots: Bike Voucher, Potion, Antidote, Awakening, Burn Heal, Ice Heal, Parlyz Heal, Escape Rope, Repel, Super Potion, Poke Ball, Great Ball, Ultra Ball, X Attack, X Defend, X Speed, X Special, Guard Spec., Dire Hit and X Accuracy.
- Bicycle not received. Item PC has free capacity. Discarding or depositing a nonessential item is allowed. No particular recovery method is required.

### Success

- Free enough bag space, exchange the Bike Voucher and receive the Bicycle during the attempt.
