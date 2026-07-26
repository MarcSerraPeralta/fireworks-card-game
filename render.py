from engine import Hint, State, Card, Color, Rank, Hints, is_game_over


def dict_to_hint(d: dict[str, str | int]) -> Hint:
    if "color" in d:
        return Color(d["color"])
    elif "rank" in d:
        return Rank(d["rank"])
    else:
        raise ValueError("Dict must have 'color' or 'rank'")


def get_max_ranks(cards: list[Card]) -> list[int]:
    max_ranks = [0, 0, 0, 0, 0]
    color_to_ind = {c: i for i, c in enumerate(Color)}
    for card in cards:
        ind = color_to_ind[card.color]
        max_ranks[ind] = max(max_ranks[ind], card.rank.value)
    return max_ranks


def get_player(hands: list[list[Card]]) -> int:
    default = [Card(color=Color("Red"), rank=Rank(1)) for _ in range(5)]
    for player, hand in enumerate(hands):
        if hand == default:
            return player
    return -1


def my_card_to_dict(hand: Card, hints: Hints):
    card = {
        "color": "Gray",
        "rank": "",
        "valid_ranks": [r.value for r in hints.ranks],
        "eliminated_ranks": [r.value for r in Rank if r not in hints.ranks],
        "valid_colors": [c.value for c in hints.colors],
        "eliminated_colors": [c.value for c in Color if c not in hints.colors],
    }
    return card


def other_card_to_dict(hand: Card, hints: Hints):
    card = {
        "color": hand.color.value,
        "rank": str(hand.rank.value),
        "valid_ranks": [r.value for r in hints.ranks],
        "eliminated_ranks": [r.value for r in Rank if r not in hints.ranks],
        "valid_colors": [c.value for c in hints.colors],
        "eliminated_colors": [c.value for c in Color if c not in hints.colors],
    }
    return card


def render_state_to_dict(state: State) -> dict[str, object]:
    deck_display = {"color": "Blue", "value": len(state.deck)}
    if len(state.deck) == 0:
        deck_display = {"color": "Red", "value": state.num_extra_turns}

    discard_pile: list[list[int]] = []
    for color in Color:
        cards = [card.rank.value for card in state.discarded if card.color == color]
        discard_pile.append(cards)

    max_ranks = get_max_ranks(state.played)

    my_player = get_player(state.hands)
    hands = []
    for player, (hand, hints) in enumerate(zip(state.hands, state.hints)):
        if player == my_player:
            data = [my_card_to_dict(card, hint) for card, hint in zip(hand, hints)]
            hands.append(data)
        else:
            data = [other_card_to_dict(card, hint) for card, hint in zip(hand, hints)]
            hands.append(data)

    return {
        "lives": state.num_lives,
        "hints": state.num_hints,
        "score": sum(max_ranks),
        "max_score": 25,
        "deck": deck_display,
        "fireworks": [(c.value, v) for c, v in zip(Color, max_ranks)],
        "discard_pile": discard_pile,
        "last_actions": state.last_actions[-5:],
        "player_turn": state.player_turn,
        "hands": hands,
        "player_names": state.player_names,
        "game_over": is_game_over(state),
    }

