"""Reporting labels for published attempts. Nothing here changes a score or what a model sees.

Most labels are computed from each attempt's own files. The two tables below hold facts the
files do not record. Each was measured once from frozen runs (docs/history/fair-harness-v061.md).
"""

# Zero-score Short cells that the v0.61 failure study traced to the harness, not to the model.
_SPINNERS = 'The local map drew the spinner tiles of this maze as plain floor, so the model kept stepping onto them.'
_QUANTITY = 'The plan matched what most models submitted, but the validator rejected quantity 1 on use_item.'
HARNESS_FAULTS = {
    'focused-pass-v056/cell-0223': _QUANTITY,
    'focused-pass-v056/cell-0235': _QUANTITY,
    'focused-pass-v056/cell-0275': 'The grader stopped the run when the model picked up a free Poke Ball, which the task allowed.',
    'focused-pass-v056/cell-0289': _SPINNERS,
    'focused-pass-v056/cell-0290': _SPINNERS,
    'focused-pass-v056/cell-0292': _SPINNERS,
    'focused-pass-v056/cell-0293': _SPINNERS,
}

# Long runs: (moves the game refused at a tile pair collision, all blocked moves), over each run's whole record.
# Before v0.61 the local map drew both tiles of a pair as floor, so these steps looked open.
LONG_PAIR_BLOCKS = {
    'long-v065-opus': (34, 137), 'long-v065-sol': (37, 197), 'long-v065-sonnet': (246, 434),
    'long-v065-terra': (9, 300), 'long-v067-astra': (10, 158), 'long-v067-fable': (103, 228),
    'long-v069-luna': (0, 249), 'long-v073-haiku': (0, 37),
    'long-v068-astra-4k': (55, 388), 'long-v069-sol-4k': (177, 477), 'long-v069-terra-4k': (93, 613),
    'long-v070-luna-plus4k': (0, 898), 'long-v071-opus-4k': (56, 327), 'long-v071-sonnet-4k': (990, 1364),
    'long-v072-astra-6k': (93, 538), 'long-v072-astra-8k': (122, 765),
}

RETRY_RULE = ('No gameplay retries. An attempt that ends in play is final, whatever its score. '
              'An infrastructure fault (provider outage, quota, reboot, full disk) stops the attempt, which then '
              'resumes from its last completed decision with its limits unchanged. Every stopped or replaced copy is '
              'kept and listed here. Before v0.61, attempts stopped by harness faults were also rerun from the start.')

# Archive folders that hold replaced or repaired attempts, by folder name.
ARCHIVES = {
    'original-errors-v058': ('replaced', 'Stopped by a provider or response error. Rerun from the start after the v0.58 provider fixes.'),
    'original-navigation-v056': ('replaced', 'The navigation task changed. Rerun from the start on the new task.'),
    'original-cli-error': ('replaced', 'Stopped by a Codex CLI error. Rerun from the start.'),
    'observation-repair-v059': ('continued', 'An inspection result was too large to send. Continued after decision 505 once it was shortened without loss.'),
}

NOTES = {
    'earlier_spec': ('earlier task version', 'Ran an earlier version of this task. Its text or rules changed later.'),
    'earlier_start': ('earlier start state', 'Started from a different save state than the current version of this task, '
                      'such as a level 55 instead of a level 60 team in the scarce-resource League.'),
    'earlier_policy': ('earlier battle controller', 'Preparation was scored with an earlier version of the fixed battle controller.'),
    'no_end_line': ('no run-ends line', 'The prompt did not say that the run ends by itself once the task is complete.'),
    'harness_fault': ('harness fault', 'The v0.61 failure study traced this zero to the harness, not to the model.'),
}
