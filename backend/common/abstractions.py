from dataclasses import dataclass


@dataclass
class Deck:
    main: list[str]
    commanders: list[str]
