from collections import defaultdict
import json
from urllib.request import Request, urlopen


def combos_including_other_combos(pool: set[frozenset[str]]) -> dict[frozenset[str], set[frozenset[str]]]:
    combo_db = defaultdict(set)
    for combo in pool:
        for card in combo:
            combo_db[card].add(combo)
    result = defaultdict(set)
    for combo in pool:
        for card in combo:
            for other_combo in combo_db[card]:
                if other_combo.issubset(combo) and other_combo != combo:
                    result[combo].add(other_combo)
        if combo not in result:
            result[combo] = set()
    return result

def find_combos():
    combosdb = dict[frozenset[str], frozenset[str]]()
    combosdata = dict[frozenset[str], tuple[str, str]]()
    combos_reverse_id = dict[frozenset[str], str]()
    combos_by_id = dict[str, frozenset[str]]()
    # Commander Spellbook database fetching
    req = Request(
        'https://sheets.googleapis.com/v4/spreadsheets/1KqyDRZRCgy8YgMFnY0tHSw_3jC99Z0zFvJrPbfm66vA/values:batchGet?ranges=combos!A2:Q&key=AIzaSyBD_rcme5Ff37Evxa4eW5BFQZkmTbgpHew')
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        for row in data['valueRanges'][0]['values']:
            cards = frozenset(map(lambda name: name.lower().strip(' \t\n\r'), filter(
                lambda name: name is not None and len(name) > 0, row[1:11]))) - set([''])
            if len(cards) <= 1:
                continue
            combos_reverse_id[cards] = row[0]
            combos_by_id[row[0]] = cards
            pros = [token.replace('.', '') for token in row[14].lower().strip(' \t\n\r').split('. ')]
            combosdb[cards] = frozenset(pros)
            combosdata[cards] = (row[12], row[13])
    cioc = combos_including_other_combos(combosdb.keys())
    result = []
    for c, ics in cioc.items():
        features = frozenset(combosdb[c])
        needs = frozenset()
        cards = c
        for ic in ics:
            features -= combosdb[ic]
            needs |= combosdb[ic]
            cards -= ic
        result.append((combos_reverse_id[c], cards, needs, features, combosdata[c][0], combosdata[c][1], c, ics))
    return result, combos_reverse_id

x, combos_reverse_id = find_combos()
i = 0
for id, cards, needs, features, prerequisites, description, original, included in x:
    if len(cards) == 0:
        print(f'{i}. Combo {id} {list(original)} is a mashup of:')
        i += 1
        for c in included:
            print(f'\t{combos_reverse_id[c]} which contains {list(c)}')
        print('\n')
    if len(features) == 0:
        print(f'{i}. Combo {id} {list(original)} is probably useless, because the same features are provided by:')
        i += 1
        for c in included:
            print(f'\tCombo {combos_reverse_id[c]} which contains {list(c)}')
        print('\n')
            