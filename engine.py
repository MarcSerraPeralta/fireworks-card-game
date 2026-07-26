from enum import Enum
from dataclasses import dataclass, field

import random
from copy import deepcopy


class Color(Enum):
    RED = "Red"
    YELLOW = "Yellow"
    GREEN = "Green"
    BLUE = "Blue"
    WHITE = "White"


class Rank(Enum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5


@dataclass(frozen=True)
class Card:
    color: Color
    rank: Rank


Hint = Color | Rank


@dataclass
class Hints:
    colors: set[Color] = field(default_factory=lambda: set(Color))
    ranks: set[Rank] = field(default_factory=lambda: set(Rank))


Note = list[Card]


@dataclass
class State:
    player_turn: int
    player_names: list[str]
    num_extra_turns: int
    deck: list[Card]
    hands: list[list[Card]]
    hints: list[list[Hints]]
    notes: list[list[Note]]
    discarded: list[Card] = field(default_factory=list)
    played: list[Card] = field(default_factory=list)
    last_actions: list[list[str]] = field(default_factory=list)
    num_hints: int = 8
    num_lives: int = 3


def get_shuffled_deck(seed: int | None = None) -> list[Card]:
    """Returns a shuffled deck."""
    deck: list[Card] = []

    counts = {1: 3, 2: 2, 3: 2, 4: 2, 5: 1}
    for color in Color:
        for rank in Rank:
            count = counts[rank.value]
            deck += [Card(color, rank)] * count

    rng = random.Random(seed)
    rng.shuffle(deck)

    return deck


def initialize_state(players: list[str] | int, seed: int | None = None) -> State:
    """Returns initial state of the game, with a shuffled deck."""
    if isinstance(players, list):
        num_players = len(players)
    elif isinstance(players, int):
        num_players = players
        players = [f"Player {i}" for i in range(1, num_players + 1)]

    if num_players > 6:
        raise ValueError("Max number of players is 5.")

    deck = get_shuffled_deck(seed=seed)

    hands: list[list[Card]] = []
    for _ in range(num_players):
        new_hand = [deck.pop(0) for _ in range(5)]
        hands.append(new_hand)

    hints = [[Hints(), Hints(), Hints(), Hints(), Hints()] for _ in range(num_players)]
    notes: list[list[Note]] = [[[] for _ in range(5)] for _ in range(num_players)]

    rng = random.Random(seed)
    player_turn = rng.randint(0, num_players - 1)

    return State(
        deck=deck,
        hands=hands,
        hints=hints,
        player_turn=player_turn,
        notes=notes,
        num_extra_turns=num_players,
        player_names=players,
    )


class Game:
    def __init__(self, players: list[str] | int, seed: int | None = None):
        self.state: State = initialize_state(players, seed=seed)
        self._last_state: State | None = None

        self.num_players: int = len(self.state.player_names)
        self.game_over: bool = False
        return

    def play_card(self, card_ind: int):
        self._last_state = deepcopy(self.state)

        player_ind = self.state.player_turn
        card = self._remove_and_draw_card(player_ind, card_ind)
        if self._is_card_playable(card):
            self.state.played.append(card)
        else:
            self.state.discarded.append(card)
            self.state.num_lives -= 1

        if card.rank == Rank.FIVE:
            self.state.num_hints = min(8, self.state.num_hints + 1)

        action = ["play_card", self.state.player_names[player_ind], card.color.value, str(card.rank.value)]
        self.state.last_actions.append(action)

        self._advance_turn()
        if is_game_over(self.state):
            self.game_over = True
        return

    def discard_card(self, card_ind: int):
        self._last_state = deepcopy(self.state)

        player_ind = self.state.player_turn
        card = self._remove_and_draw_card(player_ind, card_ind)
        self.state.discarded.append(card)

        self.state.num_hints = min(8, self.state.num_hints + 1)

        action = ["discard_card", self.state.player_names[player_ind], card.color.value, str(card.rank.value)]
        self.state.last_actions.append(action)

        self._advance_turn()
        if is_game_over(self.state):
            self.game_over = True
        return

    def give_hint(self, player_ind: int, hint: Hint):
        self._last_state = deepcopy(self.state)

        if self.state.num_hints == 0:
            print("No hint tokens are available.")
            return

        if self.state.player_turn == player_ind:
            print("Cannot give hint to yourself.")
            return

        hand = self.state.hands[player_ind]
        if isinstance(hint, Color):
            for i in range(5):
                if hand[i].color == hint:
                    self.state.hints[player_ind][i].colors = {hint}
                else:
                    self.state.hints[player_ind][i].colors.discard(hint)
        elif isinstance(hint, Rank):
            for i in range(5):
                if hand[i].rank == hint:
                    self.state.hints[player_ind][i].ranks = {hint}
                else:
                    self.state.hints[player_ind][i].ranks.discard(hint)
        else:
            print("Hint must be Color or Rank.")
            return

        self.state.num_hints -= 1

        action = [
            "give_hint",
            self.state.player_names[self.state.player_turn],
            self.state.player_names[player_ind],
            hint.value if isinstance(hint, Color) else str(hint.value),
        ]
        self.state.last_actions.append(action)

        self._advance_turn()
        if is_game_over(self.state):
            self.game_over = True
        return

    def add_note(self, player_ind: int, card_ind: int, note: Note):
        self.state.notes[player_ind][card_ind] = note
        return

    def undo(self):
        if self._last_state is None:
            print("Cannot undo twice.")
            return
        self.state = self._last_state
        self._last_state = None
        return

    def get_game_view_for(self, player_ind: int) -> State:
        view = deepcopy(self.state)

        placeholder = Card(Color.RED, Rank.ONE)
        view.deck = [placeholder for _ in view.deck]
        view.hands[player_ind] = [placeholder for _ in view.hands[player_ind]]
        for other_player_ind in range(self.num_players):
            if other_player_ind == player_ind:
                continue
            view.notes[other_player_ind] = []
        return view

    def _advance_turn(self):
        self.state.player_turn = (self.state.player_turn + 1) % self.num_players
        if not self.state.deck:
            self.state.num_extra_turns -= 1
        return

    def _remove_and_draw_card(self, player_ind: int, card_ind: int) -> Card:
        card = self.state.hands[player_ind].pop(card_ind)
        _ = self.state.hints[player_ind].pop(card_ind)
        _ = self.state.notes[player_ind].pop(card_ind)

        if self.state.deck:
            new_card = self.state.deck.pop(0)
            self.state.hands[player_ind].append(new_card)
            self.state.hints[player_ind].append(Hints())
            self.state.notes[player_ind].append([])
        return card

    def _is_card_playable(self, card: Card) -> bool:
        played_of_color = [c for c in self.state.played if c.color == card.color]

        current_rank = 0
        if played_of_color:
            current_rank = max(c.rank.value for c in played_of_color)

        return card.rank.value == current_rank + 1

def is_game_over(state: State) -> bool:
    if state.num_extra_turns == 0:
        return True
    if state.num_lives == 0:
        return True

    for color in Color:
        if len([c for c in state.played if c.color == color]) < 5:
            return False

    return True

