from dataclasses import dataclass


@dataclass
class CardInDeck:
    card: str
    quantity: int = 1


@dataclass
class Deck:
    main: list[CardInDeck]
    commanders: list[CardInDeck]
