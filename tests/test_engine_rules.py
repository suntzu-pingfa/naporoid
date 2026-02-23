import unittest

from engine import (
    GameEngine,
    Player,
    SPECIAL_MIGHTY,
    SPECIAL_YORO,
)


class EngineRuleTests(unittest.TestCase):
    def _fresh_engine(self):
        e = GameEngine()
        e.players = [Player(1, True), Player(2, False), Player(3, False), Player(4, False)]
        return e

    def test_human_exchange_flow(self):
        e = self._fresh_engine()
        e.stage = "bid"
        e.napoleon_id = 1
        ok, _ = e.set_declaration("s", 13)
        self.assertTrue(ok)
        self.assertEqual(e.stage, "lieut")

        e.players[0].cards = ["s2", "h3", "d4", "c5"]
        e.players[1].cards = ["hA", "dA", "cA", "s3"]
        e.players[2].cards = ["h2", "d2", "c2", "s4"]
        e.players[3].cards = ["h4", "d5", "c6", "s5"]
        e.mount = ["hK", "dK", "cK", "sK", "hQ"]

        ok, _ = e.set_lieut_card("hA")
        self.assertTrue(ok)
        self.assertEqual(e.stage, "exchange")

        ok, _ = e.do_swap("s2", "hK")
        self.assertTrue(ok)
        self.assertIn("hK", e.players[0].cards)
        self.assertIn("s2", e.mount)

        ok, _ = e.do_swap("h3", "dK")
        self.assertTrue(ok)
        self.assertIn("dK", e.players[0].cards)
        self.assertIn("h3", e.mount)

    def test_swap_rejects_invalid_conditions(self):
        e = self._fresh_engine()
        e.napoleon_id = 1
        e.players[0].cards = ["s2", "h3", "d4", "c5"]
        e.mount = ["hK", "dK", "cK", "sK", "hQ"]

        # Not in exchange stage -> swap must fail.
        e.stage = "lieut"
        ok, msg = e.do_swap("s2", "hK")
        self.assertFalse(ok)
        self.assertIn("Not in exchange stage", msg)

        # Enter exchange and validate card existence checks.
        e.stage = "exchange"
        ok, msg = e.do_swap("sA", "hK")
        self.assertFalse(ok)
        self.assertIn("not in Napoleon hand", msg)

        ok, msg = e.do_swap("s2", "hA")
        self.assertFalse(ok)
        self.assertIn("not in Mount", msg)

        # Valid pair still succeeds.
        ok, msg = e.do_swap("s2", "hK")
        self.assertTrue(ok)
        self.assertEqual(msg, "OK")

    def test_lieut_card_must_be_outside_napoleon_hand(self):
        e = self._fresh_engine()
        e.stage = "lieut"
        e.napoleon_id = 1
        e.players[0].cards = ["sA", "h3", "d4", "c5"]
        e.mount = ["hK", "dK", "cK", "sK", "hQ"]

        ok, msg = e.set_lieut_card("sA")
        self.assertFalse(ok)
        self.assertIn("outside Napoleon", msg)

        ok, _ = e.set_lieut_card("hK")
        self.assertTrue(ok)
        self.assertEqual(e.stage, "exchange")

    def test_turn1_napoleon_cannot_lead_joker(self):
        e = self._fresh_engine()
        e.stage = "play"
        e.turn_no = 1
        e.napoleon_id = 2
        e.obverse = "h"
        e.leader_id = 2
        e.players[1].cards = ["Jo", "s3", "d4"]

        ok, msg = e.play_card(2, "Jo")
        self.assertFalse(ok)
        self.assertIn("Napoleon cannot lead Joker", msg)

    def test_turn1_obverse_card_forbidden(self):
        e = self._fresh_engine()
        e.stage = "play"
        e.turn_no = 1
        e.napoleon_id = 1
        e.obverse = "d"
        e.leader_id = 1
        e.players[0].cards = ["dA", "s3", "h4"]

        ok, msg = e.play_card(1, "dA")
        self.assertFalse(ok)
        self.assertIn("Obverse suit", msg)

    def test_sA_optional_when_spade_led(self):
        e = self._fresh_engine()
        e.stage = "play"
        e.turn_no = 2
        e.obverse = "h"
        e.turn_cards = [(2, "s9")]
        e.turn_display = [(2, "s9")]
        e.first_card = "s9"
        e.first_suit = "s"
        e.players[0].cards = [SPECIAL_MIGHTY, "h3", "d4"]

        legal = e.legal_moves(1)
        self.assertIn(SPECIAL_MIGHTY, legal)
        self.assertIn("h3", legal)
        self.assertIn("d4", legal)

    def test_two_rule_only_under_strict_conditions(self):
        e = self._fresh_engine()
        e.stage = "play"
        e.turn_no = 3
        e.obverse = "h"
        e.first_card = "s8"
        e.first_suit = "s"
        e.turn_cards = [(1, "s8"), (2, "s2"), (3, "sK"), (4, "s9")]
        e.turn_display = [(1, "s8"), (2, "s2"), (3, "sK"), (4, "s9")]
        winner, win_card, two_active = e.judge_turn_winner()
        self.assertTrue(two_active)
        self.assertEqual(win_card, "s2")
        self.assertEqual(winner, 2)

        # If special card exists, 2-rule must be disabled.
        e.turn_cards = [(1, "s8"), (2, "s2"), (3, SPECIAL_MIGHTY), (4, "s9")]
        e.turn_display = [(1, "s8"), (2, "s2"), (3, SPECIAL_MIGHTY), (4, "s9")]
        winner, win_card, two_active = e.judge_turn_winner()
        self.assertFalse(two_active)
        self.assertEqual(win_card, SPECIAL_MIGHTY)

        # If first card is Joker, 2-rule must be disabled.
        e.first_card = "Jo"
        e.first_suit = "s"
        e.turn_cards = [(1, "Jo"), (2, "s2"), (3, "sK"), (4, "s9")]
        e.turn_display = [(1, "Jo"), (2, "s2"), (3, "sK"), (4, "s9")]
        winner, win_card, two_active = e.judge_turn_winner()
        self.assertFalse(two_active)

        # If sA and hQ are both in turn, 2-rule must be disabled.
        e.first_card = "s8"
        e.first_suit = "s"
        e.turn_cards = [(1, "s8"), (2, "s2"), (3, SPECIAL_MIGHTY), (4, SPECIAL_YORO)]
        e.turn_display = [(1, "s8"), (2, "s2"), (3, SPECIAL_MIGHTY), (4, SPECIAL_YORO)]
        winner, win_card, two_active = e.judge_turn_winner()
        self.assertFalse(two_active)

    def test_joker_wins_only_under_strict_condition(self):
        e = self._fresh_engine()
        e.stage = "play"
        e.turn_no = 3
        e.obverse = "s"

        # Joker led + all non-joker suits same + no special => Joker wins.
        e.first_card = "Jo"
        e.first_suit = "s"
        e.turn_cards = [(1, "Jo"), (2, "s2"), (3, "sK"), (4, "s9")]
        e.turn_display = [(1, "Jo"), (2, "s2"), (3, "sK"), (4, "s9")]
        winner, win_card, _ = e.judge_turn_winner()
        self.assertEqual(win_card, "Jo")
        self.assertEqual(winner, 1)

        # If a special exists, Joker must not win.
        e.turn_cards = [(1, "Jo"), (2, SPECIAL_MIGHTY), (3, "sK"), (4, "s9")]
        e.turn_display = [(1, "Jo"), (2, SPECIAL_MIGHTY), (3, "sK"), (4, "s9")]
        winner, win_card, _ = e.judge_turn_winner()
        self.assertEqual(win_card, SPECIAL_MIGHTY)
        self.assertEqual(winner, 2)

    def test_joker_is_weaker_than_two_when_condition_not_met(self):
        e = self._fresh_engine()
        e.stage = "play"
        e.turn_no = 3
        e.obverse = "s"

        # Joker led but non-joker suits are not all same -> Joker loses (weaker than 2).
        e.first_card = "Jo"
        e.first_suit = "s"
        e.turn_cards = [(1, "Jo"), (2, "s2"), (3, "h3"), (4, "s4")]
        e.turn_display = [(1, "Jo"), (2, "s2"), (3, "h3"), (4, "s4")]
        winner, win_card, _ = e.judge_turn_winner()
        self.assertNotEqual(win_card, "Jo")


if __name__ == "__main__":
    unittest.main()
