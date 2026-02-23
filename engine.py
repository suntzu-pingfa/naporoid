# engine.py
# Napoleon (core logic) - extracted from napo.py for Kivy(Android)
# Comments/messages are kept in English like the original.

import os
import random
import datetime

# ----------------------------
# Card utilities
# ----------------------------

SUITS = ["s", "h", "d", "c"]  # spades, hearts, diamonds, clubs
SUIT_ORDER = {"s": 4, "h": 3, "d": 2, "c": 1}

SUIT_LABEL = {"s": "Spade", "h": "Heart", "d": "Diamond", "c": "Club"}
SUIT_LABEL_INV = {v: k for k, v in SUIT_LABEL.items()}

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "0", "J", "Q", "K", "A"]  # 0 means 10
RANK_TO_INT = {r: i for i, r in enumerate(RANKS, start=2)}
RANK_TO_INT["0"] = 10
RANK_TO_INT["J"] = 11
RANK_TO_INT["Q"] = 12
RANK_TO_INT["K"] = 13
RANK_TO_INT["A"] = 14

SPECIAL_MIGHTY = "sA"
SPECIAL_YORO = "hQ"
FACE_DOWN = "BACK"

PICT_RANKS = {"0", "J", "Q", "K", "A"}  # 10/J/Q/K/A


def is_joker(c: str) -> bool:
    return c == "Jo"


def suit(c: str) -> str:
    if is_joker(c) or not c:
        return ""
    return c[0]


def rank(c: str) -> str:
    if is_joker(c) or not c:
        return ""
    return c[1]


def reverse_suit(s: str) -> str:
    return {"s": "c", "c": "s", "h": "d", "d": "h"}.get(s, "")


def card_value_basic(c: str) -> int:
    if is_joker(c):
        return 0
    return RANK_TO_INT.get(rank(c), 0)


def sort_cards(cards):
    # Suit first (s,h,d,c), then number (2..A), joker last
    def keyf(c):
        if is_joker(c):
            return (99, 99)
        return (-SUIT_ORDER[suit(c)], card_value_basic(c))

    return sorted(cards, key=keyf)


def build_deck_4p():
    deck = ["Jo"]
    for s in SUITS:
        for r in RANKS:
            deck.append(f"{s}{r}")
    return deck  # 53


# ----------------------------
# Image filename mapping (matches "X_of_suit.png" format)
# ----------------------------

def card_to_filename(c: str) -> str:
    if c == "Jo":
        return "joker.png"

    s = suit(c)
    r = rank(c)
    suit_word = {"s": "spades", "h": "hearts", "d": "diamonds", "c": "clubs"}[s]

    if r == "A":
        return f"ace_of_{suit_word}.png"
    if r == "K":
        return f"king_of_{suit_word}.png"
    if r == "Q":
        return f"queen_of_{suit_word}.png"
    if r == "J":
        return f"jack_of_{suit_word}.png"
    if r == "0":
        return f"10_of_{suit_word}.png"
    return f"{r}_of_{suit_word}.png"


def is_pict(c: str) -> bool:
    return (not is_joker(c)) and (rank(c) in PICT_RANKS)


# ----------------------------
# Player / Engine
# ----------------------------

class Player:
    def __init__(self, pid: int, is_human: bool = False):
        self.id = pid
        self.is_human = is_human
        self.cards = []
        self.role = "unknown"  # napoleon/lieut/coalition/unknown
        self.revealed_role = False


class GameEngine:
    def __init__(self):
        self.players = [Player(1, True), Player(2, False), Player(3, False), Player(4, False)]
        self.deck = []
        self.mount = []

        self.obverse = ""
        self.target = 0
        self.declaration = ""
        self.lieut_card = ""

        self.turn_no = 0
        self.leader_id = 1
        self.stage = "idle"
        self.napoleon_id = 1

        self.turn_cards = []    # [(pid, actual_card)]
        self.turn_display = []  # [(pid, shown_code or actual)]
        self.first_card = ""
        self.first_suit = ""

        self.lieut_id = None
        self.lieut_in_mount = False
        self.lieut_revealed = False

        self.pict_won_count = {1: 0, 2: 0, 3: 0, 4: 0}
        self.pict_won_cards = {1: [], 2: [], 3: [], 4: []}

    def human(self) -> Player:
        return self.players[0]

    def new_game(self):
        self.deck = build_deck_4p()
        random.shuffle(self.deck)

        self.mount = []
        self.obverse = ""
        self.target = 0
        self.declaration = ""
        self.lieut_card = ""

        self.turn_no = 0
        self.leader_id = 1
        self.stage = "bid"
        self.napoleon_id = 1

        self.turn_cards = []
        self.turn_display = []
        self.first_card = ""
        self.first_suit = ""

        self.lieut_id = None
        self.lieut_in_mount = False
        self.lieut_revealed = False

        self.pict_won_count = {1: 0, 2: 0, 3: 0, 4: 0}
        self.pict_won_cards = {1: [], 2: [], 3: [], 4: []}

        for p in self.players:
            p.cards = []
            p.role = "unknown"
            p.revealed_role = False

        for _ in range(5):
            self.mount.append(self.deck.pop())

        for _ in range(12):
            for p in self.players:
                p.cards.append(self.deck.pop())

        for p in self.players:
            p.cards = sort_cards(p.cards)
        self.mount = sort_cards(self.mount)

    def set_declaration(self, obverse_suit: str, target: int):
        """
        Minimal declaration finalize for UI.
        - obverse_suit: one of 's','h','d','c'
        - target: 1..20 (pict cards)
        """
        if self.stage != "bid":
            return False, "Not in bid stage."
        if obverse_suit not in SUITS:
            return False, "Invalid obverse suit."
        if not isinstance(target, int):
            return False, "Invalid target."
        if target < 1 or target > 20:
            return False, "Target must be 1..20."

        self.obverse = obverse_suit
        self.target = target
        self.declaration = f"{SUIT_LABEL[self.obverse]} {self.target}"
        # Next step is lieut selection in your ruleset
        self.stage = "lieut"
        return True, "OK"

    def set_lieut_card(self, c):
        nap = self.players[self.napoleon_id - 1]
        if c in nap.cards:
            return False, "Lieut card must be outside Napoleon's hand."

        self.lieut_card = c
        self.lieut_id = None
        self.lieut_in_mount = False
        self.lieut_revealed = False

        if c in self.mount:
            self.lieut_in_mount = True
            self.lieut_id = None
        else:
            for p in self.players:
                if c in p.cards:
                    self.lieut_id = p.id
                    break

        self.stage = "exchange"
        return True, "OK"

    def do_swap(self, hand_card, mount_card):
        if self.stage != "exchange":
            return False, "Not in exchange stage."

        nap = self.players[self.napoleon_id - 1]
        if hand_card not in nap.cards:
            return False, "Selected hand card not in Napoleon hand."
        if mount_card not in self.mount:
            return False, "Selected mount card not in Mount."

        nap.cards.remove(hand_card)
        self.mount.remove(mount_card)
        nap.cards.append(mount_card)
        self.mount.append(hand_card)

        nap.cards = sort_cards(nap.cards)
        self.mount = sort_cards(self.mount)
        return True, "OK"

    def finish_exchange(self):
        if self.stage != "exchange":
            return False, "Not in exchange stage."
        self.stage = "play"
        self.turn_no = 1
        # First lead is Napoleon.
        self.leader_id = self.napoleon_id
        self.turn_cards = []
        self.turn_display = []
        self.first_card = ""
        self.first_suit = ""
        return True, "OK"

    def legal_moves(self, pid):
        p = self.players[pid - 1]
        hand = p.cards[:]

        # Turn 1: obverse-suit cards cannot be played by anyone
        if self.turn_no == 1 and self.obverse:
            hand = [c for c in hand if is_joker(c) or suit(c) != self.obverse]
            # Turn 1: Napoleon cannot lead Joker.
            if (not self.turn_cards) and pid == self.napoleon_id:
                hand = [c for c in hand if c != "Jo"]

        if not self.turn_cards:
            return hand

        lead = self.first_card
        lead_suit = self.first_suit
        if is_joker(lead):
            lead_suit = self.first_suit

        same = [c for c in hand if (not is_joker(c)) and suit(c) == lead_suit]
        # Mighty (sA) exception:
        # Even when Spade is led, sA is not forced as a follow card,
        # but it is still legal to play.
        if lead_suit == "s":
            same_wo_mighty = [c for c in same if c != SPECIAL_MIGHTY]
            if same_wo_mighty:
                legal = same_wo_mighty + (["Jo"] if "Jo" in hand else [])
                if SPECIAL_MIGHTY in hand:
                    legal.append(SPECIAL_MIGHTY)
                return legal
            # If the only spade is sA, follow-suit is not forced.
            # Player may play any card (including sA).
            if SPECIAL_MIGHTY in same:
                return hand
        if same:
            return same + (["Jo"] if "Jo" in hand else [])
        return hand

    def _pict_cards_in_turn(self):
        return [c for _, c in self.turn_cards if is_pict(c)]

    def _pict_set(self):
        return set([f"{s}{r}" for s in SUITS for r in PICT_RANKS])

    def _is_pict(self, c: str) -> bool:
        return is_pict(c)

    def yoro_is_special_now(self):
        cards = [c for _, c in self.turn_cards]
        return (SPECIAL_MIGHTY in cards) and (SPECIAL_YORO in cards)

    def is_special(self, c):
        if is_joker(c):
            return True
        if c == SPECIAL_MIGHTY:
            return True
        if c == SPECIAL_YORO:
            return self.yoro_is_special_now()
        if self.obverse:
            if c == f"{self.obverse}J":
                return True
            if c == f"{reverse_suit(self.obverse)}J":
                return True
        return False

    def eff_suit_for_sameness(self, c):
        # Joker effective suit = lead suit for that Turn
        if is_joker(c):
            return self.first_suit
        return suit(c)

    def strength(self, c):
        # Special cards dominate
        if c == SPECIAL_MIGHTY:
            # If sA and hQ are both in this turn, hQ outranks sA.
            if self.yoro_is_special_now():
                return 4350
            return 4500
        if c == SPECIAL_YORO:
            return 4400 if self.yoro_is_special_now() else RANK_TO_INT["Q"]
        if self.obverse:
            if c == f"{self.obverse}J":
                return 4300
            if c == f"{reverse_suit(self.obverse)}J":
                return 4200
        # Joker base strength is below 2.
        # Its exceptional win condition is handled in judge_turn_winner().
        if is_joker(c):
            return 1
        return card_value_basic(c)

    def judge_turn_winner(self):
        cards = self.turn_cards[:]
        lead_suit = self.first_suit
        first_is_joker = is_joker(self.first_card)
        shown_map = {pid: shown for pid, shown in self.turn_display}

        # (2) rule: active only when all of the following are true:
        # - First card is NOT Joker
        # - No special card in the turn (sA / obverse J / reverse J / sA+hQ case)
        # - All 4 cards are non-Joker and same suit
        # - No face-down shown on table
        face_down_exists = any((shown == "BACK") for _, shown in self.turn_display)
        obv_j = f"{self.obverse}J" if self.obverse else ""
        rev_j = f"{reverse_suit(self.obverse)}J" if self.obverse else ""
        turn_cards_only = [c for _, c in cards]
        has_forbidden_special = (SPECIAL_MIGHTY in turn_cards_only) or (obv_j in turn_cards_only) or (rev_j in turn_cards_only) or ((SPECIAL_MIGHTY in turn_cards_only) and (SPECIAL_YORO in turn_cards_only))
        all_non_joker = all((not is_joker(c)) for c in turn_cards_only)
        same_suit_all = all_non_joker and (len({suit(c) for c in turn_cards_only}) == 1)
        two_rule_active = (not first_is_joker) and (not has_forbidden_special) and same_suit_all and (not face_down_exists)
        non_joker_suits = {suit(c) for c in turn_cards_only if (not is_joker(c))}
        joker_dominant = first_is_joker and (not has_forbidden_special) and (len(non_joker_suits) == 1)

        best_pid = cards[0][0]
        best_score = -10**9
        best_c = cards[0][1]

        for pid, c in cards:
            if is_joker(c):
                # Joker wins only when:
                # - it was led (first card), and
                # - all non-joker cards in this turn are same suit, and
                # - no special cards (sA / sA+hQ / obverse J / reverse J).
                # Otherwise Joker is weaker than rank-2.
                score = 4100 if joker_dominant else 1
            elif (not self.is_special(c)):
                # Face-down trump rule:
                # If a face-down card is Obverse suit, and lead card is not Joker,
                # it competes as trump and highest trump wins (except specials which are handled above).
                is_face_down = (shown_map.get(pid) == FACE_DOWN)
                if (not first_is_joker) and is_face_down and self.obverse and suit(c) == self.obverse:
                    score = 2000 + card_value_basic(c)
                elif suit(c) != lead_suit:
                    score = -10000 + card_value_basic(c)
                else:
                    score = card_value_basic(c)
            else:
                score = self.strength(c)

            if two_rule_active and (not is_joker(c)) and rank(c) == "2":
                score += 3000

            if score > best_score:
                best_score = score
                best_pid = pid
                best_c = c

        return best_pid, best_c, two_rule_active

    def award_turn(self):
        winner_id, win_card, two_active = self.judge_turn_winner()

        picts = self._pict_cards_in_turn()
        if picts:
            self.pict_won_count[winner_id] += len(picts)
            self.pict_won_cards[winner_id].extend(picts)

        self.advance_leader(winner_id)
        return winner_id, win_card, two_active, picts

    def advance_leader(self, winner_id: int):
        self.leader_id = winner_id

    def _shown_code_for_play(self, pid: int, c: str):
        """Return what should be shown on table for this play.
        Rule: If the player has NO card of the lead suit in hand (excluding Joker),
        then their played card is shown face-down as 'BACK'. Leader card is always face-up.
        """
        # Leader card is always face-up
        if not self.turn_cards:
            return c

        lead_suit = self.first_suit

        # Check whether player has any lead-suit card in hand at the moment of play
        p = self.players[pid - 1]
        has_lead = any((not is_joker(x)) and suit(x) == lead_suit for x in p.cards)

        if not has_lead:
            return FACE_DOWN
        return c

    def last_shown_for_pid(self, pid: int):
        for p, shown in reversed(self.turn_display):
            if p == pid:
                return shown
        return None

    def play_card(self, pid, c):
        if self.stage != "play":
            return False, "Not in play stage."

        p = self.players[pid - 1]
        if c not in p.cards:
            return False, "Card not in hand."

        # Turn 1 rules:
        # 1) Obverse-suit cards cannot be played by anyone.
        # 2) Napoleon cannot lead Joker.
        if self.turn_no == 1:
            if (not is_joker(c)) and self.obverse and suit(c) == self.obverse:
                return False, "Turn 1: Obverse suit cards cannot be played."
            if pid == self.napoleon_id and (not self.turn_cards) and is_joker(c):
                return False, "Turn 1: Napoleon cannot lead Joker."

        legal = self.legal_moves(pid)
        if c not in legal:
            return False, "Illegal move."

        if not self.turn_cards:
            self.first_card = c
            if is_joker(c):
                self.first_suit = self.obverse
            else:
                self.first_suit = suit(c)

        # Decide table-facing state BEFORE removing card from hand.
        shown = self._shown_code_for_play(pid, c)
        p.cards.remove(c)

        # Reveal Lieut when Lieut card is played.
        if (not self.lieut_in_mount) and (not self.lieut_revealed) and c == self.lieut_card:
            self.lieut_revealed = True
            if self.lieut_id is not None:
                lp = self.players[self.lieut_id - 1]
                lp.role = "lieut"
                lp.revealed_role = True
            for op in self.players:
                if op.id == self.napoleon_id:
                    continue
                if self.lieut_id is not None and op.id == self.lieut_id:
                    continue
                op.role = "coalition"
                op.revealed_role = True

        self.turn_cards.append((pid, c))
        self.turn_display.append((pid, shown))

        if len(self.turn_cards) == 4:
            had_face_down = any(sh == FACE_DOWN for _, sh in self.turn_display)
            winner_id, win_card, two_active, picts = self.award_turn()

            if self.turn_no >= 12:
                self.stage = "done"
            else:
                self.turn_no += 1
                self.turn_cards = []
                self.turn_display = []
                self.first_card = ""
                self.first_suit = ""

            return True, {
                "turn_complete": True,
                "winner_id": winner_id,
                "win_card": win_card,
                "two_active": two_active,
                "picts": picts,
                "had_face_down": had_face_down,
                "shown": shown,
            }

        return True, {"turn_complete": False, "had_face_down": False, "shown": shown}

    def turn_complete(self) -> bool:
        return len(self.turn_cards) == 0 and self.stage in {"play", "done"}

    def _nap_side_ids(self):
        ids = {self.napoleon_id}
        if self.lieut_revealed and self.lieut_id is not None and not self.lieut_in_mount:
            ids.add(self.lieut_id)
        return ids

    def _side_of(self, pid):
        if pid in self._nap_side_ids():
            return "nap"
        return "coal"

    def _estimate_strength(self, c: str) -> int:
        return self.strength(c)

    def _resource_cost(self, pid: int, c: str) -> int:
        if c == "Jo":
            if self.turn_cards:
                return 50000
            return 60000
        return 0

    def _nap_side_pict_public(self) -> int:
        nap_ids = self._nap_side_ids()
        return sum(self.pict_won_count[i] for i in nap_ids)

    def cpu_choose(self, pid):
        legal = self.legal_moves(pid)
        if not legal:
            return None

        def score(c):
            return self._estimate_strength(c) - self._resource_cost(pid, c)

        best = max(legal, key=score)
        return best

    def score(self):
        nap_ids = self._nap_side_ids()
        coal_ids = {1, 2, 3, 4} - nap_ids
        nap_pict = sum(self.pict_won_count[pid] for pid in nap_ids)
        coal_pict = sum(self.pict_won_count[pid] for pid in coal_ids)
        total_pict = nap_pict + coal_pict

        if self.stage != "done":
            return {
                "done": False,
                "nap_pict": nap_pict,
                "coal_pict": coal_pict,
                "total_pict": total_pict,
                "target": self.target,
            }

        if nap_pict == 20:
            return {
                "done": True,
                "nap_win": False,
                "reason": "Napoleon side took all 20 pict cards -> LOSE",
                "nap_pict": nap_pict,
                "coal_pict": coal_pict,
                "total_pict": total_pict,
                "target": self.target,
            }

        if nap_pict >= self.target and self.target > 0:
            return {
                "done": True,
                "nap_win": True,
                "reason": "Napoleon side reached target",
                "nap_pict": nap_pict,
                "coal_pict": coal_pict,
                "total_pict": total_pict,
                "target": self.target,
            }

        return {
            "done": True,
            "nap_win": False,
            "reason": "Target not reached",
            "nap_pict": nap_pict,
            "coal_pict": coal_pict,
            "total_pict": total_pict,
            "target": self.target,
        }

