"""Task-specific automation permissions, fixed when a run starts."""
ASSISTED = "assisted-gameplay-v1"
MANUAL = "manual-menu-v1"
POLICIES = (ASSISTED, MANUAL)
MENU_TASKS = frozenset(("item-recovery", "buy-pokeballs"))
SKILLS = ("menu-operation", "navigation", "battle-strategy", "resource-planning", "campaign")
MANUAL_COMMANDS = ("press", "wait", "inspect")


def tested_skill(scenario):
    explicit = scenario.get("tested_skill")
    if explicit is not None:
        if explicit not in SKILLS:
            raise ValueError(f"Unsupported tested skill: {explicit}")
        return explicit
    task = scenario.get("task_id", scenario.get("name"))
    if task in MENU_TASKS:
        return "menu-operation"
    objective = scenario.get("objective", {})
    kind = objective.get("kind")
    if task in ("league", "league-hard", "campaign"):
        return "campaign"
    if kind in ("milestone", "battle-milestone", "wild-battle", "capture", "encounter-capture"):
        return "battle-strategy"
    if kind in ("opening", "reach-map", "location", "obtain-item"):
        return "navigation"
    return "resource-planning"


def resolve(scenario, explicit=None):
    policy = explicit if explicit is not None else scenario.get("action_policy")
    skill = scenario.get("tested_skill")
    if skill is not None and skill not in SKILLS:
        raise ValueError(f"Unsupported tested skill: {skill}")
    if policy is None:
        manual = skill == "menu-operation" or scenario.get("task_id", scenario.get("name")) in MENU_TASKS
        policy = MANUAL if manual else ASSISTED
    if policy not in POLICIES:
        raise ValueError(f"Unsupported action policy: {policy}")
    return policy


def from_manifest(manifest):
    # Old manifests used automatic gameplay even on the item recovery fixture.
    return resolve({}, manifest.get("action_policy", ASSISTED))


def commands(policy):
    from .gameplay_contract import COMMANDS
    resolve({}, policy)
    return MANUAL_COMMANDS if policy == MANUAL else COMMANDS


def description(policy):
    if policy == MANUAL:
        return ("Manual menu task. Allowed commands: press, wait, inspect. "
                "Operate the menus with individual button taps. Shortcuts, automatic menu selection "
                "and automatic dialogue advancement are disabled. Each press holds the button for "
                "8 frames then releases it for 24 frames, bounded by remaining frame limits. "
                "Use wait for animations or text, and press A only when you decide to continue.")
    return ("Assisted gameplay task. Menu, movement and battle shortcuts are enabled. "
            "The controller advances confirmed continue-only dialogue and stops at choices.")
