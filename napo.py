# napo.py
# Napoleon (GUI playable)
# Created by Takashi Fujiwara and IBM Bob on 2026-02-18
#
# IMPORTANT: All comments/messages are in English (as requested).
#
# Fixes in this revision:
# - Final Result:
#   - Insert ONE blank line before "Napoleon side WINS!!/LOSES!!"
#   - Make "Napoleon side WINS!!/LOSES!!" bold
# - Rule:
#   - Turn 1: Obverse-suit cards cannot be played by anyone (human and CPU)
# - Keep prior changes:
#   - Log left margin (1 leading space)
#   - Turn separator has 1 blank line before and after
#   - End of each Turn: show 4 cards again in one horizontal row (all face-up) with labels and WIN mark
#   - (2) rule: active only if all 4 cards are same effective suit AND no face-down exists; otherwise inactive
#   - Joker effective suit = lead suit for that Turn
#   - CPU Napoleon: smarter Lieut + smarter exchange
# - Bidding fixes:
#   - Ensure _finalize_bidding exists (compat + implementation)
#   - _bid_pass ends via _check_bid_end (no direct call to a missing method)
#   - If Human passed in this 2-player bidding UI, finalize immediately with current best bid
# - New rule:
#   - If Napoleon side (Napoleon + Lieut) takes ALL 20 pict cards (10/J/Q/K/A), Napoleon side LOSES.
# - AI upgrade (no cheat):
#   - BEFORE roles are revealed: CPUs play individually (simple).
#   - AFTER roles are revealed: Napoleon+Lieut cooperate, Coalition cooperates,
#     focusing on preventing the other side from taking pict cards.
# - Declaration bidding system upgrade:
#   - Any player (Human or CPU) can start Declaration based on hand strength evaluation
#   - CPUs evaluate their hands and randomly decide to declare first (70% chance if strong hand)
#   - Removed fixed turn order - players bid based on hand strength, not predetermined sequence
#   - CPU raise decisions now use hand strength scoring (0-15+ points) with probability-based logic
#   - Raise probability decreases as target increases (0.15 penalty per level above 13)
# - Joker usage optimization:
#   - Joker is a very valuable card (wins against everything except Yoro when both sA and hQ are played)
#   - CPUs avoid using Joker carelessly when not leading
#   - Strong penalties for using Joker on non-pict turns (50000 points when following, 60000 when leading)
#   - Moderate penalties for using Joker on pict turns (10000-40000 depending on situation)
#   - Before roles revealed: Joker priority lowered to 500 when following (vs 15000 when leading)

import os
import random
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk


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
# Image loading
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


class CardImages:
    def __init__(self, base_dir: str, scale: float = 0.1):
        self.base_dir = base_dir
        self.scale = scale
        self.cache = {}
        self.missing = self._make_missing()
        self.back = self._load_special("back.png")

    def _make_missing(self):
        img = Image.new("RGBA", (120, 160), (200, 200, 200, 255))
        return ImageTk.PhotoImage(img)

    def _load_special(self, fn: str):
        path = os.path.join(self.base_dir, fn)
        if not os.path.exists(path):
            return self.missing
        img = Image.open(path).convert("RGBA")
        nw = max(1, int(img.width * self.scale))
        nh = max(1, int(img.height * self.scale))
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)

    def get(self, c: str):
        if c in self.cache:
            return self.cache[c]
        fn = card_to_filename(c)
        path = os.path.join(self.base_dir, fn)
        if not os.path.exists(path):
            self.cache[c] = self.missing
            return self.cache[c]
        img = Image.open(path).convert("RGBA")
        nw = max(1, int(img.width * self.scale))
        nh = max(1, int(img.height * self.scale))
        img = img.resize((nw, nh), Image.Resampling.LANCZOS)
        self.cache[c] = ImageTk.PhotoImage(img)
        return self.cache[c]


# ----------------------------
# Game engine
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

        self.turn_no = 0          # 0 when not started, 1..12 during play
        self.leader_id = 1
        self.stage = "idle"       # idle/bid/lieut/exchange/play/done
        self.napoleon_id = 1

        self.turn_cards = []      # [(pid, actual_card)]
        self.turn_display = []    # [(pid, shown_card_or_BACK)]
        self.first_card = ""
        self.first_suit = ""      # lead suit (if Joker led, this is obverse in this UI)

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

    # ----------------------------
    # Lieut selection and exchange
    # ----------------------------

    def set_lieut_card(self, c: str):
        napoleon = self.players[self.napoleon_id - 1]
        if c in napoleon.cards:
            return (False, "That card is in Napoleon's hand. Select an OUTSIDE card.")

        self.lieut_card = c

        if c in self.mount:
            self.lieut_in_mount = True
            self.lieut_id = None
        else:
            self.lieut_in_mount = False
            self.lieut_id = None
            for p in self.players:
                if p.id == self.napoleon_id:
                    continue
                if c in p.cards:
                    self.lieut_id = p.id
                    break
            if self.lieut_id is None:
                return (False, "No player holds that card (it might be in Mount). Select another card.")

        self.stage = "exchange"
        return (True, "")

    def do_swap(self, hand_card: str, mount_card: str):
        if self.napoleon_id != 1:
            return (False, "Exchange is only available when you are Napoleon.")

        hp = self.human()
        if hand_card not in hp.cards:
            return (False, "Selected hand card is not in your hand.")
        if mount_card not in self.mount:
            return (False, "Selected mount card is not in Mount.")

        hp.cards.remove(hand_card)
        self.mount.remove(mount_card)
        hp.cards.append(mount_card)
        self.mount.append(hand_card)

        hp.cards = sort_cards(hp.cards)
        self.mount = sort_cards(self.mount)
        return (True, "")

    def finish_exchange(self):
        self.stage = "play"
        self.turn_no = 1
        self.leader_id = self.napoleon_id
        self.turn_cards = []
        self.turn_display = []
        self.first_card = ""
        self.first_suit = ""

    # ----------------------------
    # Play
    # ----------------------------

    def legal_moves(self, pid: int):
        p = self.players[pid - 1]
        if not self.turn_cards:
            return list(p.cards)

        lead_s = self.first_suit
        suited = [c for c in p.cards if (not is_joker(c)) and suit(c) == lead_s]
        if suited:
            return suited + (["Jo"] if "Jo" in p.cards else [])
        return list(p.cards)

    def play_card(self, pid: int, c: str):
        p = self.players[pid - 1]
        if c not in p.cards:
            return (False, "That card is not in the player's hand.")

        # Turn 1 rule: nobody can play Obverse suit cards
        if self.stage == "play" and self.turn_no == 1:
            if (not is_joker(c)) and suit(c) == self.obverse:
                return (False, "Turn 1: Obverse suit cards cannot be played.")

        if not self.turn_cards:
            # Turn 1 rule: Napoleon cannot lead Joker
            if self.turn_no == 1 and pid == self.napoleon_id and is_joker(c):
                return (False, "Turn 1: Napoleon cannot lead Joker.")

            self.first_card = c
            self.first_suit = self.obverse if is_joker(c) else suit(c)

        if c not in self.legal_moves(pid):
            return (False, "Illegal move (must follow suit if possible).")

        p.cards.remove(c)

        # Reveal Lieut when Lieut card is played
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

        # Face-down display for off-suit
        shown = c
        if self.turn_cards:
            if (not is_joker(c)) and suit(c) != self.first_suit:
                shown = "BACK"
            elif is_joker(self.first_card):
                if (not is_joker(c)) and suit(c) != self.first_suit:
                    shown = "BACK"

        self.turn_cards.append((pid, c))
        self.turn_display.append((pid, shown))
        return (True, "")

    def turn_complete(self):
        return len(self.turn_cards) == 4

    def _pict_cards_in_turn(self):
        pict = {"0", "J", "Q", "K", "A"}
        got = []
        for _, c in self.turn_cards:
            if is_joker(c):
                continue
            if rank(c) in pict:
                got.append(c)
        return got

    def award_turn(self, winner_pid: int):
        got = self._pict_cards_in_turn()
        self.pict_won_count[winner_pid] += len(got)
        self.pict_won_cards[winner_pid].extend(got)

    def judge_turn_winner(self):
        lead = self.first_card
        lead_s = self.first_suit
        trump = self.obverse

        obv_j = f"{trump}J"
        rev_j = f"{reverse_suit(trump)}J"
        shown_map = {pid: shown for pid, shown in self.turn_display}

        def is_face_down(pid: int) -> bool:
            return shown_map.get(pid) == "BACK"

        # hQ (Yoro) is special ONLY when sA (Mighty) appears in the same turn.
        def yoro_is_special_now() -> bool:
            return any(c == SPECIAL_MIGHTY for _, c in self.turn_cards)

        def is_special(c: str) -> bool:
            if c == SPECIAL_MIGHTY:
                return True
            if c == obv_j or c == rev_j:
                return True
            if c == SPECIAL_YORO:
                return yoro_is_special_now()
            return False

        # Joker is treated as having the lead suit for suit-consistency checks.
        def eff_suit_for_sameness(c: str) -> str:
            if is_joker(c):
                return lead_s
            return suit(c)

        any_face_down = any(is_face_down(pid) for pid, _ in self.turn_cards)
        all_same_suit = all(eff_suit_for_sameness(c) == lead_s for _, c in self.turn_cards)

        # "2 rule" activates only from Turn 2+, no face-down cards, and all cards same suit.
        two_rule_active = (self.turn_no >= 2) and (not any_face_down) and all_same_suit

        def normal_strength(c: str) -> int:
            if is_joker(c):
                return 0
            if two_rule_active and rank(c) == "2":
                return 1000
            return card_value_basic(c)

        def base_strength(c: str) -> int:
            # sA (Mighty) is always very strong.
            if c == SPECIAL_MIGHTY:
                return 10000

            # hQ (Yoro) only beats sA when sA is present in this turn.
            if c == SPECIAL_YORO and yoro_is_special_now():
                return 10001

            # Obverse Jack and Reverse Jack are always special.
            if c == obv_j:
                return 9000
            if c == rev_j:
                return 8000

            # Joker-led rule (Turn 2+): Joker wins unless overridden by special.
            if is_joker(lead) and self.turn_no >= 2:
                if is_joker(c):
                    return 6500
                return 100

            # Joker is weak when not leading.
            if is_joker(c):
                return -10

            # hQ falls through here and behaves like a normal queen.
            if suit(c) == trump:
                return 5000 + normal_strength(c)
            if suit(c) == lead_s:
                return 1000 + normal_strength(c)
            return normal_strength(c)

        def strength(pid: int, c: str) -> int:
            s = base_strength(c)
            # Face-down restriction: only special cards or trump may beat face-up cards.
            if is_face_down(pid):
                allowed = is_special(c) or ((not is_joker(c)) and suit(c) == trump)
                if not allowed:
                    s -= 20000
            return s

        strengths = []
        for pid, c in self.turn_cards:
            strengths.append((strength(pid, c), pid))

        strengths.sort(reverse=True, key=lambda x: x[0])
        return strengths[0][1]

    def advance_leader(self, winner_pid: int):
        self.leader_id = winner_pid
        self.turn_cards = []
        self.turn_display = []
        self.first_card = ""
        self.first_suit = ""
        self.turn_no += 1

    def last_shown_for_pid(self, pid: int) -> str:
        for p, shown in reversed(self.turn_display):
            if p == pid:
                return shown
        return ""

    # ----------------------------
    # Team-aware CPU logic (no cheat)
    # - Activates ONLY after roles are revealed (lieut_revealed == True)
    # - Uses only public info: current turn state, revealed roles, own hand
    # ----------------------------

    def _nap_side_ids(self):
        nap = self.napoleon_id
        lie = self.lieut_id if (not self.lieut_in_mount) else None
        s = {nap}
        if self.lieut_revealed and lie is not None:
            s.add(lie)
        return s

    def _side_of(self, pid: int) -> str:
        # Before lieut is revealed, treat everyone as "unknown" (no team play).
        if not self.lieut_revealed:
            return "unknown"
        return "nap" if pid in self._nap_side_ids() else "coal"

    def _pict_set(self):
        return {"0", "J", "Q", "K", "A"}

    def _is_pict(self, c: str) -> bool:
        return (not is_joker(c)) and rank(c) in self._pict_set()

    def _shown_code_for_play(self, c: str) -> str:
        # Determine whether this played card would be shown face-down (BACK) under current turn rules.
        if not self.turn_cards:
            return c  # leader card is shown face-up
        if (not is_joker(c)) and suit(c) != self.first_suit:
            return "BACK"
        if is_joker(self.first_card):
            if (not is_joker(c)) and suit(c) != self.first_suit:
                return "BACK"
        return c

    def _estimate_strength(self, pid: int, c: str, temp_turn_cards, temp_turn_display, lead_card: str, lead_suit: str) -> int:
        # A local version of strength used in judge_turn_winner, but works for partial turns too.
        trump = self.obverse
        obv_j = f"{trump}J"
        rev_j = f"{reverse_suit(trump)}J"
        shown_map = {pp: sh for pp, sh in temp_turn_display}

        def is_face_down(pp: int) -> bool:
            return shown_map.get(pp) == "BACK"

        def yoro_is_special_now() -> bool:
            # hQ becomes special only if sA exists in same turn (based on known played cards so far).
            return any(cc == SPECIAL_MIGHTY for _, cc in temp_turn_cards)

        def is_special(cc: str) -> bool:
            if cc == SPECIAL_MIGHTY:
                return True
            if cc == obv_j or cc == rev_j:
                return True
            if cc == SPECIAL_YORO:
                return yoro_is_special_now()
            return False

        def eff_suit_for_sameness(cc: str) -> str:
            if is_joker(cc):
                return lead_suit
            return suit(cc)

        any_face_down = any(is_face_down(pp) for pp, _ in temp_turn_cards)

        # "2 rule" can only activate if (Turn>=2), no face-down, and all cards are same effective suit.
        # For partial turn, we assume it MAY activate if all currently known cards are consistent.
        all_same_so_far = all(eff_suit_for_sameness(cc) == lead_suit for _, cc in temp_turn_cards)
        two_rule_active = (self.turn_no >= 2) and (not any_face_down) and all_same_so_far

        def normal_strength(cc: str) -> int:
            if is_joker(cc):
                return 0
            if two_rule_active and rank(cc) == "2":
                return 1000
            return card_value_basic(cc)

        def base_strength(cc: str) -> int:
            if cc == SPECIAL_MIGHTY:
                return 10000
            if cc == SPECIAL_YORO and yoro_is_special_now():
                return 10001
            if cc == obv_j:
                return 9000
            if cc == rev_j:
                return 8000

            # Joker-led rule (Turn 2+): Joker wins unless overridden by special.
            if is_joker(lead_card) and self.turn_no >= 2:
                if is_joker(cc):
                    return 6500
                return 100

            if is_joker(cc):
                return -10

            if suit(cc) == trump:
                return 5000 + normal_strength(cc)
            if suit(cc) == lead_suit:
                return 1000 + normal_strength(cc)
            return normal_strength(cc)

        s = base_strength(c)

        # Face-down restriction: only special cards or trump may beat face-up cards.
        if is_face_down(pid):
            allowed = is_special(c) or ((not is_joker(c)) and suit(c) == trump)
            if not allowed:
                s -= 20000
        return s

    def _resource_cost(self, c: str) -> int:
        # Higher = more "valuable" card to spend. We try to save these unless needed to secure pict turns.
        trump = self.obverse
        obv_j = f"{trump}J"
        rev_j = f"{reverse_suit(trump)}J"
        specials = {SPECIAL_MIGHTY, SPECIAL_YORO, obv_j, rev_j}
        pict = self._pict_set()

        if c in specials:
            return 100000
        if is_joker(c):
            return 30000
        if (not is_joker(c)) and suit(c) == trump and rank(c) in pict:
            return 70000 + card_value_basic(c)
        if (not is_joker(c)) and suit(c) == trump:
            return 50000 + card_value_basic(c)
        if (not is_joker(c)) and rank(c) in pict:
            return 20000 + card_value_basic(c)
        return card_value_basic(c)

    def _nap_side_pict_public(self) -> int:
        # Public score view (counts are effectively public in this GUI/log world).
        nap = self.napoleon_id
        lie = self.lieut_id if (self.lieut_revealed and (not self.lieut_in_mount)) else None
        total = self.pict_won_count.get(nap, 0)
        if lie is not None:
            total += self.pict_won_count.get(lie, 0)
        return total

    def cpu_choose(self, pid: int):
        legal = self.legal_moves(pid)

        # Turn 1: nobody can play obverse suit cards
        if self.stage == "play" and self.turn_no == 1:
            filtered = [c for c in legal if is_joker(c) or suit(c) != self.obverse]
            if filtered:
                legal = filtered

        # If roles are NOT revealed yet, keep the old "simple" behavior (no team play).
        if not self.lieut_revealed:
            trump = self.obverse
            obv_j = f"{trump}J"
            rev_j = f"{reverse_suit(trump)}J"
            specials = {SPECIAL_YORO, SPECIAL_MIGHTY, obv_j, rev_j}
            pict = {"0", "J", "Q", "K", "A"}

            def score(c: str) -> int:
                if c in specials:
                    return 100000
                if not is_joker(c) and suit(c) == trump and rank(c) in pict:
                    return 80000 + card_value_basic(c)
                if not is_joker(c) and suit(c) == trump:
                    return 50000 + card_value_basic(c)
                if not is_joker(c) and rank(c) in pict:
                    return 20000 + card_value_basic(c)
                if is_joker(c):
                    # Joker is valuable: low priority unless leading
                    if not self.turn_cards:
                        # Leading: Joker gets moderate score
                        return 15000
                    else:
                        # Following: Joker gets very low score (avoid using)
                        return 500
                return card_value_basic(c)

            legal.sort(key=score, reverse=True)
            return legal[0] if legal else random.choice(self.players[pid - 1].cards)

        # ----------------------------
        # Team-aware behavior (no cheat)
        # ----------------------------
        my_side = self._side_of(pid)

        # If leader for this turn: evaluate lead options.
        if not self.turn_cards:
            best = None
            best_score = -10**18

            for c in legal:
                # Turn 1 restriction: Napoleon cannot lead Joker
                if self.turn_no == 1 and pid == self.napoleon_id and is_joker(c):
                    continue

                lead_card = c
                lead_suit = self.obverse if is_joker(c) else suit(c)

                pict_turn = self._is_pict(c)
                cost = self._resource_cost(c)

                s = 0
                
                # Joker as lead: very valuable, avoid using unless necessary
                if is_joker(c):
                    if pict_turn:
                        # Leading with Joker on pict turn: moderate penalty
                        s -= 25000
                    else:
                        # Leading with Joker on non-pict turn: strong penalty
                        s -= 60000
                
                if pict_turn:
                    # Pict involved: prefer OUR side to win this turn.
                    # But Napoleon side must avoid reaching 20 pict total.
                    if my_side == "nap" and self._nap_side_pict_public() >= 19:
                        s -= 200000
                        s -= cost * 0.5
                    else:
                        s += 80000
                        s += self._estimate_strength(pid, c, [(pid, c)], [(pid, c)], lead_card, lead_suit)
                        s -= cost * 0.7
                else:
                    # No pict: conserve resources.
                    s -= cost * 1.2
                    if (not is_joker(c)) and suit(c) != self.obverse:
                        s += 500

                if s > best_score:
                    best_score = s
                    best = c

            if best is not None:
                return best

            return random.choice(legal) if legal else random.choice(self.players[pid - 1].cards)

        # Not leader: responding within an existing turn.
        lead_card = self.first_card
        lead_suit = self.first_suit

        pict_already = any(self._is_pict(cc) for _, cc in self.turn_cards)

        current_best_strength = -10**18
        current_winner_pid = None
        for pp, cc in self.turn_cards:
            st = self._estimate_strength(pp, cc, list(self.turn_cards), list(self.turn_display), lead_card, lead_suit)
            if st > current_best_strength:
                current_best_strength = st
                current_winner_pid = pp

        # Check if Napoleon is currently winning
        napoleon_winning = (current_winner_pid == self.napoleon_id)
        
        best = None
        best_score = -10**18

        for c in legal:
            shown = self._shown_code_for_play(c)

            temp_cards = list(self.turn_cards) + [(pid, c)]
            temp_disp = list(self.turn_display) + [(pid, shown)]

            my_strength = self._estimate_strength(pid, c, temp_cards, temp_disp, lead_card, lead_suit)
            win_now = my_strength > current_best_strength

            pict_now = pict_already or self._is_pict(c)

            cost = self._resource_cost(c)
            score = 0

            # Lieutenant cooperation: if Napoleon is winning, avoid overtaking unless necessary
            if my_side == "nap" and pid == self.lieut_id and napoleon_winning:
                if win_now:
                    # Penalize overtaking Napoleon unless it's a pict turn and we need to secure it
                    if pict_now and self._nap_side_pict_public() < 19:
                        score += 50000  # Still try to win pict turns
                    else:
                        score -= 150000  # Strong penalty for overtaking Napoleon in non-critical situations
                else:
                    # Reward letting Napoleon win
                    score += 100000
                    score -= cost * 0.3  # Prefer low-cost cards when letting Napoleon win

            if pict_now:
                if my_side == "nap":
                    if self._nap_side_pict_public() >= 19:
                        score += (0 if win_now else 120000)
                        score -= cost * 0.4
                    else:
                        score += (180000 if win_now else -90000)
                        score -= cost * (1.0 if win_now else 0.2)
                else:
                    score += (180000 if win_now else -90000)
                    score -= cost * (1.0 if win_now else 0.2)
            else:
                if win_now:
                    score -= cost * 1.2
                    score += 800
                else:
                    score -= cost * 0.8
                    score += 1200

            if (not is_joker(c)) and suit(c) == lead_suit and (not win_now) and (not pict_now):
                score += 600

            # Joker penalty: very valuable card, avoid using carelessly
            if is_joker(c):
                if not pict_now:
                    # Non-pict turn: strong penalty for using Joker
                    score -= 50000
                elif not win_now:
                    # Pict turn but not winning: still penalize
                    score -= 30000
                elif my_side == "nap" and self._nap_side_pict_public() >= 19:
                    # Napoleon side near 20 pict: avoid using Joker to win
                    score -= 40000
                else:
                    # Winning a pict turn when needed: moderate penalty
                    score -= 10000

            if score > best_score:
                best_score = score
                best = c

        return best if best is not None else (legal[0] if legal else random.choice(self.players[pid - 1].cards))


# ----------------------------
# GUI app
# ----------------------------

class NapoApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Napoleon (GUI playable)")

        self.root.geometry("1400x820")
        self.root.minsize(1200, 720)

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cards_dir = os.path.join(self.base_dir, "Cards")

        self.engine = GameEngine()
        self.img = CardImages(self.cards_dir, scale=0.1)

        self.selected_lieut = None
        self.selected_hand_swap = None
        self.selected_mount_swap = None
        self.selected_play_card = None

        # Keep references
        self.log_images = []
        self.log_windows = []

        # Bidding state (4-player bidding)
        self.bid_started = False
        self.bid_round = 0
        self.bid_current_player = 1
        self.bid_player_status = {}
        self.bid_last_raiser = None
        self.bid_consecutive_passes = 0
        self.bid_player_bids = {}
        self.current_target = 13
        self.bid_suit_code = "s"
        self.best_bid = None  # (target, suit_order, pid, suit)
        self.lbl_bid_players = None

        self._build_ui()
        self._new_game()

    # ---------- UI helpers ----------
    def _clear_frame(self, w):
        for child in w.winfo_children():
            child.destroy()

    def log(self, msg: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", " " + msg + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def log_card(self, prefix: str, shown_code: str, actual_code: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", " " + prefix)
        if shown_code == "BACK":
            img = self.img.back
        else:
            img = self.img.get(actual_code)
        self.txt_log.image_create("end", image=img)
        self.log_images.append(img)
        self.txt_log.insert("end", "\n\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def log_turn_header(self):
        leader = self.engine.leader_id
        n = self.engine.turn_no
        self.log("")
        self.log(f"----- Turn {n} (Leader: P{leader} {self._player_label(leader)}) -----")
        self.log("")

    def _reset_log(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")
        self.log_images.clear()
        self.log_windows.clear()

    # ---------- UI build ----------
    def _build_ui(self):
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.rowconfigure(2, weight=1)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)

        self.var_status = tk.StringVar(
            value="Declaration: - | Turn: 0 | Obverse: - | Target: - | Lieut card: - | Napoleon: -"
        )
        ttk.Label(main, textvariable=self.var_status).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        topbar = ttk.Frame(main)
        topbar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        topbar.columnconfigure(0, weight=1)

        btns = ttk.Frame(topbar)
        btns.grid(row=0, column=1, sticky="e")
        ttk.Button(btns, text="New Game", command=self._new_game).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btns, text="Quit", command=self.root.destroy).grid(row=0, column=1)

        left = ttk.Frame(main)
        left.grid(row=2, column=0, sticky="nsew")
        left.rowconfigure(6, weight=1)
        left.columnconfigure(0, weight=1)

        right = ttk.LabelFrame(main, text="Log", padding=8)
        right.grid(row=2, column=1, sticky="nsew", padx=(10, 0))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.txt_log = tk.Text(right, wrap="word", height=24, state="disabled")
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        self.txt_log.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))

        yscroll = ttk.Scrollbar(right, orient="vertical", command=self.txt_log.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.txt_log.configure(yscrollcommand=yscroll.set)

        self.frm_hand_preview = ttk.LabelFrame(left, text="Your hand (preview)", padding=8)
        self.frm_hand_preview.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.preview_area = ttk.Frame(self.frm_hand_preview)
        self.preview_area.pack(fill="x")

        self.frm_bid = ttk.LabelFrame(left, text="Bidding (4 Players)", padding=8)
        self.frm_bid.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        row = ttk.Frame(self.frm_bid)
        row.pack(fill="x")

        ttk.Label(row, text="Suit (declaration):").pack(side="left")
        self.var_dec_suit_label = tk.StringVar(value="Spade")
        self.cmb_suit = ttk.Combobox(
            row,
            textvariable=self.var_dec_suit_label,
            values=[SUIT_LABEL[s] for s in SUITS],
            width=10,
            state="readonly",
        )
        self.cmb_suit.pack(side="left", padx=(6, 10))

        self.var_bid_status = tk.StringVar(value="Not started.")
        ttk.Label(row, textvariable=self.var_bid_status).pack(side="left", padx=(10, 0))

        row2 = ttk.Frame(self.frm_bid)
        row2.pack(fill="x", pady=(6, 0))
        self.btn_pass = ttk.Button(row2, text="Pass", command=self._bid_pass)
        self.btn_raise = ttk.Button(row2, text="Raise (+1)", command=self._bid_raise)
        self.btn_start = ttk.Button(row2, text="Start Bidding", command=self._bid_start)
        self.btn_pass.pack(side="left", padx=(0, 6))
        self.btn_raise.pack(side="left", padx=(0, 6))
        self.btn_start.pack(side="left")

        # Player status display for 4-player bidding
        row3 = ttk.Frame(self.frm_bid)
        row3.pack(fill="x", pady=(6, 0))
        self.lbl_bid_players = ttk.Label(row3, text="", justify="left")
        self.lbl_bid_players.pack(side="left")

        self.frm_lieut = ttk.LabelFrame(left, text="Lieut selection (Choose an OUTSIDE card)", padding=8)
        self.frm_lieut.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        self.frm_lieut.columnconfigure(0, weight=1)
        ttk.Label(
            self.frm_lieut,
            text="Pick an outside card (not in Napoleon's hand). If it is in Mount, Napoleon is alone.",
        ).grid(row=0, column=0, sticky="w")
        self.lieut_area = ttk.Frame(self.frm_lieut)
        self.lieut_area.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        self.frm_exchange = ttk.LabelFrame(left, text="Exchange (After Lieut selection)", padding=8)
        self.frm_exchange.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        self.frm_exchange.columnconfigure(0, weight=1)
        ex_top = ttk.Frame(self.frm_exchange)
        ex_top.grid(row=0, column=0, sticky="ew")
        ttk.Label(ex_top, text="Select 1 hand card and 1 mount card, then press Swap. Repeat as needed.").pack(
            side="left"
        )
        ttk.Button(ex_top, text="Done Exchange", command=self._done_exchange).pack(side="right", padx=(6, 0))
        self.exchange_area = ttk.Frame(self.frm_exchange)
        self.exchange_area.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        self.frm_play = ttk.LabelFrame(left, text="Play", padding=8)
        self.frm_play.grid(row=4, column=0, sticky="nsew", pady=(0, 8))
        self.frm_play.columnconfigure(0, weight=1)

        play_top = ttk.Frame(self.frm_play)
        play_top.grid(row=0, column=0, sticky="ew")
        ttk.Label(play_top, text="Select a card in your hand, then press Play.").pack(side="left")
        ttk.Button(play_top, text="Play", command=self._play_selected).pack(side="right")

        self.play_hand_area = ttk.Frame(self.frm_play)
        self.play_hand_area.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        self.frm_credit = ttk.Frame(left)
        self.frm_credit.grid(row=5, column=0, sticky="ew")
        created = datetime.date.today().isoformat()
        ttk.Label(self.frm_credit, text=f"Created by Takashi Fujiwara and IBM Bob on {created}").pack(
            anchor="w", pady=(6, 0)
        )

    # ---------- status ----------
    def _update_status_bar(self):
        if self.engine.declaration:
            dec = f"{SUIT_LABEL.get(self.engine.obverse,'-')} {self.engine.target}"
        else:
            dec = "-"

        turn = self.engine.turn_no
        obv = SUIT_LABEL.get(self.engine.obverse, "-") if self.engine.obverse else "-"
        tgt = self.engine.target if self.engine.target else "-"
        lie = self.engine.lieut_card if self.engine.lieut_card else "-"
        nap = f"Player {self.engine.napoleon_id}" if self.engine.napoleon_id else "-"

        self.var_status.set(
            f"Declaration: {dec} | Turn: {turn} | Obverse: {obv} | Target: {tgt} | Lieut card: {lie} | Napoleon: {nap}"
        )

    # ---------- labels ----------
    def _cpu_index(self, pid: int) -> int:
        return pid - 1

    def _player_label(self, pid: int) -> str:
        if pid == 1:
            return "Human"
        p = self.engine.players[pid - 1]
        if pid == self.engine.napoleon_id:
            return "Napo"
        if p.revealed_role:
            return p.role.capitalize()
        return f"CPU#{self._cpu_index(pid)}"

    # ---------- stage management ----------
    def _set_stage_visibility(self):
        st = self.engine.stage

        def show(frame, cond: bool):
            if cond:
                frame.grid()
            else:
                frame.grid_remove()

        show(self.frm_bid, st == "bid")
        show(self.frm_lieut, st == "lieut")
        show(self.frm_exchange, st == "exchange")
        show(self.frm_play, st == "play")
        
        # Update bidding UI when entering bid stage
        if st == "bid" and self.bid_started:
            self._update_bid_ui()

    # ---------- hand preview ----------
    def _build_hand_preview(self):
        self._clear_frame(self.preview_area)
        hp = self.engine.human()
        cards = sort_cards(hp.cards)

        cols = 12
        for idx, c in enumerate(cards):
            r = idx // cols
            col = idx % cols
            img = self.img.get(c)
            lbl = ttk.Label(self.preview_area, image=img)
            lbl.image = img
            lbl.grid(row=r, column=col, padx=2, pady=2)

    # ---------- bidding (4-player) ----------
    def _bid_reset_state(self):
        self.bid_started = False
        self.bid_round = 0
        self.bid_current_player = 1
        self.bid_player_status = {1: "active", 2: "active", 3: "active", 4: "active"}
        self.bid_last_raiser = None
        self.bid_consecutive_passes = 0
        self.bid_player_bids = {1: [], 2: [], 3: [], 4: []}
        self.current_target = 13
        self.best_bid = None
        self.bid_suit_code = "s"
        self.var_bid_status.set("Not started.")
        if self.lbl_bid_players:
            self.lbl_bid_players.config(text="")

    def _bid_start(self):
        if self.bid_started:
            return
        label = self.var_dec_suit_label.get()
        self.bid_suit_code = SUIT_LABEL_INV.get(label, "s")

        self.bid_started = True
        self.bid_round = 1
        self.bid_current_player = 1
        self.bid_player_status = {1: "active", 2: "active", 3: "active", 4: "active"}
        self.bid_last_raiser = None
        self.bid_consecutive_passes = 0
        self.current_target = 13
        self.best_bid = None

        self.log("Bidding started (4 players). Max target is 16.")
        self.log(f"Suit for bidding: {label}")
        self.log("Any player can start declaring based on their hand strength...")
        
        self.var_bid_status.set(f"Round {self.bid_round} | Target: {self.current_target} (max 16)")
        self._update_bid_ui()
        
        # Check if any CPU wants to declare first based on hand strength
        self.root.after(500, self._check_initial_declarations)

    def _check_initial_declarations(self):
        """Check if any player wants to make initial declaration based on hand strength"""
        # Evaluate all players' hands and determine who might declare
        declaration_candidates = []
        
        # Check CPU players (2, 3, 4)
        for pid in [2, 3, 4]:
            player = self.engine.players[pid - 1]
            hand = player.cards
            strength = self._evaluate_hand_for_declaration(hand)
            
            # Add randomness: even with strong hand, might not declare immediately
            if strength:
                # Random chance to declare based on hand strength
                declare_probability = random.random()
                if declare_probability > 0.3:  # 70% chance if hand is strong
                    declaration_candidates.append(pid)
        
        # If any CPU wants to declare, pick one randomly
        if declaration_candidates:
            declaring_cpu = random.choice(declaration_candidates)
            self.log(f"Player {declaring_cpu} (CPU) evaluates hand and decides to declare first!")
            self.root.after(800, lambda: self._cpu_make_initial_declaration(declaring_cpu))
        else:
            # No CPU declares, Human can decide
            self.log("CPUs evaluate their hands. Human's turn to decide.")
            self._update_bid_ui()
    
    def _cpu_make_initial_declaration(self, pid: int):
        """CPU makes the initial declaration"""
        self.bid_last_raiser = pid
        self.bid_consecutive_passes = 0
        self.best_bid = (self.current_target, SUIT_ORDER[self.bid_suit_code], pid, self.bid_suit_code)
        self.bid_player_bids[pid].append((self.current_target, self.bid_suit_code))
        self.log(f"Player {pid} (CPU) declares {SUIT_LABEL[self.bid_suit_code]} {self.current_target}.")
        
        # Reset all players to active
        self.bid_player_status = {1: "active", 2: "active", 3: "active", 4: "active"}
        
        # Now start the bidding rounds with player 1
        self.bid_current_player = 1
        self._update_bid_ui()

    def _bid_raise(self):
        if not self.bid_started:
            messagebox.showerror("Error", "Start bidding first.")
            return
        if self.bid_current_player != 1:
            messagebox.showerror("Error", "Not your turn.")
            return
        if self.current_target >= 16:
            messagebox.showerror("Error", "Target is already at max (16).")
            return

        # If this is the first declaration (no one has raised yet)
        if self.bid_last_raiser is None:
            # Initial declaration at target 13
            self.bid_last_raiser = 1
            self.bid_consecutive_passes = 0
            self.best_bid = (self.current_target, SUIT_ORDER[self.bid_suit_code], 1, self.bid_suit_code)
            self.bid_player_bids[1].append((self.current_target, self.bid_suit_code))
            self.log(f"Player 1 (Human) declares {SUIT_LABEL[self.bid_suit_code]} {self.current_target}.")
        else:
            # Raise existing bid
            self.current_target += 1
            self.bid_last_raiser = 1
            self.bid_consecutive_passes = 0
            self.best_bid = (self.current_target, SUIT_ORDER[self.bid_suit_code], 1, self.bid_suit_code)
            self.bid_player_bids[1].append((self.current_target, self.bid_suit_code))
            self.log(f"Player 1 (Human) raises to {SUIT_LABEL[self.bid_suit_code]} {self.current_target}.")
        
        # Reset all players to active when someone raises
        self.bid_player_status = {1: "active", 2: "active", 3: "active", 4: "active"}
        
        self._advance_bid_turn()

    def _bid_pass(self):
        if not self.bid_started:
            messagebox.showerror("Error", "Start bidding first.")
            return
        if self.bid_current_player != 1:
            messagebox.showerror("Error", "Not your turn.")
            return

        self.bid_player_status[1] = "passed_this_round"
        self.bid_consecutive_passes += 1
        self.log("Player 1 (Human) passes.")
        self._advance_bid_turn()

    def _cpu_bid_turn(self, pid: int):
        """CPU (pid=2,3,4) bidding decision"""
        # CPU decision logic
        do_raise = self._cpu_should_raise(pid)
        
        if do_raise and self.current_target < 16:
            # If this is the first declaration (no one has raised yet)
            if self.bid_last_raiser is None:
                # Initial declaration at target 13
                self.bid_last_raiser = pid
                self.bid_consecutive_passes = 0
                self.best_bid = (self.current_target, SUIT_ORDER[self.bid_suit_code], pid, self.bid_suit_code)
                self.bid_player_bids[pid].append((self.current_target, self.bid_suit_code))
                self.log(f"Player {pid} (CPU) declares {SUIT_LABEL[self.bid_suit_code]} {self.current_target}.")
            else:
                # Raise existing bid
                self.current_target += 1
                self.bid_last_raiser = pid
                self.bid_consecutive_passes = 0
                self.best_bid = (self.current_target, SUIT_ORDER[self.bid_suit_code], pid, self.bid_suit_code)
                self.bid_player_bids[pid].append((self.current_target, self.bid_suit_code))
                self.log(f"Player {pid} (CPU) raises to {SUIT_LABEL[self.bid_suit_code]} {self.current_target}.")
            
            # Reset all players to active when someone raises
            self.bid_player_status = {1: "active", 2: "active", 3: "active", 4: "active"}
        else:
            self.bid_player_status[pid] = "passed_this_round"
            self.bid_consecutive_passes += 1
            self.log(f"Player {pid} (CPU) passes.")
        
        self._advance_bid_turn()

    def _cpu_should_raise(self, pid: int) -> bool:
        """Determine if CPU should raise based on hand strength"""
        player = self.engine.players[pid - 1]
        hand = player.cards
        
        # If no one has declared yet, evaluate if hand is strong enough to declare
        if self.bid_last_raiser is None:
            has_strength = self._evaluate_hand_for_declaration(hand)
            # Add randomness: even with strong hand, might not declare
            if has_strength:
                return random.random() > 0.4  # 60% chance to declare if strong
            else:
                return random.random() > 0.85  # 15% chance to declare if weak (bluff)
        
        # If someone has declared, decide whether to raise based on hand strength
        hand_strength = self._evaluate_hand_strength_score(hand)
        
        # Calculate raise probability based on hand strength and current target
        base_probability = 0.0
        
        if hand_strength >= 10:  # Very strong hand
            base_probability = 0.7
        elif hand_strength >= 7:  # Strong hand
            base_probability = 0.5
        elif hand_strength >= 5:  # Medium hand
            base_probability = 0.3
        else:  # Weak hand
            base_probability = 0.1
        
        # Decrease probability as target increases
        target_penalty = (self.current_target - 13) * 0.15
        final_probability = max(0.05, base_probability - target_penalty)
        
        return random.random() < final_probability
    
    def _evaluate_hand_for_declaration(self, hand) -> bool:
        """Evaluate if hand is strong enough to make initial declaration"""
        # Count strong cards
        strong_count = 0
        pict_count = 0
        
        for c in hand:
            if is_joker(c):
                strong_count += 3
                continue
            
            r = rank(c)
            s = suit(c)
            
            # Count picture cards
            if r in ["0", "J", "Q", "K", "A"]:
                pict_count += 1
            
            # Special cards
            if c == SPECIAL_MIGHTY:  # Spade A
                strong_count += 3
            elif c == SPECIAL_YORO:  # Heart Q
                strong_count += 2
            elif r == "A":
                strong_count += 2
            elif r == "K":
                strong_count += 1
            elif r == "Q":
                strong_count += 1
        
        # Decision threshold: need at least 6 strong points or 8+ pict cards
        return strong_count >= 6 or pict_count >= 8
    
    def _evaluate_hand_strength_score(self, hand) -> int:
        """Calculate numeric hand strength score for bidding decisions"""
        score = 0
        pict_count = 0
        
        for c in hand:
            if is_joker(c):
                score += 3
                pict_count += 1
                continue
            
            r = rank(c)
            s = suit(c)
            
            # Count picture cards
            if r in ["0", "J", "Q", "K", "A"]:
                pict_count += 1
            
            # Special cards
            if c == SPECIAL_MIGHTY:  # Spade A
                score += 3
            elif c == SPECIAL_YORO:  # Heart Q
                score += 2
            elif r == "A":
                score += 2
            elif r == "K":
                score += 1
            elif r == "Q":
                score += 1
            elif r == "J":
                score += 0.5
            elif r == "0":
                score += 0.5
        
        # Bonus for having many picture cards
        if pict_count >= 10:
            score += 2
        elif pict_count >= 8:
            score += 1
        
        return int(score)

    def _advance_bid_turn(self):
        """Advance to next player's turn"""
        # Check end conditions first
        if self._check_bid_end():
            return
        
        # Move to next player (always cycle through all 4 players)
        start_player = self.bid_current_player
        self.bid_current_player = (self.bid_current_player % 4) + 1
        
        # Update round counter when returning to P1
        if self.bid_current_player <= start_player:
            self.bid_round += 1
        
        # Update UI
        self.var_bid_status.set(f"Round {self.bid_round} | Target: {self.current_target} (max 16)")
        self._update_bid_ui()
        
        # Execute next turn
        if self.bid_current_player == 1:
            # Human's turn: wait for UI input
            pass
        else:
            # CPU's turn: auto-execute after delay
            self.root.after(800, lambda: self._cpu_bid_turn(self.bid_current_player))

    def _update_bid_ui(self):
        """Update bidding UI to reflect current state"""
        if not self.lbl_bid_players:
            return
        
        status_lines = [f"Round {self.bid_round} | Current: Player {self.bid_current_player}"]
        player_status = []
        for pid in range(1, 5):
            status = self.bid_player_status[pid]
            marker = "→" if pid == self.bid_current_player else " "
            player_name = "Human" if pid == 1 else f"CPU{pid-1}"
            # Display status: ACTIVE or PASSED (this round)
            display_status = "ACTIVE" if status == "active" else "PASSED"
            player_status.append(f"{marker}P{pid}({player_name}): {display_status}")
        status_lines.append(" | ".join(player_status))
        
        self.lbl_bid_players.config(text="\n".join(status_lines))
        
        # Enable/disable buttons based on current player
        is_human_turn = (self.bid_current_player == 1)
        can_raise = is_human_turn and self.current_target < 16
        can_pass = is_human_turn
        
        self.btn_raise.config(state="normal" if can_raise else "disabled")
        self.btn_pass.config(state="normal" if can_pass else "disabled")

    def _check_bid_end(self) -> bool:
        """Check if bidding should end"""
        # Condition 1: 3 consecutive passes (and someone has raised)
        if self.bid_consecutive_passes >= 3 and self.bid_last_raiser is not None:
            self._finalize_bidding()
            return True
        
        # Condition 2: Max target reached
        if self.current_target >= 16:
            self._finalize_bidding()
            return True
        
        # Condition 3: All 4 players passed without anyone declaring (first round)
        if self.bid_consecutive_passes >= 4 and self.bid_last_raiser is None:
            self.log("All players passed. Restarting bidding round...")
            # Reset for another round
            self.bid_consecutive_passes = 0
            self.bid_player_status = {1: "active", 2: "active", 3: "active", 4: "active"}
            self.bid_round += 1
            return False
        
        return False

    def _finalize_bidding(self):
        # Compatibility wrapper: keep this name stable for callbacks.
        return self._finalize_bidding_impl()

    def _finalize_bidding_impl(self):
        # Decide winner from best_bid; if no raises, default to Human 13 with selected suit.
        if self.best_bid is None:
            self.engine.napoleon_id = 1
            self.engine.obverse = self.bid_suit_code
            self.engine.target = 13
        else:
            t, so, pid, s = self.best_bid
            self.engine.napoleon_id = pid
            self.engine.obverse = s
            self.engine.target = t

        self.engine.declaration = f"{self.engine.obverse}{self.engine.target}"

        # Reset roles: only Napoleon is revealed now.
        for p in self.engine.players:
            p.role = "unknown"
            p.revealed_role = False
        nap = self.engine.players[self.engine.napoleon_id - 1]
        nap.role = "napoleon"
        nap.revealed_role = True

        self.log(
            f"Bidding resolved: Declaration={SUIT_LABEL[self.engine.obverse]} {self.engine.target}, "
            f"Napoleon=Player {self.engine.napoleon_id}"
        )

        # Move next stage.
        if self.engine.napoleon_id == 1:
            self.engine.stage = "lieut"
            self.log("Step 2: Select Lieut card (outside card).")
            self._build_lieut_candidates()
        else:
            # CPU Napoleon: auto lieut + exchange, then start play.
            self.engine.stage = "play"
            self._cpu_auto_lieut_and_exchange()
            self.engine.turn_no = 1
            self.engine.leader_id = self.engine.napoleon_id
            self.log("CPU is Napoleon. Lieut selection and exchange were automated. Play starts now.")
            self._build_play_hand()
            if self.engine.leader_id != 1:
                self._cpu_loop()

        self._update_status_bar()
        self._set_stage_visibility()

    # ---------- CPU Napoleon: lieut + exchange ----------
    def _cpu_auto_lieut_and_exchange(self):
        nap = self.engine.players[self.engine.napoleon_id - 1]
        trump = self.engine.obverse
        obv_j = f"{trump}J"
        rev_j = f"{reverse_suit(trump)}J"
        pict_ranks = {"0", "J", "Q", "K", "A"}
        specials = {SPECIAL_MIGHTY, SPECIAL_YORO, obv_j, rev_j}

        def is_pict(c: str) -> bool:
            return (not is_joker(c)) and (rank(c) in pict_ranks)

        def rv(c: str) -> int:
            return card_value_basic(c)

        def is_trump(c: str) -> bool:
            return (not is_joker(c)) and suit(c) == trump

        def strong_card_value(c: str) -> int:
            if c in specials:
                return 200000
            if is_pict(c) and is_trump(c):
                return 120000 + rv(c)
            if is_trump(c):
                return 80000 + rv(c)
            if is_pict(c):
                return 30000 + rv(c)
            return rv(c)

        holder = {}
        for c in self.engine.mount:
            holder[c] = None
        for p in self.engine.players:
            if p.id == self.engine.napoleon_id:
                continue
            for c in p.cards:
                holder[c] = p.id

        outside = [c for c in build_deck_4p() if c not in nap.cards]
        best_c = None
        best_score = -10**18
        for c in outside:
            sc = strong_card_value(c)
            if c in self.engine.mount:
                sc -= 60000
            if holder.get(c) is not None:
                sc += 5000
            if is_trump(c) and rv(c) >= 11:
                sc += 8000
            if sc > best_score:
                best_score = sc
                best_c = c

        self.engine.lieut_card = best_c if best_c else random.choice(outside)

        if self.engine.lieut_card in self.engine.mount:
            self.engine.lieut_in_mount = True
            self.engine.lieut_id = None
        else:
            self.engine.lieut_in_mount = False
            self.engine.lieut_id = holder.get(self.engine.lieut_card)

        def keep_value(c: str) -> int:
            if c in specials:
                return 150000
            if is_pict(c) and is_trump(c):
                return 90000 + rv(c)
            if is_trump(c):
                return 60000 + rv(c)
            if is_pict(c):
                return 20000 + rv(c)
            if is_joker(c):
                return 1000
            # Prioritize keeping 2s in hand (useful for strategic play)
            if not is_joker(c) and rank(c) == "2":
                return 15000 + rv(c)
            return rv(c)

        def two_synergy_score(hand_cards) -> int:
            counts = {"s": 0, "h": 0, "d": 0, "c": 0}
            for c in hand_cards:
                if is_joker(c):
                    continue
                counts[suit(c)] += 1
            dominant_s = max(counts, key=lambda k: counts[k])
            dom = counts[dominant_s]
            score = dom * 1200
            if dominant_s == trump:
                score += dom * 900
            spread = sum(1 for k in counts if counts[k] > 0)
            score -= spread * 500
            return score

        def hand_total_score(cards) -> int:
            return sum(keep_value(x) for x in cards) + two_synergy_score(cards)

        for _ in range(5):
            best_delta = 0
            best_out = None
            best_in = None
            current_score = hand_total_score(nap.cards)

            for out_c in nap.cards:
                if out_c in specials:
                    continue
                for in_c in self.engine.mount:
                    new_hand = list(nap.cards)
                    new_hand.remove(out_c)
                    new_hand.append(in_c)
                    delta = hand_total_score(new_hand) - current_score
                    if delta > best_delta:
                        best_delta = delta
                        best_out = out_c
                        best_in = in_c

            if best_delta <= 0 or best_out is None or best_in is None:
                break

            nap.cards.remove(best_out)
            self.engine.mount.remove(best_in)
            nap.cards.append(best_in)
            self.engine.mount.append(best_out)

        nap.cards = sort_cards(nap.cards)
        self.engine.mount = sort_cards(self.engine.mount)

    # ---------- new game ----------
    def _new_game(self):
        if not os.path.isdir(self.cards_dir):
            messagebox.showerror("Error", f'Cards folder not found: "{self.cards_dir}"')
            return

        self.engine.new_game()
        self.selected_lieut = None
        self.selected_hand_swap = None
        self.selected_mount_swap = None
        self.selected_play_card = None

        self._bid_reset_state()
        self._reset_log()
        self.log("New game started.")
        self.log("Step 1: Select suit and start bidding.")

        self._build_hand_preview()
        self._clear_frame(self.lieut_area)
        self._clear_frame(self.exchange_area)
        self._build_play_hand()

        self._update_status_bar()
        self._set_stage_visibility()

    # ---------- lieut selection ----------
    def _build_lieut_candidates(self):
        self._clear_frame(self.lieut_area)
        if self.engine.napoleon_id != 1:
            return

        nap = self.engine.players[self.engine.napoleon_id - 1]
        candidates = [c for c in build_deck_4p() if c not in nap.cards]
        candidates = sort_cards(candidates)

        cols = 12
        for idx, c in enumerate(candidates):
            r = idx // cols
            col = idx % cols
            img = self.img.get(c)

            lbl = tk.Label(self.lieut_area, image=img, bd=1, relief="flat")
            lbl.image = img
            lbl.grid(row=r, column=col, padx=2, pady=2)

            def on_click(_e, card=c, w=lbl):
                self.selected_lieut = card
                for child in self.lieut_area.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(relief="flat", bd=1)
                w.configure(relief="solid", bd=2)

            lbl.bind("<Button-1>", on_click)

        row = ttk.Frame(self.lieut_area)
        row.grid(row=(len(candidates) // cols) + 1, column=0, columnspan=cols, sticky="ew", pady=(6, 0))
        ttk.Button(row, text="Confirm Lieut Card", command=self._confirm_lieut).pack(side="right")

    def _confirm_lieut(self):
        if not self.selected_lieut:
            messagebox.showerror("Error", "Select a Lieut card first.")
            return

        ok, msg = self.engine.set_lieut_card(self.selected_lieut)
        if not ok:
            messagebox.showerror("Error", msg)
            return

        if self.engine.lieut_in_mount:
            self.log(f"Lieut card selected: {self.engine.lieut_card} (in Mount). Napoleon is alone.")
        else:
            self.log(
                f"Lieut card selected: {self.engine.lieut_card} (held by a player). "
                f"Roles remain hidden until it is played."
            )

        self.log("Step 3: Exchange (swap hand card <-> mount card).")
        self._build_exchange_panels()

        self._update_status_bar()
        self._set_stage_visibility()

    # ---------- exchange ----------
    def _build_exchange_panels(self):
        self._clear_frame(self.exchange_area)
        if self.engine.stage not in ["exchange", "play"]:
            return
        if self.engine.napoleon_id != 1:
            return

        hp = self.engine.human()

        hand_frame = ttk.LabelFrame(self.exchange_area, text="Your hand (select 1)", padding=6)
        hand_frame.grid(row=0, column=0, sticky="ew")
        cols = 12
        for idx, c in enumerate(sort_cards(hp.cards)):
            r = idx // cols
            col = idx % cols
            img = self.img.get(c)

            lbl = tk.Label(hand_frame, image=img, bd=1, relief="flat")
            lbl.image = img
            lbl.grid(row=r, column=col, padx=2, pady=2)

            def on_click(_e, card=c, w=lbl):
                self.selected_hand_swap = card
                for child in hand_frame.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(relief="flat", bd=1)
                w.configure(relief="solid", bd=2)

            lbl.bind("<Button-1>", on_click)

        mount_frame = ttk.LabelFrame(self.exchange_area, text="Mount (select 1)", padding=6)
        mount_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for idx, c in enumerate(sort_cards(self.engine.mount)):
            img = self.img.get(c)

            lbl = tk.Label(mount_frame, image=img, bd=1, relief="flat")
            lbl.image = img
            lbl.grid(row=0, column=idx, padx=2, pady=2)

            def on_click(_e, card=c, w=lbl):
                self.selected_mount_swap = card
                for child in mount_frame.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(relief="flat", bd=1)
                w.configure(relief="solid", bd=2)

            lbl.bind("<Button-1>", on_click)

        action = ttk.Frame(self.exchange_area)
        action.grid(row=2, column=0, sticky="e", pady=(8, 0))
        ttk.Button(action, text="Swap", command=self._do_swap).pack(side="right")

    def _do_swap(self):
        if not self.selected_hand_swap or not self.selected_mount_swap:
            messagebox.showerror("Error", "Select BOTH a hand card and a mount card, then press Swap.")
            return
        ok, msg = self.engine.do_swap(self.selected_hand_swap, self.selected_mount_swap)
        if not ok:
            messagebox.showerror("Error", msg)
            return

        self.log(f"Swapped: hand {self.selected_hand_swap} <-> mount {self.selected_mount_swap}")
        self.selected_hand_swap = None
        self.selected_mount_swap = None

        self._build_exchange_panels()
        self._build_hand_preview()

    def _done_exchange(self):
        if self.engine.stage != "exchange":
            return
        self.engine.finish_exchange()
        self.log("Exchange finished. Play starts.")

        self._build_play_hand()
        self._build_hand_preview()
        self._update_status_bar()
        self._set_stage_visibility()

        if self.engine.leader_id != 1:
            self._cpu_loop()

    # ---------- play ----------
    def _build_play_hand(self):
        self._clear_frame(self.play_hand_area)
        if self.engine.stage != "play":
            return

        hp = self.engine.human()
        cards = sort_cards(hp.cards)

        cols = 12
        for idx, c in enumerate(cards):
            r = idx // cols
            col = idx % cols
            img = self.img.get(c)

            lbl = tk.Label(self.play_hand_area, image=img, bd=1, relief="flat")
            lbl.image = img
            lbl.grid(row=r, column=col, padx=2, pady=2)

            def on_click(_e, card=c, w=lbl):
                self.selected_play_card = card
                for child in self.play_hand_area.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(relief="flat", bd=1)
                w.configure(relief="solid", bd=2)

            lbl.bind("<Button-1>", on_click)

    def _play_selected(self):
        if self.engine.stage != "play":
            return
        if not self.selected_play_card:
            messagebox.showerror("Error", "Select a card to play.")
            return

        leader = self.engine.leader_id
        order = [((leader - 1 + i) % 4) + 1 for i in range(4)]
        already = {p for p, _ in self.engine.turn_cards}
        pending = [x for x in order if x not in already]
        if not pending or pending[0] != 1:
            messagebox.showerror("Error", "It is not your turn.")
            return

        card = self.selected_play_card

        if not self.engine.turn_cards:
            self.log_turn_header()

        ok, msg = self.engine.play_card(1, card)
        if not ok:
            messagebox.showerror("Error", msg)
            return

        shown = self.engine.last_shown_for_pid(1) or card
        label = self._player_label(1)
        self.log_card(f"P1 ({label}) plays: ", shown, card)

        self.selected_play_card = None
        self._build_play_hand()
        self._build_hand_preview()
        self._update_status_bar()

        self._cpu_loop()

    def _cpu_loop(self):
        while self.engine.stage == "play" and not self.engine.turn_complete():
            leader = self.engine.leader_id
            order = [((leader - 1 + i) % 4) + 1 for i in range(4)]
            already = {p for p, _ in self.engine.turn_cards}
            pending = [x for x in order if x not in already]
            if not pending:
                break

            pid = pending[0]
            if pid == 1:
                break

            card = self.engine.cpu_choose(pid)

            if not self.engine.turn_cards:
                self.log_turn_header()

            ok, msg = self.engine.play_card(pid, card)
            if not ok:
                legal = self.engine.legal_moves(pid)
                if self.engine.turn_no == 1:
                    legal2 = [c for c in legal if is_joker(c) or suit(c) != self.engine.obverse]
                    if legal2:
                        legal = legal2
                if not legal:
                    break
                card = random.choice(legal)
                self.engine.play_card(pid, card)

            shown = self.engine.last_shown_for_pid(pid) or card
            label = self._player_label(pid)
            self.log_card(f"P{pid} ({label}) plays: ", shown, card)

            self._update_status_bar()

        if self.engine.turn_complete():
            self._end_turn()

    def _log_turn_summary_row(self, winner_pid: int):
        self.txt_log.configure(state="normal")

        outer = tk.Frame(self.txt_log, bg="#e6e6e6")
        inner = tk.Frame(outer, bg="#e6e6e6")
        inner.pack(anchor="w", padx=10, pady=8)

        for idx, (pid, actual) in enumerate(self.engine.turn_cards):
            label_txt = f"P{pid} ({self._player_label(pid)})"
            if pid == winner_pid:
                label_txt += " (WIN)"
            lbl = tk.Label(inner, text=label_txt, bg="#e6e6e6")
            lbl.grid(row=0, column=idx, padx=8, pady=(0, 4), sticky="w")

            img = self.img.get(actual)
            card_lbl = tk.Label(inner, image=img, bg="#e6e6e6")
            card_lbl.image = img
            card_lbl.grid(row=1, column=idx, padx=8, pady=(0, 2))
            self.log_images.append(img)

        self.txt_log.window_create("end", window=outer)
        self.log_windows.append(outer)
        self.txt_log.insert("end", "\n\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _end_turn(self):
        winner = self.engine.judge_turn_winner()
        self.engine.award_turn(winner)
        self.log(f"Winner: Player {winner}")

        self._log_turn_summary_row(winner)

        self.engine.advance_leader(winner)

        self._build_play_hand()
        self._build_hand_preview()
        self._update_status_bar()
        
        # Force scroll to bottom after turn ends
        self.txt_log.see("end")
        self.txt_log.yview_moveto(1.0)
        self.root.update_idletasks()

        if all(len(p.cards) == 0 for p in self.engine.players):
            self._final_result()
            self.engine.stage = "done"
            self._set_stage_visibility()
            return

        if self.engine.leader_id != 1:
            self._cpu_loop()

    # ---------- FINAL RESULT helpers ----------
    def log_pict_cards_row(self, cards):
        self.txt_log.configure(state="normal")

        if not cards:
            self.txt_log.insert("end", " (none)\n\n")
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
            return

        max_per_row = 10
        rows = (len(cards) + max_per_row - 1) // max_per_row

        outer = ttk.Frame(self.txt_log)
        for r in range(rows):
            rowf = ttk.Frame(outer)
            rowf.grid(row=r, column=0, sticky="w", pady=(0, 4))
            start = r * max_per_row
            end = min(len(cards), start + max_per_row)
            for i, c in enumerate(cards[start:end]):
                img = self.img.get(c)
                lbl = ttk.Label(rowf, image=img)
                lbl.image = img
                lbl.grid(row=0, column=i, padx=4, pady=2)
                self.log_images.append(img)

        self.txt_log.window_create("end", window=outer)
        self.log_windows.append(outer)

        self.txt_log.insert("end", "\n\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def log_nap_side_pict_block(self, nap_pid: int, nap_cards, lie_pid, lie_cards):
        self.txt_log.configure(state="normal")

        outer = ttk.Frame(self.txt_log)
        bg = tk.Frame(outer, bg="#e6e6e6")
        bg.grid(row=0, column=0, sticky="ew")

        def add_row(row_idx: int, title: str, cards):
            rowf = tk.Frame(bg, bg="#e6e6e6")
            rowf.grid(row=row_idx, column=0, sticky="w", padx=10, pady=(8 if row_idx == 0 else 14, 8))

            ttl = tk.Label(rowf, text=title, bg="#e6e6e6")
            ttl.grid(row=0, column=0, sticky="w")

            cards_frame = tk.Frame(rowf, bg="#e6e6e6")
            cards_frame.grid(row=1, column=0, sticky="w", pady=(4, 0))

            if not cards:
                tk.Label(cards_frame, text="(none)", bg="#e6e6e6").grid(row=0, column=0, sticky="w")
                return

            max_per_row = 10
            for i, c in enumerate(cards):
                rr = i // max_per_row
                cc = i % max_per_row
                img = self.img.get(c)
                lbl = tk.Label(cards_frame, image=img, bg="#e6e6e6")
                lbl.image = img
                lbl.grid(row=rr, column=cc, padx=6, pady=3)
                self.log_images.append(img)

        add_row(0, f"Napoleon (P{nap_pid}) pict: {len(nap_cards)}", nap_cards)
        if lie_pid is None:
            add_row(1, "Lieut pict: 0", [])
        else:
            add_row(1, f"Lieut (P{lie_pid}) pict: {len(lie_cards)}", lie_cards)

        self.txt_log.window_create("end", window=outer)
        self.log_windows.append(outer)

        self.txt_log.insert("end", "\n\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _final_result(self):
        nap = self.engine.napoleon_id
        lie = self.engine.lieut_id if (not self.engine.lieut_in_mount) else None

        nap_side = {nap}
        if self.engine.lieut_revealed and lie is not None:
            nap_side.add(lie)
        coal_side = {1, 2, 3, 4} - nap_side

        coal_pict = sum(self.engine.pict_won_count[pid] for pid in coal_side)
        coal_cards = []
        for pid in sorted(coal_side):
            coal_cards.extend(self.engine.pict_won_cards[pid])
        coal_cards = sort_cards(coal_cards)

        napoleon_cards = sort_cards(list(self.engine.pict_won_cards[nap]))
        lieut_cards = sort_cards(list(self.engine.pict_won_cards[lie])) if (lie is not None) else []
        nap_pict = len(napoleon_cards) + len(lieut_cards)

        required = int(self.engine.target)

        self.log("")
        self.log("===== FINAL RESULT =====")
        self.log("")
        self.log(f"Target: {required} (pict cards: 10/J/Q/K/A)")
        self.log(f"Napoleon side pict: {nap_pict}")
        self.log_nap_side_pict_block(nap, napoleon_cards, lie, lieut_cards)

        self.log(f"Coalition side pict: {coal_pict}")
        self.log_pict_cards_row(coal_cards)

        # Mount cards
        self.log("")
        self.log("Mount cards:")
        mount_cards = sort_cards(list(self.engine.mount))
        self.log_pict_cards_row(mount_cards)

        # Insert ONE blank line before final line, and make it bold
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", "\n")

        # New rule: taking all 20 pict cards is an automatic loss for Napoleon side.
        if nap_pict == 20:
            self.txt_log.insert("end", " Napoleon side LOSES!!\n", "bold")
        else:
            if nap_pict >= required:
                self.txt_log.insert("end", " Napoleon side WINS!!\n", "bold")
            else:
                self.txt_log.insert("end", " Napoleon side LOSES!!\n", "bold")

        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    # ---------- run ----------
    def run(self):
        self.root.mainloop()


def main():
    app = NapoApp()
    app.run()


if __name__ == "__main__":
    main()

