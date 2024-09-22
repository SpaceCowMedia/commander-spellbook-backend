import re
from dataclasses import dataclass


MAX_DECKLIST_LINES = 600
DECKLIST_LINE_REGEX = r'^(?:(?P<quantity>\d{1,20})x?\s{1,6})?(?P<card>.*?[^\s])(?:(?:\s{1,6}<\w{1,50}>)?(?:\s{1,6}\[\w{1,50}\](?:\s{1,6}\(\w{1,50}\))?|\s{1,6}\(\w{1,50}\)(?:\s[\w-]+(?:\s\*\w\*)?)?))?$'
DECKLIST_LINE_PARSER = re.compile(DECKLIST_LINE_REGEX)


@dataclass
class CardInDeck:
    card: str
    quantity: int = 1


@dataclass
class Deck:
    main: list[CardInDeck]
    commanders: list[CardInDeck]

    @classmethod
    def from_text(cls, decklist: str) -> 'Deck':
        lines = decklist.splitlines()[:MAX_DECKLIST_LINES]
        main = list[CardInDeck]()
        commanders = list[CardInDeck]()
        current_set = main
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line_lower = line.lower()
            if line_lower.startswith('// command') or line_lower in ('commanders', 'commander', 'command', 'command zone'):
                current_set = commanders
            elif line_lower.startswith('//') or line_lower in ('main', 'deck'):
                current_set = main
            elif regex_match := DECKLIST_LINE_PARSER.fullmatch(line):
                current_set.append(CardInDeck(card=regex_match.group('card'), quantity=int(regex_match.group('quantity') or 1)))
        return cls(main=main, commanders=commanders)
