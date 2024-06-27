from dataclasses import dataclass


@dataclass
class Deck:
    cards: list[str]
    commanders: list[str]
