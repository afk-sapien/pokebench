# Navigation without battles

Forest crossing, Mt. Moon, Victory Road and the blocked Saffron route now use navigation-no-battles-v1. Relevant trainers start defeated. Random wild encounters are disabled across map transitions by a guarded Red ROM override of TryDoWildEncounter, which returns the native no-encounter result. The original ROM file is unchanged. There are no repeated RAM writes, no automatic moves and no battle decisions supplied to the agent.

Party, inventory, decision limits, token limits, map layouts and puzzle objectives stay unchanged. The fossil Super Nerd starts defeated, so either fossil can be chosen without a battle. Saffron Gym and Rocket Hideout already clear the relevant trainers and have no wild encounters on their task maps. They retain their existing results.

Original attempts remain archived with their original fixtures. Replacement navigation attempts are recorded separately and count toward the same total spending ceiling. The current comparison uses the replacement condition for these four tasks and keeps pending replacements explicit.
