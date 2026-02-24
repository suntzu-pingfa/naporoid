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
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget

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


class FinalResultModal(ModalView):
    def __init__(
        self,
        owner,
        outcome_text,
        target,
        nap_lieut_count,
        nap_cards,
        lieut_cards,
        coalition_cards,
        mount_cards,
        nap_count,
        lieut_count,
        coalition_count,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.owner = owner
        self.size_hint = (0.96, 0.92)
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        self.auto_dismiss = False

        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(6))

        title = Label(
            text=f"[b]{outcome_text}[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="middle",
        )
        title.bind(size=lambda *_: setattr(title, "text_size", title.size))
        root.add_widget(title)

        summary = Label(
            text=f"[b]Target: {target}  Napoleon + Lieut:{nap_lieut_count}[/b]",
            markup=True,
            size_hint_y=None,
            height=dp(22),
            halign="left",
            valign="middle",
        )
        summary.bind(size=lambda *_: setattr(summary, "text_size", summary.size))
        root.add_widget(summary)

        body_scroll = ScrollView(do_scroll_x=False, do_scroll_y=True, size_hint=(1, 1))
        body = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))

        def add_card_row(header_text: str, cards):
            lab = Label(text=header_text, size_hint_y=None, height=dp(18), halign="left", valign="middle")
            lab.bind(size=lambda *_: setattr(lab, "text_size", lab.size))
            body.add_widget(lab)

            # Use wrapped grid rows (no nested horizontal ScrollView) so vertical scrolling works reliably on mobile.
            card_w = owner.mount_w
            cell_w = card_w + dp(3)
            avail_w = max(dp(120), Window.width * 0.90 - dp(24))
            cols = max(1, int(avail_w // cell_w))
            rows = max(1, (len(cards) + cols - 1) // cols)
            grid_h = rows * (owner.mount_h + dp(3))
            grid = GridLayout(cols=cols, spacing=dp(3), size_hint=(1, None), height=grid_h)
            for c in cards:
                grid.add_widget(CardButton(c, None, wdp=owner.mount_w, hdp=owner.mount_h))
            body.add_widget(grid)

        add_card_row(f"Napoleon ({nap_count})  {outcome_text}", nap_cards)
        add_card_row(f"Lieut ({lieut_count})", lieut_cards)
        add_card_row(f"Coalition ({coalition_count})", coalition_cards)
        add_card_row("Mount", mount_cards)
        body_scroll.add_widget(body)
        root.add_widget(body_scroll)

        foot = AnchorLayout(anchor_x="right", anchor_y="center", size_hint_y=None, height=dp(40))
        btn = Button(text="New Game", size_hint=(None, None), size=(dp(120), dp(38)))
        btn.bind(on_release=lambda *_: owner._on_final_modal_new_game(self))
        foot.add_widget(btn)
        root.add_widget(foot)

        self.add_widget(root)


class Root(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=(dp(1), dp(6), dp(1), dp(1)), spacing=dp(0), **kwargs)

        self.engine = GameEngine()

        self.selected_hand = None
        self.selected_mount = None

        self.turn_snapshot = []
        self.turn_reveal_until = 0.0

        self.final_result_due_at = 0.0
        self.final_result_logged = False
        self.final_result_scheduled = False
        self.pending_cpu_bid = None
        self.final_modal = None
        self.pending_hidden_special_msgs = []
        self.pending_lieut_turn_msg = None

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
        self.gap_after_status = Widget(size_hint_y=None, height=dp(2))
        self.add_widget(self.gap_after_status)

        self.bid_wrap = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, None), height=self.panel_h)
        self.bid_panel = BoxLayout(orientation="horizontal", spacing=dp(2), size_hint=(None, 1), width=dp(420))
        self.spinner_suit = Spinner(text="Spade", values=("Spade", "Heart", "Diamond", "Club"), size_hint=(None, 1))
        self.spinner_target = Spinner(text="13", values=("13", "14", "15", "16"), size_hint=(None, 1))
        self.btn_declare = Button(text="Declare", size_hint=(None, 1))
        self.btn_declare.bind(on_release=self.on_declare)
        self._style_action_button(self.btn_declare)
        self.bid_panel.add_widget(self.spinner_suit)
        self.bid_panel.add_widget(self.spinner_target)
        self.bid_panel.add_widget(self.btn_declare)
        self.bid_wrap.add_widget(self.bid_panel)
        self.add_widget(self.bid_wrap)
        self.gap_after_bid = Widget(size_hint_y=None, height=dp(2))
        self.add_widget(self.gap_after_bid)

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

        self.ctrl_wrap = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, None), height=self.panel_h)
        self.ctrl = BoxLayout(orientation="horizontal", spacing=dp(2), size_hint=(None, 1), width=dp(420))
        self.btn_swap = Button(text="Swap", disabled=True, size_hint=(None, 1))
        self.btn_swap.bind(on_release=self.on_swap)
        self._style_action_button(self.btn_swap)
        self.btn_finish_exchange = Button(text="FinishEx", disabled=True, size_hint=(None, 1))
        self.btn_finish_exchange.bind(on_release=self.on_finish_exchange)
        self._style_action_button(self.btn_finish_exchange)
        self.btn_play = Button(text="Play", disabled=True, size_hint=(None, 1))
        self.btn_play.bind(on_release=self.on_play)
        self._style_action_button(self.btn_play)
        self.btn_cpu = Button(text="CPU", size_hint=(None, 1))
        self.btn_cpu.bind(on_release=self.on_cpu_step)
        self._style_action_button(self.btn_cpu)
        self.btn_new = Button(text="New", size_hint=(None, 1))
        self.btn_new.bind(on_release=self.on_new_game)
        self._style_action_button(self.btn_new)
        for w in (self.btn_swap, self.btn_finish_exchange, self.btn_play, self.btn_cpu, self.btn_new):
            self.ctrl.add_widget(w)
        self.ctrl_wrap.add_widget(self.ctrl)
        self.add_widget(self.ctrl_wrap)
        self.gap_after_ctrl = Widget(size_hint_y=None, height=dp(2))
        self.add_widget(self.gap_after_ctrl)

        self.table_gap_top = Widget(size_hint_y=None, height=dp(4))
        self.add_widget(self.table_gap_top)
        self.table_label = Label(text="Table", size_hint_y=None, height=self.label_h, halign="left", valign="middle")
        self.table_label.bind(size=lambda *_: setattr(self.table_label, "text_size", self.table_label.size))
        self.add_widget(self.table_label)
        self.table = GridLayout(cols=4, spacing=dp(2), size_hint_y=None, height=dp(62))
        self.add_widget(self.table)
        self.table_gap_bottom = Widget(size_hint_y=None, height=dp(8))
        self.add_widget(self.table_gap_bottom)

        self.mount_head = BoxLayout(orientation="horizontal", spacing=dp(4), size_hint_y=None, height=self.label_h)
        self.mount_label = Label(text="Mount(hidden)", size_hint=(0.28, None), height=self.label_h, halign="left", valign="middle")
        self.mount_label.bind(size=lambda *_: setattr(self.mount_label, "text_size", self.mount_label.size))
        self.log = Label(text="", size_hint=(0.72, None), height=self.label_h, halign="left", valign="middle", markup=True)
        self.log.bind(size=lambda *_: setattr(self.log, "text_size", self.log.size))
        self.mount_head.add_widget(self.mount_label)
        self.mount_head.add_widget(self.log)
        self.add_widget(self.mount_head)
        self.mount_grid = GridLayout(cols=5, spacing=dp(2), size_hint_y=None, height=dp(50))
        self.add_widget(self.mount_grid)

        self.hand_label = Label(text="Your Hand", size_hint_y=None, height=self.label_h, halign="left", valign="middle")
        self.hand_label.bind(size=lambda *_: setattr(self.hand_label, "text_size", self.hand_label.size))
        self.add_widget(self.hand_label)
        self.hand_gap = Widget(size_hint_y=None, height=dp(2))
        self.add_widget(self.hand_gap)
        self.hand_wrap = AnchorLayout(anchor_x="center", anchor_y="center", size_hint=(1, None), height=dp(56))
        self.hand_grid = GridLayout(cols=12, spacing=dp(2), size_hint=(None, None), height=dp(56), width=dp(360))
        self.hand_wrap.add_widget(self.hand_grid)
        self.add_widget(self.hand_wrap)

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
        self._style_action_button(self.btn_result_new)
        self.result_footer.add_widget(self.btn_result_new)
        self.result_panel.add_widget(self.result_footer)

        self.add_widget(self.result_panel)
        self.bottom_spacer = Widget(size_hint_y=1)
        self.add_widget(self.bottom_spacer)

        Window.bind(size=self.on_window_resize)
        self.on_new_game()

    def _style_action_button(self, btn: Button):
        # Use flat backgrounds so disabled state does not look like strikethrough text.
        btn.background_normal = ""
        btn.background_down = ""
        btn.background_disabled_normal = ""
        btn.background_disabled_down = ""
        btn.background_color = (0.42, 0.42, 0.42, 1.0)
        btn.disabled_color = (0.72, 0.72, 0.72, 1.0)

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
        self.status_h = max(dp(11), min(dp(14), h * 0.035))
        self.label_h = max(dp(10), min(dp(13), h * 0.032))
        self.panel_h = max(dp(22), min(dp(28), h * 0.068))

        # Width-bound card size (12 cards on one row), based on actual inner width.
        gap = dp(2)
        inner_w = max(dp(120), w - self.padding[0] - self.padding[2] - dp(2))
        # Reserve fixed side margins, then derive integer card width from remaining space.
        side_margin = dp(8)
        usable_for_12 = max(dp(120), inner_w - side_margin * 2 - gap * 11)
        cw_by_w = float(int(usable_for_12 / 12.0))
        ch_by_w = cw_by_w * 1.5

        # Height-bound cap to avoid vertical overflow.
        fixed_h = (
            self.status_h
            + self.panel_h
            + self.panel_h
            + self.label_h
            + self.label_h
            + self.label_h
            + dp(28)
        )
        free_h = max(dp(120), h - fixed_h - dp(20))
        # Use more vertical space for cards while keeping everything on screen.
        hand_h_cap = free_h / 2.02
        ch = min(ch_by_w, hand_h_cap)
        cw = ch / 1.5
        # Final hard cap by width so 12 cards never overflow horizontally.
        cw = max(dp(18), min(dp(58), cw, cw_by_w))
        ch = cw * 1.5

        self.hand_w = cw
        self.hand_h = ch
        self.mount_w = max(dp(26), cw * 0.9)
        self.mount_h = max(dp(38), ch * 0.9)
        # Table cards use the same size as hand cards.
        self.table_w = cw
        self.table_h = ch

        self.status.height = self.status_h
        self.bid_wrap.height = self.panel_h
        self.ctrl_wrap.height = self.panel_h
        self.bid_panel.height = self.panel_h
        self.ctrl.height = self.panel_h
        top_gap = max(dp(3), min(dp(10), h * 0.018))
        self.gap_after_status.height = top_gap
        # Keep the gap between upper/lower button rows tight (about same as horizontal spacing).
        self.gap_after_bid.height = dp(2)
        self.gap_after_ctrl.height = top_gap
        # Keep top rows compact and balanced: total width of bid row == total width of control row.
        self.bid_panel.spacing = dp(2)
        self.ctrl.spacing = dp(2)
        hand_gap_x = self.hand_grid.spacing[0] if isinstance(self.hand_grid.spacing, (list, tuple)) else self.hand_grid.spacing
        hand_total = self.hand_w * 12 + hand_gap_x * 11
        # Keep a fixed edge margin so right/left never touch window edges.
        edge_safe = dp(8)
        max_content_w = max(dp(120), inner_w - edge_safe * 2)
        # Match button total width to 12-card hand total (within safe bounds).
        row_total = min(hand_total, max_content_w)
        # Integer width math guarantees total width does not overflow.
        btn_w = int((row_total - self.ctrl.spacing * 4) / 5.0)
        btn_w = max(int(dp(60)), btn_w)
        self.btn_swap.width = btn_w
        self.btn_finish_exchange.width = btn_w
        self.btn_play.width = btn_w
        self.btn_cpu.width = btn_w
        self.btn_new.width = btn_w
        ctrl_total = btn_w * 5 + self.ctrl.spacing * 4
        # Use centered wrapper + fixed row width (same as hand 12 cards).
        self.ctrl.width = ctrl_total
        self.bid_panel.width = ctrl_total
        # Bid row widths: always sum exactly to ctrl_total.
        bid_gap = self.bid_panel.spacing * 2
        content_w = max(int(dp(120)), int(ctrl_total - bid_gap))
        suit_w = int(content_w * 0.30)
        target_w = int(content_w * 0.16)
        # Keep suit/target usable, then give the rest to Declare.
        suit_w = max(int(dp(70)), suit_w)
        target_w = max(int(dp(50)), target_w)
        declare_w = content_w - suit_w - target_w
        if declare_w < int(dp(80)):
            deficit = int(dp(80)) - declare_w
            reduce_suit = min(deficit, max(0, suit_w - int(dp(60))))
            suit_w -= reduce_suit
            deficit -= reduce_suit
            reduce_target = min(deficit, max(0, target_w - int(dp(44))))
            target_w -= reduce_target
            declare_w = content_w - suit_w - target_w
        self.spinner_suit.width = suit_w
        self.spinner_target.width = target_w
        self.btn_declare.width = max(int(dp(72)), declare_w)
        if not self.lieut_panel.disabled:
            self.lieut_panel.height = self.panel_h

        self.table_label.height = self.label_h
        table_top_gap = max(dp(6), min(dp(14), h * 0.024))
        table_bottom_gap = max(dp(14), min(dp(34), h * 0.060))
        self.table_gap_top.height = table_top_gap
        self.table_gap_bottom.height = table_bottom_gap
        self.mount_head.height = self.label_h
        self.mount_label.height = self.label_h
        self.log.height = self.label_h
        self.hand_label.height = self.label_h
        self.hand_gap.height = max(dp(3), min(dp(7), h * 0.010))
        self.result_head.height = self.label_h
        self.result_nap_label.height = self.label_h
        self.result_outcome_label.height = self.label_h
        self.result_coal_label.height = self.label_h

        self.table.height = self.table_h + dp(14)
        self.mount_grid.height = self.mount_h + dp(8)
        self.hand_wrap.height = self.hand_h + dp(8)
        self.hand_grid.height = self.hand_h + dp(8)
        # Hand row uses fixed content width and centered wrapper to avoid clipping.
        # GameEngine stores cards under players[*].cards (no hands dict).
        hand_count = max(1, len(self.engine.players[0].cards))
        hand_total_live = self.hand_w * hand_count + hand_gap_x * max(0, hand_count - 1)
        self.hand_grid.width = hand_total_live

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
            self.append_log("Mighty!")
        elif c == obv_j:
            self.append_log("Oberse Jack!")
        elif c == rev_j:
            self.append_log("Reverse Jack!")
        elif c == SPECIAL_YORO:
            self.append_log("Yoromeki!")

    def _special_msg_for_card(self, c: str):
        obv = self.engine.obverse
        obv_j = f"{obv}J" if obv else ""
        rev_j = f"{reverse_suit(obv)}J" if obv else ""
        if c == SPECIAL_MIGHTY:
            return "Mighty!"
        if c == obv_j:
            return "Oberse Jack!"
        if c == rev_j:
            return "Reverse Jack!"
        if c == SPECIAL_YORO:
            return "Yoromeki!"
        return None

    def _special_msgs_for_turn(self, turn_cards):
        # turn_cards: [(pid, card_code), ...] for the completed turn
        cards = [c for _, c in turn_cards]
        msgs = []
        seen = set()
        for c in cards:
            m = self._special_msg_for_card(c)
            if m and m not in seen:
                msgs.append(m)
                seen.add(m)
        if (SPECIAL_MIGHTY in cards) and (SPECIAL_YORO in cards):
            msgs.append("[b]Yoromeki Hits!!![/b]")
        return msgs

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

    def _dismiss_final_modal(self):
        if self.final_modal is not None:
            try:
                self.final_modal.dismiss()
            except Exception:
                pass
            self.final_modal = None

    def _on_final_modal_new_game(self, modal):
        try:
            modal.dismiss()
        except Exception:
            pass
        self.final_modal = None
        self.on_new_game()

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
        self._dismiss_final_modal()
        self.engine.new_game()
        self.engine.napoleon_id = 1
        self.engine.stage = "bid"

        self.compute_card_sizes()
        self._reset_timers()
        self.turn_snapshot = []
        self._clear_selection()
        self.pending_cpu_bid = None
        self.pending_hidden_special_msgs = []
        self.pending_lieut_turn_msg = None

        self.spinner_suit.text = "Spade"
        self.spinner_target.text = "13"

        if self.cpu_event is not None:
            self.cpu_event.cancel()
            self.cpu_event = None
        self.cpu_running = False

        self.append_log("Game ready. Declare first.")
        self.refresh()

    def _bid_strength_for_suit(self, pid: int, suit_code: str) -> int:
        hand = self.engine.players[pid - 1].cards[:]
        score = 0
        suit_count = 0
        for c in hand:
            if c == "Jo":
                score += 5
                continue
            r = rank(c)
            if suit(c) == suit_code:
                suit_count += 1
                score += 2
                score += {"A": 6, "K": 5, "Q": 4, "J": 3, "0": 2}.get(r, 0)
            elif r in {"A", "K"}:
                score += 1

        if suit_count >= 6:
            score += 3
        elif suit_count >= 5:
            score += 2
        elif suit_count >= 4:
            score += 1
        return score

    def _cpu_best_bid(self, pid: int):
        best = {"pid": pid, "target": 13, "suit": "s", "score": -10**9, "is_human": False}
        for s in SUITS:
            sc = self._bid_strength_for_suit(pid, s)
            if sc > best["score"]:
                best["score"] = sc
                best["suit"] = s

        sc = best["score"]
        if sc >= 29:
            best["target"] = 16
        elif sc >= 23:
            best["target"] = 15
        elif sc >= 17:
            best["target"] = 14
        else:
            best["target"] = 13
        return best

    def _bid_key(self, b: dict):
        suit_power = {"s": 4, "h": 3, "d": 2, "c": 1}.get(b.get("suit", ""), 0)
        # target > suit strength > hand score > human priority
        return (b.get("target", 13), suit_power, b.get("score", 0), 1 if b.get("is_human") else 0)

    def _auto_progress_cpu_napoleon(self):
        if self.engine.stage == "lieut" and self.engine.napoleon_id != 1:
            c = self._auto_lieut_card()
            ok, msg = self.engine.set_lieut_card(c)
            if not ok:
                self.append_log(f"CPU lieut failed: {msg}")
                return
        if self.engine.stage == "exchange" and self.engine.napoleon_id != 1:
            self._cpu_exchange_smart(max_swaps=None)
            ok, msg = self.engine.finish_exchange()
            if not ok:
                self.append_log(f"CPU FinishEx failed: {msg}")
                return
        if self.engine.stage == "play" and self.engine.napoleon_id != 1:
            self.start_cpu_until_human(immediate=True)

    def _cpu_card_exchange_score(self, c: str, suit_counts: dict) -> float:
        # Evaluate card strength from Napoleon-side perspective during exchange.
        obv = self.engine.obverse
        target = max(13, min(16, int(self.engine.target or 13)))
        aggr = target - 13  # 0..3

        obv_j = f"{obv}J" if obv else ""
        rev_j = f"{reverse_suit(obv)}J" if obv else ""

        if c == SPECIAL_MIGHTY:
            return 200.0
        if c == obv_j:
            return 185.0
        if c == rev_j:
            return 178.0
        if c == "Jo":
            return 165.0 + aggr * 3.0
        if c == SPECIAL_YORO:
            return 150.0

        r = rank(c)
        sv = suit(c)
        rank_v = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "0": 10, "J": 11, "Q": 12, "K": 13, "A": 14}.get(r, 0)
        pict_bonus = 22.0 + aggr * 6.0 if r in {"0", "J", "Q", "K", "A"} else 0.0
        obv_bonus = (10.0 + aggr * 2.0) if (obv and sv == obv) else 0.0
        suit_len_bonus = suit_counts.get(sv, 0) * 1.6
        low_offsuit_penalty = -6.0 if (r in {"2", "3", "4", "5", "6"} and (not obv or sv != obv)) else 0.0
        return rank_v + pict_bonus + obv_bonus + suit_len_bonus + low_offsuit_penalty

    def _cpu_exchange_smart(self, max_swaps=None):
        if self.engine.stage != "exchange":
            return 0
        nap = self.engine.players[self.engine.napoleon_id - 1]
        if not nap.cards or not self.engine.mount:
            return 0

        swaps_done = 0
        threshold = 2.5
        # If max_swaps is None, keep swapping until no further improvement.
        if max_swaps is None:
            max_swaps = 64  # safety guard only
        max_swaps = max(0, int(max_swaps))

        while swaps_done < max_swaps:
            if not nap.cards or not self.engine.mount:
                break

            suit_counts = {s: 0 for s in SUITS}
            for hc in nap.cards:
                if hc != "Jo":
                    suit_counts[suit(hc)] += 1

            hand_scores = sorted(
                [(self._cpu_card_exchange_score(hc, suit_counts), hc) for hc in nap.cards],
                key=lambda x: x[0],
            )

            mount_candidates = []
            for mc in self.engine.mount:
                # Keep lieutenant-in-mount semantics stable.
                if self.engine.lieut_in_mount and mc == self.engine.lieut_card:
                    continue
                mount_candidates.append((self._cpu_card_exchange_score(mc, suit_counts), mc))
            mount_scores = sorted(mount_candidates, key=lambda x: x[0], reverse=True)

            if not hand_scores or not mount_scores:
                break

            worst_hand_score, worst_hand = hand_scores[0]
            best_mount_score, best_mount = mount_scores[0]
            if best_mount_score <= worst_hand_score + threshold:
                break

            ok, _ = self.engine.do_swap(worst_hand, best_mount)
            if not ok:
                break
            swaps_done += 1

        return swaps_done

    def _finalize_bid(self, bid: dict):
        self.pending_cpu_bid = None
        self.engine.napoleon_id = bid["pid"]
        ok, msg = self.engine.set_declaration(bid["suit"], bid["target"])
        if not ok:
            self.append_log(f"Declare failed: {msg}")
            return False
        who = "Human" if bid["pid"] == 1 else f"CPU P{bid['pid']}"
        decl_suit = SUIT_LABEL.get(bid["suit"], "Spade")
        self.append_log(f"Bid winner: {who} ({decl_suit} {bid['target']})")
        if bid["pid"] != 1:
            self._auto_progress_cpu_napoleon()
        return True

    def on_declare(self, *_):
        if self.engine.stage != "bid":
            self.append_log("Not in bid stage.")
            self.refresh()
            return

        suit_code = SUIT_LABEL_INV.get(self.spinner_suit.text, "s")
        try:
            target = int(self.spinner_target.text)
        except Exception:
            target = 13
        target = max(13, min(16, target))

        human_bid = {
            "pid": 1,
            "target": target,
            "suit": suit_code,
            "score": self._bid_strength_for_suit(1, suit_code),
            "is_human": True,
        }

        # If a CPU bid is pending, Human may re-declare repeatedly until overtaking.
        if self.pending_cpu_bid is not None:
            cpu_bid = self.pending_cpu_bid
            if self._bid_key(human_bid) >= self._bid_key(cpu_bid):
                self._finalize_bid(human_bid)
            else:
                cpu_suit = SUIT_LABEL.get(cpu_bid["suit"], "Spade")
                self.append_log(
                    f"CPU P{cpu_bid['pid']} still leads ({cpu_suit} {cpu_bid['target']}). "
                    f"Re-declare or press CPU to accept."
                )
            self.refresh()
            return

        bids = [human_bid] + [self._cpu_best_bid(pid) for pid in (2, 3, 4)]
        winner = max(bids, key=self._bid_key)
        if winner["pid"] == 1:
            self._finalize_bid(winner)
            self.refresh()
            return

        # Keep CPU best bid pending; Human can re-declare any number of times.
        cpu_best = max([b for b in bids if b["pid"] != 1], key=self._bid_key)
        self.pending_cpu_bid = cpu_best
        cpu_suit = SUIT_LABEL.get(cpu_best["suit"], "Spade")
        self.append_log(
            f"CPU P{cpu_best['pid']} bids {cpu_suit} {cpu_best['target']}. "
            f"Re-declare or press CPU to accept."
        )
        self.refresh()

    def _auto_lieut_card(self):
        nap = self.engine.players[self.engine.napoleon_id - 1]
        nap_set = set(nap.cards)
        # Strong rule: if Napoleon does not hold sA, always call sA as Lieut.
        if SPECIAL_MIGHTY not in nap_set:
            return SPECIAL_MIGHTY
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
        lieut_revealed_before = bool(getattr(self.engine, "lieut_revealed", False))
        ok, result = self.engine.play_card(pid, c)
        if not ok:
            return False, result

        logs = []

        if (not lieut_revealed_before) and bool(getattr(self.engine, "lieut_revealed", False)):
            lcard = pretty_card(getattr(self.engine, "lieut_card", "") or "")
            lpid = getattr(self.engine, "lieut_id", None)
            if lpid:
                self.pending_lieut_turn_msg = f"Lieut: {lcard} - Player {lpid}!!"

        if result.get("turn_complete"):
            completed_turn = prev + [(pid, c)]
            self.turn_snapshot = completed_turn
            winner = result.get("winner_id")
            if result.get("two_active") and result.get("win_card") and rank(result.get("win_card")) == "2":
                wc = result.get("win_card")
                sname = SUIT_LABEL.get(suit(wc), "Suit")
                logs.append(f"{sname} 2 Wins!")
            else:
                logs.append(f"Turn complete. Winner: P{winner}")

            special_logs = self._special_msgs_for_turn(completed_turn)
            if result.get("had_face_down"):
                self.turn_reveal_until = time.time() + 3.0
                if special_logs:
                    delay = max(0.05, self.turn_reveal_until - time.time())
                    Clock.schedule_once(lambda _dt, msg=" / ".join(special_logs): self.append_log(msg), delay)
            elif special_logs:
                logs.extend(special_logs)

            if self.engine.stage == "done":
                self.turn_reveal_until = max(self.turn_reveal_until, time.time() + 3.0)

            if self.pending_lieut_turn_msg:
                logs.append(self.pending_lieut_turn_msg)
                self.pending_lieut_turn_msg = None
        else:
            self.turn_snapshot = list(self.engine.turn_display)

        if logs:
            self.append_log(" / ".join(logs))

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
            if self.pending_cpu_bid is not None:
                self._finalize_bid(self.pending_cpu_bid)
            else:
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
            self._cpu_exchange_smart(max_swaps=None)
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
            self._open_final_result_modal()

    def _open_final_result_modal(self):
        if self.final_modal is not None:
            return
        nap_id = self.engine.napoleon_id
        lieut_id = self.engine.lieut_id if (self.engine.lieut_revealed and self.engine.lieut_id and not self.engine.lieut_in_mount) else None
        nap_cards = list(self.engine.pict_won_cards.get(nap_id, []))
        lieut_cards = list(self.engine.pict_won_cards.get(lieut_id, [])) if lieut_id is not None else []
        nap_side_ids = {nap_id}
        if lieut_id is not None:
            nap_side_ids.add(lieut_id)
        coalition_cards = []
        for pid in (1, 2, 3, 4):
            if pid in nap_side_ids:
                continue
            coalition_cards.extend(self.engine.pict_won_cards.get(pid, []))
        mount_cards = list(getattr(self.engine, "mount", []))
        s = self.engine.score()
        outcome = "Napoleon Wins!!" if s.get("nap_win") else "Napoleon Loses!!"
        modal = FinalResultModal(
            owner=self,
            outcome_text=outcome,
            target=s.get("target", 0),
            nap_lieut_count=s.get("nap_pict", 0),
            nap_cards=nap_cards,
            lieut_cards=lieut_cards,
            coalition_cards=coalition_cards,
            mount_cards=mount_cards,
            nap_count=len(nap_cards),
            lieut_count=len(lieut_cards),
            coalition_count=len(coalition_cards),
        )
        self.final_modal = modal
        modal.open()

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
            outcome = "[b]Napoleon Wins!![/b]" if s.get("nap_win") else "[b]Napoleon Loses!![/b]"
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
        nap_id = getattr(self.engine, "napoleon_id", 1)
        lieut_pid_text = ""
        if getattr(self.engine, "lieut_revealed", False) and getattr(self.engine, "lieut_id", None):
            lieut_pid_text = f"  Lieut:P{self.engine.lieut_id}"
        self.status.text = f"Stage:{st}  Turn:{turn_no}  Napoleon:P{nap_id}{lieut_pid_text}  Decl:{decl}  Lieut:{lieut}"

        self._update_buttons()

        done = st == "done"
        self._show_result_panel(done)

        # Table: hide during declaration/bid and exchange stages.
        if st in {"bid", "exchange"}:
            self.table_label.opacity = 0.0
            self.table.opacity = 0.0
            self.table.disabled = True
            self.table.clear_widgets()
        else:
            self.table_label.opacity = 1.0
            self.table.opacity = 1.0
            self.table.disabled = False
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
            mount = list(getattr(self.engine, "mount", []))
            self.mount_label.text = f"Mount({len(mount)})"
            self.mount_label.height = self.label_h
            self.mount_grid.height = self.mount_h + dp(8)
            self.mount_grid.opacity = 1.0
            self.mount_grid.disabled = False
            self.mount_grid.cols = max(1, len(mount))
            for c in mount:
                self.mount_grid.add_widget(
                    CardButton(c, self._on_mount_tap, selected=(self.selected_mount == c), wdp=self.mount_w, hdp=self.mount_h)
                )
        else:
            self.mount_label.text = ""
            self.mount_label.height = self.label_h
            self.mount_grid.height = 0
            self.mount_grid.opacity = 0.0
            self.mount_grid.disabled = True
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
                # Ensure final announcement always occurs after 3s at game end.
                self._schedule_final_result_after(3.0)


class NapoleonApp(App):
    def build(self):
        # Desktop debug window: force phone-like landscape ratio.
        if platform not in {"android", "ios"}:
            # Pixel 9a logical size (portrait ~412x915 dp) in landscape.
            Window.size = (915, 412)
        return Root()

    def on_start(self):
        if platform == "android":
            # Hide Android status/navigation bars and use full screen.
            Window.fullscreen = "auto"
        # Shared icon for desktop run and packaged builds.
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.icon = icon_path


if __name__ == "__main__":
    NapoleonApp().run()
