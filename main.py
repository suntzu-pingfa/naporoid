import os
import random
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.utils import platform
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner

from engine import (
    FACE_DOWN,
    SPECIAL_MIGHTY,
    SPECIAL_YORO,
    SUIT_LABEL,
    SUIT_LABEL_INV,
    SUITS,
    GameEngine,
    build_deck_4p,
    card_to_filename,
    is_joker,
    rank,
    reverse_suit,
    sort_cards,
    suit,
)


CARD_DIR = os.path.join(os.path.dirname(__file__), "Cards")


def card_img_path(c: str) -> str:
    if c == FACE_DOWN:
        p = os.path.join(CARD_DIR, "back.png")
        return p if os.path.exists(p) else ""
    fn = card_to_filename(c)
    p = os.path.join(CARD_DIR, fn)
    return p if os.path.exists(p) else ""


def pretty_card(c: str) -> str:
    if not c:
        return "-"
    if c == "Jo":
        return "Joker"
    r = rank(c)
    if r == "0":
        r = "10"
    return f"{SUIT_LABEL[suit(c)]}-{r}"


def make_card_code(suit_label: str, rank_label: str) -> str:
    if suit_label == "Joker":
        return "Jo"
    s = SUIT_LABEL_INV.get(suit_label, "s")
    r = "0" if rank_label == "10" else rank_label
    return f"{s}{r}"


class CardButton(Button):
    card_code = StringProperty("")
    wdp = NumericProperty(dp(42))
    hdp = NumericProperty(dp(63))

    def __init__(self, card_code: str, on_tap, selected: bool = False, wdp=None, hdp=None, **kwargs):
        super().__init__(**kwargs)
        self.card_code = card_code
        self._on_tap = on_tap
        self.size_hint = (None, None)
        if wdp is not None:
            self.wdp = wdp
        if hdp is not None:
            self.hdp = hdp
        self.size = (self.wdp, self.hdp)
        self.border = (0, 0, 0, 0)
        self.background_color = (0.72, 0.85, 1.0, 1.0) if selected else (1, 1, 1, 1)
        self.text = ""
        self.always_release = True
        self.reload_source()

    def on_press(self):
        if self._on_tap:
            self._on_tap(self.card_code)

    def reload_source(self):
        p = card_img_path(self.card_code)
        if p:
            self.background_normal = p
            self.background_down = p
            self.background_disabled_normal = p
            self.background_disabled_down = p
        else:
            self.background_normal = ""
            self.background_down = ""
            self.background_disabled_normal = ""
            self.background_disabled_down = ""
            self.text = pretty_card(self.card_code)


class TableCell(BoxLayout):
    def __init__(self, pid: int, card_code: str, wdp, hdp, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2), **kwargs)
        self.size_hint = (1, 1)

        lab = Label(text=f"P{pid}", size_hint_y=None, height=dp(16), halign="center", valign="middle")
        lab.bind(size=lambda *_: setattr(lab, "text_size", lab.size))
        self.add_widget(lab)

        slot = AnchorLayout(anchor_x="center", anchor_y="center")
        if card_code:
            slot.add_widget(CardButton(card_code, None, wdp=wdp, hdp=hdp))
        else:
            slot.add_widget(Button(text="-", disabled=True, size_hint=(None, None), size=(wdp, hdp)))
        self.add_widget(slot)


class Root(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(2), spacing=dp(2), **kwargs)

        self.engine = GameEngine()

        self.selected_hand = None
        self.selected_mount = None

        self.turn_snapshot = []
        self.turn_reveal_until = 0.0

        self.final_result_due_at = 0.0
        self.final_result_logged = False
        self.final_result_scheduled = False

        self.cpu_running = False
        self.cpu_event = None

        self.hand_w = dp(32)
        self.hand_h = dp(48)
        self.mount_w = dp(28)
        self.mount_h = dp(42)
        self.table_w = dp(28)
        self.table_h = dp(42)
        self.label_h = dp(16)
        self.status_h = dp(18)
        self.panel_h = dp(32)

        self.status = Label(text="", size_hint_y=None, height=self.status_h, halign="left", valign="middle")
        self.status.bind(size=lambda *_: setattr(self.status, "text_size", self.status.size))
        self.add_widget(self.status)

        self.bid_panel = GridLayout(cols=3, spacing=dp(3), size_hint_y=None, height=self.panel_h)
        self.spinner_suit = Spinner(text="Spade", values=("Spade", "Heart", "Diamond", "Club"))
        self.spinner_target = Spinner(text="13", values=tuple(str(i) for i in range(12, 21)))
        self.btn_declare = Button(text="Declare")
        self.btn_declare.bind(on_release=self.on_declare)
        self.bid_panel.add_widget(self.spinner_suit)
        self.bid_panel.add_widget(self.spinner_target)
        self.bid_panel.add_widget(self.btn_declare)
        self.add_widget(self.bid_panel)

        self.lieut_panel = GridLayout(cols=4, spacing=dp(3), size_hint_y=None, height=0, opacity=0, disabled=True)
        self.spinner_lieut_suit = Spinner(text="Spade", values=("Spade", "Heart", "Diamond", "Club", "Joker"))
        self.spinner_lieut_rank = Spinner(text="A", values=("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"))
        self.btn_set_lieut = Button(text="Set Lieut")
        self.btn_set_lieut.bind(on_release=self.on_set_lieut)
        self.btn_auto_lieut = Button(text="Auto")
        self.btn_auto_lieut.bind(on_release=self.on_auto_lieut)
        self.lieut_panel.add_widget(self.spinner_lieut_suit)
        self.lieut_panel.add_widget(self.spinner_lieut_rank)
        self.lieut_panel.add_widget(self.btn_set_lieut)
        self.lieut_panel.add_widget(self.btn_auto_lieut)
        self.add_widget(self.lieut_panel)

        self.ctrl = GridLayout(cols=5, spacing=dp(3), size_hint_y=None, height=self.panel_h)
        self.btn_swap = Button(text="Swap", disabled=True)
        self.btn_swap.bind(on_release=self.on_swap)
        self.btn_finish_exchange = Button(text="FinishEx", disabled=True)
        self.btn_finish_exchange.bind(on_release=self.on_finish_exchange)
        self.btn_play = Button(text="Play", disabled=True)
        self.btn_play.bind(on_release=self.on_play)
        self.btn_cpu = Button(text="CPU")
        self.btn_cpu.bind(on_release=self.on_cpu_step)
        self.btn_new = Button(text="New")
        self.btn_new.bind(on_release=self.on_new_game)
        for w in (self.btn_swap, self.btn_finish_exchange, self.btn_play, self.btn_cpu, self.btn_new):
            self.ctrl.add_widget(w)
        self.add_widget(self.ctrl)

        self.table_label = Label(text="Table", size_hint_y=None, height=self.label_h, halign="left", valign="middle")
        self.table_label.bind(size=lambda *_: setattr(self.table_label, "text_size", self.table_label.size))
        self.add_widget(self.table_label)
        self.table = GridLayout(cols=4, spacing=dp(2), size_hint_y=None, height=dp(62))
        self.add_widget(self.table)

        self.mount_head = BoxLayout(orientation="horizontal", spacing=dp(4), size_hint_y=None, height=self.label_h)
        self.mount_label = Label(text="Mount(hidden)", size_hint=(0.28, None), height=self.label_h, halign="left", valign="middle")
        self.mount_label.bind(size=lambda *_: setattr(self.mount_label, "text_size", self.mount_label.size))
        self.log = Label(text="", size_hint=(0.72, None), height=self.label_h, halign="left", valign="middle")
        self.log.bind(size=lambda *_: setattr(self.log, "text_size", self.log.size))
        self.mount_head.add_widget(self.mount_label)
        self.mount_head.add_widget(self.log)
        self.add_widget(self.mount_head)
        self.mount_grid = GridLayout(cols=5, spacing=dp(2), size_hint_y=None, height=dp(50))
        self.add_widget(self.mount_grid)

        self.hand_label = Label(text="Your Hand", size_hint_y=None, height=self.label_h, halign="left", valign="middle")
        self.hand_label.bind(size=lambda *_: setattr(self.hand_label, "text_size", self.hand_label.size))
        self.add_widget(self.hand_label)
        self.hand_grid = GridLayout(cols=12, spacing=dp(2), size_hint_y=None, height=dp(56))
        self.add_widget(self.hand_grid)

        self.result_panel = BoxLayout(orientation="vertical", spacing=dp(2), size_hint=(1, None), height=0, opacity=0, disabled=True)

        self.result_head = BoxLayout(orientation="horizontal", spacing=0, size_hint_y=None, height=self.label_h)
        self.result_nap_label = Label(text="Napoleon+Lieut", size_hint=(1.0, None), height=self.label_h, halign="left", valign="middle", markup=True)
        self.result_nap_label.bind(size=lambda *_: setattr(self.result_nap_label, "text_size", self.result_nap_label.size))
        self.result_outcome_label = Label(text="", size_hint=(0.0, None), width=0, height=self.label_h, halign="left", valign="middle")
        self.result_outcome_label.bind(size=lambda *_: setattr(self.result_outcome_label, "text_size", self.result_outcome_label.size))
        self.result_head.add_widget(self.result_nap_label)
        self.result_head.add_widget(self.result_outcome_label)
        self.result_panel.add_widget(self.result_head)

        self.result_nap_scroll = ScrollView(do_scroll_x=True, do_scroll_y=False, size_hint=(1, None), height=dp(58))
        self.result_nap_grid = GridLayout(rows=1, spacing=dp(2), size_hint_x=None, height=dp(50))
        self.result_nap_grid.bind(minimum_width=self.result_nap_grid.setter("width"))
        self.result_nap_scroll.add_widget(self.result_nap_grid)
        self.result_panel.add_widget(self.result_nap_scroll)

        self.result_coal_label = Label(text="Coalition", size_hint_y=None, height=self.label_h, halign="left", valign="middle")
        self.result_coal_label.bind(size=lambda *_: setattr(self.result_coal_label, "text_size", self.result_coal_label.size))
        self.result_panel.add_widget(self.result_coal_label)

        self.result_coal_scroll = ScrollView(do_scroll_x=True, do_scroll_y=False, size_hint=(1, None), height=dp(58))
        self.result_coal_grid = GridLayout(rows=1, spacing=dp(2), size_hint_x=None, height=dp(50))
        self.result_coal_grid.bind(minimum_width=self.result_coal_grid.setter("width"))
        self.result_coal_scroll.add_widget(self.result_coal_grid)
        self.result_panel.add_widget(self.result_coal_scroll)

        self.result_footer = AnchorLayout(anchor_x="right", anchor_y="center", size_hint_y=None, height=self.panel_h)
        self.btn_result_new = Button(text="New Game", size_hint=(None, None), size=(dp(112), self.panel_h))
        self.btn_result_new.bind(on_release=self.on_new_game)
        self.result_footer.add_widget(self.btn_result_new)
        self.result_panel.add_widget(self.result_footer)

        self.add_widget(self.result_panel)

        Window.bind(size=self.on_window_resize)
        self.on_new_game()

    def _card_code_from_touch(self, grid: GridLayout, touch):
        for child in grid.children:
            if not hasattr(child, "card_code"):
                continue
            if child.collide_point(*touch.pos):
                return child.card_code
        return None

    def on_touch_down(self, touch):
        # Fallback for environments where card Button press is not dispatched reliably.
        if self.engine.stage in {"exchange", "play"}:
            c_hand = self._card_code_from_touch(self.hand_grid, touch)
            if c_hand is not None:
                self._on_hand_tap(c_hand)
                return True
        if self.engine.stage == "exchange":
            c_mount = self._card_code_from_touch(self.mount_grid, touch)
            if c_mount is not None:
                self._on_mount_tap(c_mount)
                return True

        return super().on_touch_down(touch)

    def on_window_resize(self, *_):
        self.compute_card_sizes()
        self.refresh()

    def compute_card_sizes(self):
        w = Window.width
        h = Window.height

        # Scale controls to fit mobile-like landscape screens.
        self.status_h = max(dp(14), min(dp(18), h * 0.045))
        self.label_h = max(dp(12), min(dp(16), h * 0.04))
        self.panel_h = max(dp(28), min(dp(34), h * 0.085))

        # Width-bound card size (12 cards on one row).
        gap = dp(2)
        usable_w = max(dp(300), w - dp(10))
        cw_by_w = (usable_w - gap * 11) / 12.0
        ch_by_w = cw_by_w * 1.5

        # Height-bound cap to avoid vertical overflow.
        fixed_h = (
            self.status_h
            + self.panel_h
            + self.panel_h
            + self.label_h
            + self.label_h
            + self.label_h
            + dp(26)
        )
        free_h = max(dp(120), h - fixed_h - dp(20))
        hand_h_cap = free_h / 2.8
        ch = min(ch_by_w, hand_h_cap)
        cw = ch / 1.5
        cw = max(dp(22), min(dp(42), cw))
        ch = cw * 1.5

        self.hand_w = cw
        self.hand_h = ch
        self.mount_w = max(dp(26), cw * 0.9)
        self.mount_h = max(dp(38), ch * 0.9)
        self.table_w = self.mount_w
        self.table_h = self.mount_h

        self.status.height = self.status_h
        self.bid_panel.height = self.panel_h
        self.ctrl.height = self.panel_h
        if not self.lieut_panel.disabled:
            self.lieut_panel.height = self.panel_h

        self.table_label.height = self.label_h
        self.mount_head.height = self.label_h
        self.mount_label.height = self.label_h
        self.log.height = self.label_h
        self.hand_label.height = self.label_h
        self.result_head.height = self.label_h
        self.result_nap_label.height = self.label_h
        self.result_outcome_label.height = self.label_h
        self.result_coal_label.height = self.label_h

        self.table.height = self.table_h + dp(16)
        self.mount_grid.height = self.mount_h + dp(8)
        self.hand_grid.height = self.hand_h + dp(8)

        self.result_nap_grid.height = self.mount_h + dp(8)
        self.result_nap_scroll.height = self.mount_h + dp(12)
        self.result_coal_grid.height = self.mount_h + dp(8)
        self.result_coal_scroll.height = self.mount_h + dp(12)
        self.result_footer.height = self.panel_h
        self.btn_result_new.height = self.panel_h

    def append_log(self, msg: str):
        self.log.text = msg

    def _log_special(self, pid: int, c: str):
        obv = self.engine.obverse
        obv_j = f"{obv}J" if obv else ""
        rev_j = f"{reverse_suit(obv)}J" if obv else ""

        if c == SPECIAL_MIGHTY:
            self.append_log(f"Special: P{pid} played sA")
        elif c == obv_j:
            self.append_log(f"Special: P{pid} played Obverse Jack")
        elif c == rev_j:
            self.append_log(f"Special: P{pid} played Reverse Jack")
        elif c == SPECIAL_YORO:
            self.append_log(f"Special: P{pid} played hQ")

    def next_player_id(self) -> int:
        if self.engine.stage != "play":
            return 1
        if not self.engine.turn_cards:
            return self.engine.leader_id
        return (self.engine.turn_cards[-1][0] % 4) + 1

    def _show_lieut_panel(self, show: bool):
        self.lieut_panel.opacity = 1.0 if show else 0.0
        self.lieut_panel.height = self.panel_h if show else 0
        self.lieut_panel.disabled = not show

    def _show_result_panel(self, show: bool):
        self.result_panel.opacity = 1.0 if show else 0.0
        self.result_panel.height = ((self.mount_h + dp(12)) * 2 + self.label_h * 2 + self.panel_h + dp(10)) if show else 0
        self.result_panel.disabled = not show
        self.btn_result_new.disabled = not show

    def _reset_timers(self):
        self.turn_reveal_until = 0.0
        self.final_result_due_at = 0.0
        self.final_result_logged = False
        self.final_result_scheduled = False

    def _clear_selection(self):
        self.selected_hand = None
        self.selected_mount = None

    def _sync_selection_validity(self):
        hand = self.engine.players[0].cards[:]
        mount = self.engine.mount[:]
        if self.selected_hand not in hand:
            self.selected_hand = None
        if self.selected_mount not in mount:
            self.selected_mount = None

    def _update_buttons(self):
        st = self.engine.stage
        can_swap = st == "exchange" and self.selected_hand is not None and self.selected_mount is not None
        self.btn_swap.disabled = not can_swap
        self.btn_swap.text = "Swap"

        self.btn_finish_exchange.disabled = (st != "exchange")
        self.btn_declare.disabled = (st != "bid")
        self.spinner_suit.disabled = (st != "bid")
        self.spinner_target.disabled = (st != "bid")
        self.btn_play.disabled = not (st == "play" and self.next_player_id() == 1 and time.time() >= self.turn_reveal_until)
        self.btn_new.disabled = (st == "done")
        self.btn_new.opacity = 0.0 if st == "done" else 1.0

        self._show_lieut_panel(st == "lieut" and self.engine.napoleon_id == 1)

    def on_new_game(self, *_):
        self.engine.new_game()
        self.engine.napoleon_id = 1
        self.engine.stage = "bid"

        self.compute_card_sizes()
        self._reset_timers()
        self.turn_snapshot = []
        self._clear_selection()

        self.spinner_suit.text = "Spade"
        self.spinner_target.text = "13"

        if self.cpu_event is not None:
            self.cpu_event.cancel()
            self.cpu_event = None
        self.cpu_running = False

        self.append_log("Game ready. Declare first.")
        self.refresh()

    def on_declare(self, *_):
        if self.engine.stage != "bid":
            self.append_log("Not in bid stage.")
            self.refresh()
            return

        self.engine.napoleon_id = 1
        suit_code = SUIT_LABEL_INV.get(self.spinner_suit.text, "s")
        try:
            target = int(self.spinner_target.text)
        except Exception:
            target = 13

        ok, msg = self.engine.set_declaration(suit_code, target)
        if ok:
            self.append_log(f"Declared: {self.spinner_suit.text} {target}")
        else:
            self.append_log(f"Declare failed: {msg}")
        self.refresh()

    def _auto_lieut_card(self):
        nap = self.engine.players[self.engine.napoleon_id - 1]
        nap_set = set(nap.cards)
        pool = [c for c in build_deck_4p() if c not in nap_set]

        def score(c: str) -> int:
            if c == "Jo":
                return 1000
            r = rank(c)
            rv = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "0": 10, "J": 11, "Q": 12, "K": 13, "A": 14}.get(r, 0)
            bonus = 30 if r in {"A", "K", "Q", "J", "0"} else 0
            return rv + bonus

        pool = sort_cards(pool)
        return max(pool, key=score) if pool else "Jo"

    def on_set_lieut(self, *_):
        if self.engine.stage != "lieut":
            self.append_log("Not in lieut stage.")
            self.refresh()
            return
        c = make_card_code(self.spinner_lieut_suit.text, self.spinner_lieut_rank.text)
        ok, msg = self.engine.set_lieut_card(c)
        if ok:
            self.append_log(f"Lieut set: {pretty_card(c)}")
            self._clear_selection()
        else:
            self.append_log(f"Set Lieut failed: {msg}")
        self.refresh()

    def on_auto_lieut(self, *_):
        if self.engine.stage != "lieut":
            self.append_log("Not in lieut stage.")
            self.refresh()
            return
        c = self._auto_lieut_card()
        ok, msg = self.engine.set_lieut_card(c)
        if ok:
            self.append_log(f"Lieut auto: {pretty_card(c)}")
            self._clear_selection()
        else:
            self.append_log(f"Auto lieut failed: {msg}")
        self.refresh()

    def on_swap(self, *_):
        if self.engine.stage != "exchange":
            self.append_log("Not in exchange stage.")
            self.refresh()
            return
        if self.selected_hand is None or self.selected_mount is None:
            self.append_log("Select 1 hand + 1 mount.")
            self.refresh()
            return

        ok, msg = self.engine.do_swap(self.selected_hand, self.selected_mount)
        if ok:
            self._clear_selection()
            self.append_log("Swapped.")
        else:
            self.append_log(f"Swap failed: {msg}")
        self.refresh()

    def on_finish_exchange(self, *_):
        ok, msg = self.engine.finish_exchange()
        if not ok:
            self.append_log(f"FinishEx failed: {msg}")
            self.refresh()
            return

        self._clear_selection()
        self.append_log("Exchange finished. Play stage entered.")
        self.refresh()

        if self.engine.napoleon_id != 1:
            self.start_cpu_until_human(immediate=True)

    def _play_one(self, pid: int, c: str):
        prev = list(self.engine.turn_cards)
        ok, result = self.engine.play_card(pid, c)
        if not ok:
            return False, result

        self._log_special(pid, c)

        if result.get("turn_complete"):
            self.turn_snapshot = prev + [(pid, c)]
            winner = result.get("winner_id")
            self.append_log(f"Turn complete. Winner: P{winner}")

            if result.get("had_face_down"):
                self.turn_reveal_until = time.time() + 5.0

            if self.engine.stage == "done":
                self.turn_reveal_until = max(self.turn_reveal_until, time.time() + 5.0)
                self._schedule_final_result_after(max(0.0, self.turn_reveal_until - time.time()))
        else:
            self.turn_snapshot = list(self.engine.turn_display)

        return True, result

    def on_play(self, *_):
        if self.engine.stage != "play":
            self.append_log("Not in play stage.")
            self.refresh()
            return
        if time.time() < self.turn_reveal_until:
            self.append_log("Revealing cards... wait.")
            self.refresh()
            return
        if self.next_player_id() != 1:
            self.append_log("Not your turn.")
            self.refresh()
            return
        if self.selected_hand is None:
            self.append_log("Select a hand card.")
            self.refresh()
            return

        ok, res = self._play_one(1, self.selected_hand)
        if not ok:
            self.append_log(f"Illegal: {res}")
            self.refresh()
            return

        self.selected_hand = None
        self.refresh()

        if self.engine.stage == "play":
            self.start_cpu_until_human(immediate=False)

    def _cpu_step(self, _dt):
        self.cpu_event = None

        if not self.cpu_running:
            return
        if self.engine.stage != "play":
            self.cpu_running = False
            self.refresh()
            return

        wait = self.turn_reveal_until - time.time()
        if wait > 0:
            self.cpu_event = Clock.schedule_once(self._cpu_step, min(wait, 0.5))
            return

        pid = self.next_player_id()
        if pid == 1:
            self.cpu_running = False
            self.refresh()
            return

        c = self.engine.cpu_choose(pid)
        if c is None:
            self.cpu_running = False
            self.append_log(f"CPU P{pid} no legal move.")
            self.refresh()
            return

        ok, res = self._play_one(pid, c)
        if not ok:
            self.cpu_running = False
            self.append_log(f"CPU play failed: {res}")
            self.refresh()
            return

        self.refresh()
        if self.engine.stage == "play":
            delay = max(0.2, self.turn_reveal_until - time.time())
            self.cpu_event = Clock.schedule_once(self._cpu_step, delay)
        else:
            self.cpu_running = False

    def start_cpu_until_human(self, immediate: bool):
        if self.cpu_running:
            return
        if self.engine.stage != "play":
            return
        self.cpu_running = True
        delay = 0.0 if immediate else 0.2
        if self.turn_reveal_until > time.time():
            delay = max(delay, self.turn_reveal_until - time.time())
        self.cpu_event = Clock.schedule_once(self._cpu_step, delay)

    def on_cpu_step(self, *_):
        st = self.engine.stage
        if st == "bid":
            self.append_log("Bid stage: declare first.")
            self.refresh()
            return

        if st == "lieut" and self.engine.napoleon_id != 1:
            c = self._auto_lieut_card()
            ok, _ = self.engine.set_lieut_card(c)
            if ok:
                self.append_log("CPU lieut set.")
                self.refresh()
            return

        if st == "exchange" and self.engine.napoleon_id != 1:
            nap = self.engine.players[self.engine.napoleon_id - 1]
            for _ in range(2):
                if not nap.cards or not self.engine.mount:
                    break
                self.engine.do_swap(random.choice(nap.cards), random.choice(self.engine.mount))
            ok, msg = self.engine.finish_exchange()
            self.append_log("CPU exchange done." if ok else f"CPU FinishEx failed: {msg}")
            self.refresh()
            self.start_cpu_until_human(immediate=True)
            return

        if st == "play":
            self.start_cpu_until_human(immediate=True)
            self.refresh()
            return

        if st == "done":
            self.refresh()

    def _schedule_final_result_after(self, delay_sec: float):
        if self.final_result_logged:
            return
        due = time.time() + max(0.0, delay_sec)
        if due <= self.final_result_due_at and self.final_result_scheduled:
            return
        self.final_result_due_at = due
        self.final_result_scheduled = True
        Clock.schedule_once(self._final_result_tick, max(0.1, delay_sec))

    def _final_result_tick(self, _dt):
        self.final_result_scheduled = False
        if self.final_result_logged:
            return
        now = time.time()
        if now < self.final_result_due_at:
            Clock.schedule_once(self._final_result_tick, max(0.1, self.final_result_due_at - now))
            self.final_result_scheduled = True
            return
        self._announce_final_result()
        self.refresh()

    def _announce_final_result(self):
        if self.final_result_logged:
            return
        s = self.engine.score()
        target = s.get("target", 0)
        nap_p = s.get("nap_pict", 0)
        coal_p = s.get("coal_pict", 0)
        if s.get("done"):
            if s.get("nap_win"):
                self.append_log(f"Result: Napoleon WIN ({nap_p}/{target})")
            else:
                self.append_log(f"Result: Coalition WIN ({nap_p}/{target}, coal={coal_p})")
            self.final_result_logged = True

    def _on_hand_tap(self, c: str):
        st = self.engine.stage
        if st == "exchange":
            self.selected_hand = c
            ms = pretty_card(self.selected_mount) if self.selected_mount else "M:-"
            self.append_log(f"Hand selected: {pretty_card(c)}  /  {ms}")
            self.refresh()
            return
        if st == "play":
            self.selected_hand = c
            self.append_log(f"Selected to play: {pretty_card(c)}")
            self.refresh()
            return

    def _on_mount_tap(self, c: str):
        if self.engine.stage != "exchange":
            return
        self.selected_mount = c
        hs = pretty_card(self.selected_hand) if self.selected_hand else "H:-"
        self.append_log(f"Mount selected: {pretty_card(c)}  /  {hs}")
        self.refresh()

    def _render_result_cards(self):
        nap_ids = {self.engine.napoleon_id}
        if self.engine.lieut_revealed and self.engine.lieut_id and not self.engine.lieut_in_mount:
            nap_ids.add(self.engine.lieut_id)
        coal_ids = {1, 2, 3, 4} - nap_ids

        nap_cards = []
        for pid in sorted(nap_ids):
            nap_cards.extend(self.engine.pict_won_cards.get(pid, []))
        coal_cards = []
        for pid in sorted(coal_ids):
            coal_cards.extend(self.engine.pict_won_cards.get(pid, []))

        outcome = ""
        s = self.engine.score()
        if s.get("done"):
            outcome = "[b]Napoleon Wins!![/b]" if s.get("nap_win") else "[b]Napoleon Losses!![/b]"
        self.result_nap_label.text = f"Napoleon+Lieut ({len(nap_cards)}) {outcome}".rstrip()
        self.result_coal_label.text = f"Coalition ({len(coal_cards)})"
        self.result_outcome_label.text = ""

        self.result_nap_grid.clear_widgets()
        for c in nap_cards:
            self.result_nap_grid.add_widget(CardButton(c, None, wdp=self.mount_w, hdp=self.mount_h))

        self.result_coal_grid.clear_widgets()
        for c in coal_cards:
            self.result_coal_grid.add_widget(CardButton(c, None, wdp=self.mount_w, hdp=self.mount_h))

    def refresh(self):
        st = self.engine.stage
        self._sync_selection_validity()

        turn_no = self.engine.turn_no if self.engine.turn_no else 1
        decl = self.engine.declaration if self.engine.declaration else "-"
        lieut = pretty_card(self.engine.lieut_card) if self.engine.lieut_card else "-"
        self.status.text = f"Stage:{st}  Turn:{turn_no}  Decl:{decl}  Lieut:{lieut}"

        self._update_buttons()

        done = st == "done"
        self._show_result_panel(done)

        # Table
        live = list(self.engine.turn_display)
        if live:
            pairs = live
            self.turn_snapshot = live
        else:
            pairs = self.turn_snapshot

        shown = {pid: c for pid, c in pairs}
        self.table.clear_widgets()
        for pid in (1, 2, 3, 4):
            self.table.add_widget(TableCell(pid, shown.get(pid, ""), self.table_w, self.table_h))

        # Mount
        self.mount_grid.clear_widgets()
        if st == "exchange":
            mount = self.engine.mount[:]
            self.mount_label.text = f"Mount({len(mount)})"
            self.mount_label.height = self.label_h
            self.mount_grid.cols = max(1, len(mount))
            for c in mount:
                self.mount_grid.add_widget(
                    CardButton(c, self._on_mount_tap, selected=(self.selected_mount == c), wdp=self.mount_w, hdp=self.mount_h)
                )
        else:
            self.mount_label.text = "Mount(hidden)"
            self.mount_label.height = self.label_h
            self.mount_grid.cols = 5

        # Hand
        self.hand_grid.clear_widgets()
        hand = self.engine.players[0].cards[:]
        self.hand_label.text = f"Your Hand({len(hand)})"
        self.hand_grid.cols = max(1, len(hand))
        for c in hand:
            self.hand_grid.add_widget(
                CardButton(c, self._on_hand_tap, selected=(self.selected_hand == c), wdp=self.hand_w, hdp=self.hand_h)
            )

        # Final stage handling
        if done:
            self._render_result_cards()
            if not self.final_result_logged and self.final_result_due_at == 0.0:
                # Ensure final announcement always occurs after 5s at game end.
                self._schedule_final_result_after(5.0)


class NapoleonApp(App):
    def build(self):
        # Desktop debug window: force phone-like landscape ratio.
        if platform not in {"android", "ios"}:
            Window.size = (736, 414)
        return Root()


if __name__ == "__main__":
    NapoleonApp().run()
