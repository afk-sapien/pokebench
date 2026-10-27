"""Execute an agent-selected item or party change through real controller input."""
import re

from pokecore.gen1 import read_bag, read_party
from pokecore.controls import ControllerPort, use_item, switch_pokemon, identity as identity
from pokecore.shortcuts import choose_move

from .dialogue import continue_ready
from .gameplay import ui_state


ITEMS = {'ANTIDOTE':11, 'BURNHEAL':12, 'ICEHEAL':13, 'AWAKENING':14, 'PARLYZHEAL':15,
         'FULLRESTORE':16, 'MAXPOTION':17, 'HYPERPOTION':18, 'SUPERPOTION':19, 'POTION':20,
         'FULLHEAL':52, 'REVIVE':53, 'MAXREVIVE':54, 'ELIXER':82, 'MAXELIXER':83,
         'ELIXIR':82, 'MAXELIXIR':83}


def normalize(text):
    return re.sub('[^A-Z0-9]', '', text.upper().replace('É', 'E'))


def parse_item(argument):
    parts = argument.split(':')
    if len(parts) != 2 or normalize(parts[0]) not in ITEMS or parts[1].strip() not in tuple('123456'):
        raise ValueError('Use item name:party slot, such as Full Restore:1. Only supported restorative items are allowed.')
    return ITEMS[normalize(parts[0])], int(parts[1].strip()) - 1


def execute_shortcut(session, command, send, choose, result):
    port = ControllerPort(
        memory=session.engine.memory, send=send, choose=choose,
        observe=lambda: ui_state(session.engine.memory), frame=lambda: session.frame,
        stopped=lambda: bool(session.reason), continue_ready=lambda: continue_ready(session.engine),
        item_labels=session.gameplay_catalog['labels']['items'],
        read_party=read_party, read_bag=read_bag,
        version='red',
    )
    if command['command'] == 'use_item':
        item, slot = parse_item(command['argument'])
        result.update(use_item(port, item, slot))
    elif command['command'] == 'use_move':
        result.update(choose_move(port, int(command['argument']) - 1))
    else:
        result.update(switch_pokemon(port, int(command['argument']) - 1))
