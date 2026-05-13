#!/usr/bin/env python3
"""
Euronet Falcon TCP Simulator
Developed by Rohan Sakhare
Internal Tool — IDFC First Bank / Euronet Integration
"""

import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import datetime
import json
import queue

# =============================================================================
# FIELD DEFINITIONS
# =============================================================================

# ── Inbound request header (96 bytes total)
# Positions derived from actual log:
#   00000000400000000995100000102EURONET FALCON  0000000000 DBTRAN25VISA932123123452
#   |--10--|--10--|--9--|--8--|--8--|---10--|1|--------40--------|
INBOUND_HEADER_FIELDS = [
    ("extHeaderLength",        10),
    ("appDataLength",          10),
    ("tranCode",                9),
    ("sourceApplication",       8),
    ("destinationApplication",  8),
    ("errorCode",              10),
    ("filler",                  1),
    ("externalHeaderData",     40),
]
INBOUND_HEADER_SIZE = sum(s for _, s in INBOUND_HEADER_FIELDS)  # 96

# ── ISO 125 outbound fields (vcDBTrans25Response from FalconPlugin.h)
ISO125_FIELDS = [
    # version + count
    ("responseRecordVersion",    1),
    ("scoreCount",               2),
    # score 1  (22+4+4+4+4+4 = 42)
    ("scoreName1",              22),
    ("errorCode1",               4),
    ("score1",                   4),
    ("reason11",                 4),
    ("reason12",                 4),
    ("reason13",                 4),
    # score 2
    ("scoreName2",              22),
    ("errorCode2",               4),
    ("score2",                   4),
    ("reason21",                 4),
    ("reason22",                 4),
    ("reason23",                 4),
    # score 3
    ("scoreName3",              22),
    ("errorCode3",               4),
    ("score3",                   4),
    ("reason31",                 4),
    ("reason32",                 4),
    ("reason33",                 4),
    # score 4
    ("scoreName4",              22),
    ("errorCode4",               4),
    ("score4",                   4),
    ("reason41",                 4),
    ("reason42",                 4),
    ("reason43",                 4),
    # score 5
    ("scoreName5",              22),
    ("errorCode5",               4),
    ("score5",                   4),
    ("reason51",                 4),
    ("reason52",                 4),
    ("reason53",                 4),
    # score 6
    ("scoreName6",              22),
    ("errorCode6",               4),
    ("score6",                   4),
    ("reason61",                 4),
    ("reason62",                 4),
    ("reason63",                 4),
    # score 7
    ("scoreName7",              22),
    ("errorCode7",               4),
    ("score7",                   4),
    ("reason71",                 4),
    ("reason72",                 4),
    ("reason73",                 4),
    # score 8
    ("scoreName8",              22),
    ("errorCode8",               4),
    ("score8",                   4),
    ("reason81",                 4),
    ("reason82",                 4),
    ("reason83",                 4),
    # segments + fillers  (8+8+8+2+4+2+8+8+8+8+4+4+8+4 = 86)
    ("segmentID1",               8),
    ("segmentID2",               8),
    ("segmentID3",               8),
    ("filler11",                 2),
    ("filler12",                 4),
    ("filler13",                 2),
    ("segmentID4",               8),
    ("segmentID5",               8),
    ("segmentID6",               8),
    ("segmentID7",               8),
    ("filler21",                 4),
    ("filler22",                 4),
    ("segmentID8",               8),
    ("filler3",                  4),
    # decisions 1-9 in ISO125, decision 9 code + decision10 + scoringServerID in ISO126
    ("decisionCount",            2),
    ("decisionType1",           32),
    ("decisionCode1",           32),
    ("decisionType2",           32),
    ("decisionCode2",           32),
    ("decisionType3",           32),
    ("decisionCode3",           32),
    ("decisionType4",           32),
    ("decisionCode4",           32),
    ("decisionType5",           32),
    ("decisionCode5",           32),
    ("decisionType6",           32),
    ("decisionCode6",           32),
    ("decisionType7",           32),
    ("decisionCode7",           32),
    ("decisionType8",           32),
    ("decisionCode8",           32),
    ("decisionType9",           32),
]

# ── ISO 126 outbound fields
ISO126_FIELDS = [
    ("decisionCode9",           32),
    ("decisionType10",          32),
    ("decisionCode10",          32),
    ("scoringServerID",          4),
]

# ISO125 size = 1+2 + 8*42 + 86 + 2 + 9*32+8*32 = 3+336+86+2+288+256 = 971
# ISO126 size = 32+32+32+4 = 100
# total app data = 1071   (appDataLength field)

# ── Inbound DBTrans25 body fields (for display only)
DBTRANS25_REQUEST_FIELDS = [
    ("workflow",                        16),
    ("recordType",                       8),
    ("dataSpecificationVersion",         5),
    ("clientIdFromHeader",              16),
    ("recordCreationDate",               8),
    ("recordCreationTime",               6),
    ("recordCreationMilliseconds",       3),
    ("gmtOffset",                        6),
    ("customerIdFromHeader",            20),
    ("customerAcctNumber",              40),
    ("externalTransactionId",           32),
    ("pan",                             19),
    ("authPostFlag",                     1),
    ("cardPostalCode",                   9),
    ("cardCountryCode",                  3),
    ("openDate",                         8),
    ("plasticIssueDate",                 8),
    ("plasticIssueType",                 1),
    ("acctExpireDate",                   8),
    ("cardExpireDate",                   8),
    ("dailyMerchandiseLimit",           10),
    ("dailyCashLimit",                  10),
    ("customerGender",                   1),
    ("customerDateOfBirth",              8),
    ("numberOfCards",                    3),
    ("incomeOrCashBack",                10),
    ("cardType",                         1),
    ("cardUse",                          1),
    ("transactionDate",                  8),
    ("transactionTime",                  6),
    ("transactionAmount",               13),
    ("transactionCurrencyCode",          3),
    ("transactionCurrencyConversionRate",13),
    ("authDecisionCode",                 1),
    ("transactionType",                  1),
    ("mcc",                              4),
    ("merchantPostalCode",               9),
    ("merchantCountryCode",              3),
    ("pinVerifyCode",                    1),
    ("cvvVerifyCode",                    1),
    ("posEntryMode",                     1),
    ("postDate",                         8),
    ("authPostMiscIndicator",            1),
    ("mismatchIndicator",                1),
    ("caseCreationIndicator",            1),
    ("userIndicator01",                  1),
    ("userIndicator02",                  1),
    ("userData01",                      10),
    ("userData02",                      10),
    ("onUsMerchantId",                  10),
    ("merchantDataProvided",             1),
    ("cardholderDataProvided",           1),
    ("externalScore1",                   4),
    ("externalScore2",                   4),
    ("externalScore3",                   4),
    ("customerPresent",                  1),
    ("atmOwner",                         1),
    ("randomDigits",                     2),
    ("portfolio",                       14),
    ("clientId",                        14),
    ("acquirerBin",                      6),
    ("merchantName",                    40),
    ("merchantCity",                    30),
    ("merchantState",                    3),
    ("caseSuppressionIndicator",         1),
    ("userIndicator03",                  5),
    ("userIndicator04",                  5),
    ("userData03",                      15),
    ("userData04",                      20),
    ("userData05",                      40),
    ("realtimeRequest",                  1),
    ("padResponse",                      1),
    ("padActionExpireDate",              8),
    ("cardMasterAcctNumber",            19),
    ("cardAipStatic",                    1),
    ("cardAipDynamic",                   1),
    ("RESERVED_01",                      1),
    ("cardAipVerify",                    1),
    ("cardAipRisk",                      1),
    ("cardAipIssuerAuthentication",      1),
    ("cardAipCombined",                  1),
    ("cardDailyLimitCode",               1),
    ("availableBalance",                13),
    ("availableDailyCashLimit",         13),
    ("availableDailyMerchandiseLimit",  13),
    ("atmHostMcc",                       4),
    ("atmProcessingCode",                6),
    ("atmCameraPresent",                 1),
    ("cardPinType",                      1),
    ("cardMediaType",                    1),
    ("cvv2Present",                      1),
    ("cvv2Response",                     1),
    ("avsResponse",                      1),
    ("transactionCategory",              1),
    ("acquirerId",                      12),
    ("acquirerCountry",                  3),
    ("terminalId",                      16),
    ("terminalType",                     1),
    ("terminalEntryCapability",          1),
    ("posConditionCode",                 2),
    ("networkId",                        1),
    ("RESERVED_02",                      1),
    ("authExpireDateVerify",             1),
    ("authSecondaryVerify",              1),
    ("authBeneficiary",                  1),
    ("authResponseCode",                 1),
    ("authReversalReason",               1),
    ("authCardIssuer",                   1),
    ("terminalVerificationResults",     10),
    ("cardVerificationResults",         10),
    ("cryptogramValid",                  1),
    ("atcCard",                          5),
    ("atcHost",                          5),
    ("RESERVED_03",                      2),
    ("offlineLowerLimit",                2),
    ("offlineUpperLimit",                2),
    ("recurringAuthFrequency",           2),
    ("recurringAuthExpireDate",          8),
    ("linkedAcctType",                   1),
    ("cardIncentive",                    1),
    ("cardPinLength",                    2),
    ("cardPinSetDate",                   8),
    ("processorAuthReasonCode",          5),
    ("standinAdvice",                    1),
    ("merchantId",                      16),
    ("cardOrder",                        1),
    ("cashbackAmount",                  13),
    ("userData06",                      13),
    ("userData07",                      40),
    ("paymentInstrumentId",             30),
    ("avsRequest",                       1),
    ("cvrOfflinePinVerificationPerformed",1),
    ("cvrOfflinePinVerificationFailed",  1),
    ("cvrPinTryLimitExceeded",           1),
    ("posUnattended",                    1),
    ("posOffPremises",                   1),
    ("posCardCapture",                   1),
    ("posSecurity",                      1),
    ("authId",                           6),
    ("userData08",                      10),
    ("userData09",                      10),
    ("userIndicator05",                  1),
    ("userIndicator06",                  1),
    ("userIndicator07",                  5),
    ("userIndicator08",                  5),
    ("modelControl1",                    1),
    ("modelControl2",                    1),
    ("modelControl3",                    1),
    ("modelControl4",                    1),
    ("RESERVED_04",                      3),
    ("segmentId1",                       6),
    ("segmentId2",                       6),
    ("segmentId3",                       6),
    ("segmentId4",                       6),
]

# =============================================================================
# DEFAULT RESPONSE VALUES
# =============================================================================

DEFAULT_ISO124 = {
    "appDataLength":            "00001071",   # auto-recalculated on send
    "extHeaderLength":          "0020",
    "tranCode":                 "200000102",
    "sourceApplication":        "PMAX      ",
    "destinationApplication":   "IDFCTANGO ",
    "errorCode":                "0000000000",
    "filler":                   " ",
    "externalHeaderData":       "DBTRAN251718532397  ",
}

DEFAULT_ISO125 = {
    "responseRecordVersion":   "4",
    "scoreCount":              " 1",
    "scoreName1":              "FFM.FRD.CARD          ",
    "errorCode1":              "   0",
    "score1":                  "  12",
    "reason11":                "   2",
    "reason12":                "  12",
    "reason13":                "   3",
    "scoreName2":              " " * 22,
    "errorCode2":              "    ",
    "score2":                  "    ",
    "reason21":                "    ",
    "reason22":                "    ",
    "reason23":                "    ",
    "scoreName3":              " " * 22,
    "errorCode3":              "    ",
    "score3":                  "    ",
    "reason31":                "    ",
    "reason32":                "    ",
    "reason33":                "    ",
    "scoreName4":              " " * 22,
    "errorCode4":              "    ",
    "score4":                  "    ",
    "reason41":                "    ",
    "reason42":                "    ",
    "reason43":                "    ",
    "scoreName5":              " " * 22,
    "errorCode5":              "    ",
    "score5":                  "    ",
    "reason51":                "    ",
    "reason52":                "    ",
    "reason53":                "    ",
    "scoreName6":              " " * 22,
    "errorCode6":              "    ",
    "score6":                  "    ",
    "reason61":                "    ",
    "reason62":                "    ",
    "reason63":                "    ",
    "scoreName7":              " " * 22,
    "errorCode7":              "    ",
    "score7":                  "    ",
    "reason71":                "    ",
    "reason72":                "    ",
    "reason73":                "    ",
    "scoreName8":              " " * 22,
    "errorCode8":              "    ",
    "score8":                  "    ",
    "reason81":                "    ",
    "reason82":                "    ",
    "reason83":                "    ",
    "segmentID1":              "gid180a1",
    "segmentID2":              "        ",
    "segmentID3":              "        ",
    "filler11":                "  ",
    "filler12":                "    ",
    "filler13":                "  ",
    "segmentID4":              "        ",
    "segmentID5":              "        ",
    "segmentID6":              "        ",
    "segmentID7":              "        ",
    "filler21":                "    ",
    "filler22":                "    ",
    "segmentID8":              "        ",
    "filler3":                 "    ",
    "decisionCount":           " 0",
    "decisionType1":           " " * 32,
    "decisionCode1":           " " * 32,
    "decisionType2":           " " * 32,
    "decisionCode2":           " " * 32,
    "decisionType3":           " " * 32,
    "decisionCode3":           " " * 32,
    "decisionType4":           " " * 32,
    "decisionCode4":           " " * 32,
    "decisionType5":           " " * 32,
    "decisionCode5":           " " * 32,
    "decisionType6":           " " * 32,
    "decisionCode6":           " " * 32,
    "decisionType7":           " " * 32,
    "decisionCode7":           " " * 32,
    "decisionType8":           " " * 32,
    "decisionCode8":           " " * 32,
    "decisionType9":           " " * 32,
}

DEFAULT_ISO126 = {
    "decisionCode9":           " " * 32,
    "decisionType10":          " " * 32,
    "decisionCode10":          " " * 32,
    "scoringServerID":         "    ",
}

# =============================================================================
# UTILITIES
# =============================================================================

def fw(val, size: int) -> str:
    """Fixed-width: pad right with spaces or trim to exact size."""
    s = str(val) if val is not None else ""
    return s[:size].ljust(size)


def parse_fields(raw: str, fields: list) -> dict:
    result = {}
    pos = 0
    for name, size in fields:
        result[name] = raw[pos:pos + size]
        pos += size
    return result


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class FalconSimulator:

    # Colour palette
    BG      = "#1e1e2e"
    PANEL   = "#181825"
    CARD    = "#313244"
    ACCENT  = "#cba6f7"
    ACCENT2 = "#89b4fa"
    TXT     = "#cdd6f4"
    TXT2    = "#a6adc8"
    GREEN   = "#a6e3a1"
    RED     = "#f38ba8"
    YELLOW  = "#f9e2af"
    BORDER  = "#45475a"
    ORANGE  = "#fab387"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(
            "Euronet Falcon TCP Simulator  —  Developed by Rohan Sakhare")
        self.root.geometry("1440x920")
        self.root.minsize(1100, 700)
        self.root.configure(bg=self.BG)

        self.server_socket = None
        self.server_thread = None
        self.running       = False
        self.client_conn   = None
        self.log_queue     = queue.Queue()
        self._bound_ip     = ""
        self._bound_port   = 0

        # Live editable response values
        self.resp124 = dict(DEFAULT_ISO124)
        self.resp125 = dict(DEFAULT_ISO125)
        self.resp126 = dict(DEFAULT_ISO126)

        # Tkinter StringVars (populated by _build_editor_tab)
        self.svars124: dict = {}
        self.svars125: dict = {}
        self.svars126: dict = {}

        self._build_ui()
        self._poll_log()

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):
        self._apply_styles()

        # Banner
        banner = tk.Frame(self.root, bg="#11111b", height=52)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner,
                 text="🦅  EURONET FALCON TCP SIMULATOR",
                 bg="#11111b", fg=self.ACCENT,
                 font=("Consolas", 14, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(banner,
                 text="Developed by Rohan Sakhare",
                 bg="#11111b", fg=self.TXT2,
                 font=("Consolas", 10)).pack(side="left", padx=4)
        self.dot = tk.Label(banner, text="●  STOPPED",
                            bg="#11111b", fg=self.RED,
                            font=("Consolas", 11, "bold"))
        self.dot.pack(side="right", padx=20)

        # Control bar
        ctrl = tk.Frame(self.root, bg=self.PANEL, height=54)
        ctrl.pack(fill="x")
        ctrl.pack_propagate(False)
        self._build_ctrl_bar(ctrl)

        # Main paned area
        pane = tk.PanedWindow(self.root, orient="horizontal",
                              bg=self.BG, sashwidth=5, sashrelief="flat")
        pane.pack(fill="both", expand=True)

        left = tk.Frame(pane, bg=self.BG)
        pane.add(left, minsize=600)

        right = tk.Frame(pane, bg=self.BG)
        pane.add(right, minsize=380)

        # Notebook (left)
        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        t0 = tk.Frame(nb, bg=self.BG)
        nb.add(t0, text="  📥 Incoming Request  ")
        self._build_request_tab(t0)

        t1 = tk.Frame(nb, bg=self.BG)
        nb.add(t1, text="  ISO 124 (Header)  ")
        self._build_editor_tab(
            t1,
            "ISO 124 — Response Header",
            DEFAULT_ISO124,
            self.svars124,
            self.resp124,
            {"appDataLength": 8, "extHeaderLength": 4,
             "tranCode": 9, "sourceApplication": 10,
             "destinationApplication": 10, "errorCode": 10,
             "filler": 1, "externalHeaderData": 20},
        )

        t2 = tk.Frame(nb, bg=self.BG)
        nb.add(t2, text="  ISO 125 (Scores)  ")
        self._build_editor_tab(
            t2,
            "ISO 125 — Falcon Score + Decision Response",
            DEFAULT_ISO125,
            self.svars125,
            self.resp125,
            {n: s for n, s in ISO125_FIELDS},
        )

        t3 = tk.Frame(nb, bg=self.BG)
        nb.add(t3, text="  ISO 126 (Decision overflow)  ")
        self._build_editor_tab(
            t3,
            "ISO 126 — Decision Code 9 + Decision 10 + Scoring Server ID",
            DEFAULT_ISO126,
            self.svars126,
            self.resp126,
            {n: s for n, s in ISO126_FIELDS},
        )

        # Log (right)
        self._build_log_panel(right)

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook",     background=self.BG,   borderwidth=0)
        s.configure("TNotebook.Tab", background=self.CARD, foreground=self.TXT2,
                    padding=[14, 6], font=("Consolas", 10))
        s.map("TNotebook.Tab",
              background=[("selected", self.PANEL)],
              foreground=[("selected", self.ACCENT)])
        s.configure("TFrame",        background=self.BG)
        s.configure("TScrollbar",    background=self.CARD,
                    troughcolor=self.PANEL, arrowcolor=self.TXT2)

    def _build_ctrl_bar(self, ctrl):
        def lbl(text):
            return tk.Label(ctrl, text=text, bg=self.PANEL, fg=self.TXT2,
                            font=("Consolas", 10))

        def ent(var, w):
            return tk.Entry(ctrl, textvariable=var, width=w,
                            bg=self.CARD, fg=self.TXT,
                            insertbackground=self.TXT,
                            relief="flat", font=("Consolas", 11), bd=2)

        def btn(text, cmd, bg, fg, **kw):
            return tk.Button(ctrl, text=text, command=cmd,
                             bg=bg, fg=fg,
                             font=("Consolas", 10, "bold"),
                             relief="flat", padx=12,
                             cursor="hand2", **kw)

        lbl("Listen IP:").pack(side="left", padx=(16, 4), pady=14)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        ent(self.ip_var, 15).pack(side="left", padx=4)

        lbl("Port:").pack(side="left", padx=(10, 4))
        self.port_var = tk.StringVar(value="8070")
        ent(self.port_var, 7).pack(side="left", padx=4)

        self.start_btn = btn("▶  START", self._start_server, "#40a02b", "white")
        self.start_btn.pack(side="left", padx=12)

        self.stop_btn = btn("■  STOP", self._stop_server,
                            self.CARD, self.RED, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        btn("🗑  Clear Log",     self._clear_log,      self.CARD, self.TXT2
            ).pack(side="right", padx=14)
        btn("💾  Save Response", self._save_template,  self.CARD, self.ACCENT2
            ).pack(side="right", padx=4)
        btn("📂  Load Response", self._load_template,  self.CARD, self.ACCENT2
            ).pack(side="right", padx=4)

    # ── Request viewer tab ────────────────────────────────────────────────────

    def _build_request_tab(self, parent):
        top = tk.Frame(parent, bg=self.BG)
        top.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(top,
                 text="Last received request — parsed fields",
                 bg=self.BG, fg=self.TXT2,
                 font=("Consolas", 9)).pack(side="left")
        tk.Button(top, text="🗑  Clear Request",
                  command=self._clear_request,
                  bg=self.CARD, fg=self.RED,
                  font=("Consolas", 9), relief="flat",
                  padx=8, cursor="hand2").pack(side="right")

        self.req_text = scrolledtext.ScrolledText(
            parent, bg=self.PANEL, fg=self.TXT,
            font=("Consolas", 10), relief="flat",
            selectbackground=self.ACCENT,
            selectforeground="#11111b",
            insertbackground=self.TXT,
            state="disabled")
        self.req_text.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        for tag, fg, bold in [
            ("sec", self.ACCENT,  True),
            ("fld", self.ACCENT2, False),
            ("val", self.TXT,     False),
            ("raw", self.YELLOW,  False),
            ("ts",  self.TXT2,    False),
            ("sep", self.BORDER,  False),
            ("err", self.RED,     False),
        ]:
            font_spec = ("Consolas", 10, "bold") if bold else ("Consolas", 10)
            self.req_text.tag_configure(tag, foreground=fg, font=font_spec)

    def _clear_request(self):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")
        self.req_text.config(state="disabled")

    # ── Generic editor tab ────────────────────────────────────────────────────

    def _build_editor_tab(self, parent, title: str, defaults: dict,
                          var_dict: dict, store_dict: dict, size_map: dict):
        tk.Label(parent, text=title,
                 bg=self.BG, fg=self.ACCENT,
                 font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 1))
        tk.Label(parent,
                 text="Fields are fixed-length — values padded/trimmed to exact size on send.",
                 bg=self.BG, fg=self.TXT2,
                 font=("Consolas", 9)).pack(anchor="w", padx=8, pady=(0, 4))

        canvas = tk.Canvas(parent, bg=self.BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=6, pady=2)

        inner = tk.Frame(canvas, bg=self.BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_inner)
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        for ev, delta in [("<MouseWheel>", None),
                          ("<Button-4>", -1), ("<Button-5>", 1)]:
            if delta is None:
                canvas.bind(ev, lambda e: canvas.yview_scroll(
                    -1 * (e.delta // 120), "units"))
            else:
                canvas.bind(ev, lambda e, d=delta: canvas.yview_scroll(d, "units"))

        # Column header
        hdr = tk.Frame(inner, bg=self.CARD)
        hdr.pack(fill="x", padx=2, pady=(2, 1))
        for lbl_text, w in [("Field Name", 36), ("Size", 6),
                             ("Value (editable)", 0)]:
            tk.Label(hdr, text=lbl_text, bg=self.CARD, fg=self.ACCENT,
                     font=("Consolas", 9, "bold"),
                     width=w, anchor="w").pack(side="left", padx=6, pady=3)

        for name, default_val in defaults.items():
            sz = size_map.get(name, len(str(default_val)))
            row = tk.Frame(inner, bg=self.PANEL)
            row.pack(fill="x", padx=2, pady=1)

            tk.Label(row, text=name, bg=self.PANEL, fg=self.ACCENT2,
                     font=("Consolas", 9), width=36,
                     anchor="w").pack(side="left", padx=6)
            tk.Label(row, text=str(sz), bg=self.PANEL, fg=self.TXT2,
                     font=("Consolas", 9), width=6,
                     anchor="w").pack(side="left", padx=2)

            var = tk.StringVar(value=str(default_val))
            var_dict[name] = var
            tk.Entry(row, textvariable=var,
                     bg=self.CARD, fg=self.TXT,
                     insertbackground=self.TXT, relief="flat",
                     font=("Consolas", 9), width=56
                     ).pack(side="left", padx=4, pady=2, fill="x", expand=True)

            var.trace_add("write",
                          lambda *a, k=name, v=var, d=store_dict:
                              d.update({k: v.get()}))

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _build_log_panel(self, parent):
        tk.Label(parent, text="📋  Activity Log",
                 bg=self.BG, fg=self.ACCENT,
                 font=("Consolas", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 2))

        self.log_text = scrolledtext.ScrolledText(
            parent, bg=self.PANEL, fg=self.TXT,
            font=("Consolas", 10), relief="flat",
            selectbackground=self.ACCENT,
            selectforeground="#11111b",
            insertbackground=self.TXT,
            state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        for tag, fg in [("ts",      self.TXT2),
                        ("info",    self.ACCENT2),
                        ("success", self.GREEN),
                        ("error",   self.RED),
                        ("warn",    self.YELLOW),
                        ("raw",     self.ORANGE),
                        ("sep",     self.BORDER)]:
            self.log_text.tag_configure(tag, foreground=fg)

    # =========================================================================
    # SERVER
    # =========================================================================

    def _start_server(self):
        ip       = self.ip_var.get().strip()
        port_str = self.port_var.get().strip()

        try:
            port = int(port_str)
            assert 1 <= port <= 65535
        except Exception:
            messagebox.showerror("Invalid Port",
                                 f"Port must be 1–65535.  Got: '{port_str}'")
            return

        if self.running:
            self._log("Server already running.", "warn")
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind ONLY to the exact IP and port entered by the user
            self.server_socket.bind((ip, port))
            self.server_socket.listen(1)
        except Exception as ex:
            messagebox.showerror("Bind Error", str(ex))
            self._log(f"Bind failed on {ip}:{port} — {ex}", "error")
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
            return

        self.running     = True
        self._bound_ip   = ip
        self._bound_port = port

        self.server_thread = threading.Thread(
            target=self._accept_loop, daemon=True)
        self.server_thread.start()

        self._log(f"Server started — listening on {ip}:{port}", "success")
        self._set_dot(f"●  LISTENING  {ip}:{port}", self.GREEN)
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def _stop_server(self):
        self.running = False
        for obj in (self.client_conn, self.server_socket):
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
        self.client_conn  = None
        self.server_socket = None

        self._log("Server stopped.", "warn")
        self._set_dot("●  STOPPED", self.RED)
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _set_dot(self, text: str, colour: str):
        self.root.after(0, lambda: self.dot.config(text=text, fg=colour))

    # ── Accept loop ───────────────────────────────────────────────────────────

    def _accept_loop(self):
        self._log("Waiting for connection…", "info")
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                conn, addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as ex:
                if self.running:
                    self._log(f"Accept error: {ex}", "error")
                break

            cip, cport = addr
            self._log(f"Client connected: {cip}:{cport}", "success")
            self._set_dot(f"●  CONNECTED  {cip}:{cport}", self.ACCENT)
            self.client_conn = conn

            self._handle_client(conn, addr)

            self._log(f"Client disconnected: {cip}:{cport}", "warn")
            self.client_conn = None
            self._set_dot(
                f"●  LISTENING  {self._bound_ip}:{self._bound_port}",
                self.GREEN)

    # ── Handle one client ─────────────────────────────────────────────────────

    def _handle_client(self, conn: socket.socket, addr):
        buf = b""
        conn.settimeout(120.0)
        try:
            while self.running:
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                except Exception as ex:
                    self._log(f"Recv error: {ex}", "error")
                    break

                if not chunk:
                    break

                buf += chunk

                try:
                    raw = buf.decode("ascii", errors="replace")
                except Exception:
                    raw = buf.decode("latin-1", errors="replace")

                self._log("─" * 55, "sep")
                self._log(
                    f"Received {len(chunk)} bytes from {addr[0]}:{addr[1]}",
                    "info")
                self._log(f"RAW IN ↓\n{raw}", "raw")

                hdr_d, body_d = self._parse_request(raw)
                self.root.after(0,
                    lambda h=hdr_d, b=body_d, r=raw:
                        self._display_request(h, b, r))

                resp = self._build_response()
                try:
                    conn.sendall(resp.encode("ascii"))
                    self._log(
                        f"Response sent ({len(resp)} bytes)", "success")
                    self._log(f"RAW OUT ↓\n{resp}", "raw")
                except Exception as ex:
                    self._log(f"Send error: {ex}", "error")

                buf = b""

        except Exception as ex:
            self._log(f"Client handler error: {ex}", "error")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # =========================================================================
    # PARSE REQUEST
    # =========================================================================

    def _parse_request(self, raw: str):
        hdr, body = {}, {}
        if len(raw) < INBOUND_HEADER_SIZE:
            hdr["_error"] = (
                f"Message too short for header "
                f"({len(raw)} < {INBOUND_HEADER_SIZE})")
            return hdr, body
        hdr  = parse_fields(raw, INBOUND_HEADER_FIELDS)
        body = parse_fields(raw[INBOUND_HEADER_SIZE:], DBTRANS25_REQUEST_FIELDS)
        return hdr, body

    # =========================================================================
    # BUILD RESPONSE
    # =========================================================================

    def _build_response(self) -> str:
        """
        Assemble the complete outbound message:

          ISO 124  (72 bytes)
            appDataLength      [8]   ← auto-computed = len(ISO125+ISO126)
            extHeaderLength    [4]   "0020"
            tranCode           [9]   "200000102"
            sourceApplication  [10]  "PMAX      "
            destinationApp     [10]  "IDFCTANGO "
            errorCode          [10]  "0000000000"
            filler             [1]   " "
            externalHeaderData [20]  "DBTRAN25xxxxxxxxxx  "

          ISO 125  (971 bytes)  — all fields from ISO125_FIELDS
          ISO 126  (100 bytes)  — decisionCode9 + decisionType10 +
                                  decisionCode10 + scoringServerID
        """

        # ── Read current StringVar values ──────────────────────────────────
        s125 = ({k: v.get() for k, v in self.svars125.items()}
                if self.svars125 else dict(self.resp125))
        s126 = ({k: v.get() for k, v in self.svars126.items()}
                if self.svars126 else dict(self.resp126))
        s124 = ({k: v.get() for k, v in self.svars124.items()}
                if self.svars124 else dict(self.resp124))

        # ── Build ISO 125 ──────────────────────────────────────────────────
        iso125 = ""
        for fname, fsize in ISO125_FIELDS:
            iso125 += fw(s125.get(fname, ""), fsize)

        # ── Build ISO 126 ──────────────────────────────────────────────────
        iso126 = ""
        for fname, fsize in ISO126_FIELDS:
            iso126 += fw(s126.get(fname, ""), fsize)

        app_data = iso125 + iso126          # this is what appDataLength counts
        app_len  = len(app_data)            # auto-computed

        # ── Build ISO 124 ─────────────────────────────────────────────────
        ext_hdr = fw(s124.get("externalHeaderData",
                               "DBTRAN251718532397  "), 20)

        iso124 = (
            fw(str(app_len).zfill(8),                               8) +  # appDataLength
            fw(s124.get("extHeaderLength",  "0020"),                4) +  # extHeaderLength
            fw(s124.get("tranCode",         "200000102"),           9) +  # tranCode
            fw(s124.get("sourceApplication","PMAX      "),         10) +  # sourceApplication
            fw(s124.get("destinationApplication","IDFCTANGO "),    10) +  # destinationApplication
            fw(s124.get("errorCode",        "0000000000"),         10) +  # errorCode
            fw(s124.get("filler",           " "),                   1) +  # filler
            ext_hdr                                                        # externalHeaderData (20)
        )
        # total ISO124 = 8+4+9+10+10+10+1+20 = 72

        return iso124 + app_data

    # =========================================================================
    # DISPLAY REQUEST
    # =========================================================================

    def _display_request(self, hdr: dict, body: dict, raw: str):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.req_text.insert("end", f"Received: {ts}\n", "ts")
        self.req_text.insert("end", "─" * 70 + "\n", "sep")

        self.req_text.insert("end", "\n▸ HEADER  (ISO 124 incoming)\n", "sec")
        for k, v in hdr.items():
            if k.startswith("_"):
                self.req_text.insert("end", f"  {v}\n", "err")
                continue
            disp = v.strip() if isinstance(v, str) else str(v)
            self.req_text.insert("end", f"  {k:<44}", "fld")
            self.req_text.insert("end", f"  [{disp}]\n",  "val")

        if body:
            self.req_text.insert("end", "\n▸ BODY  (DBTrans25 Request)\n", "sec")
            for k, v in body.items():
                disp = v.strip() if isinstance(v, str) else str(v)
                self.req_text.insert("end", f"  {k:<44}", "fld")
                self.req_text.insert("end", f"  [{disp}]\n", "val")

        self.req_text.insert("end", "\n─ RAW ─\n", "sep")
        self.req_text.insert("end", raw + "\n", "raw")
        self.req_text.config(state="disabled")
        self.req_text.see("1.0")

    # =========================================================================
    # LOG
    # =========================================================================

    def _log(self, msg: str, level: str = "info"):
        self.log_queue.put((msg, level))

    def _poll_log(self):
        try:
            while True:
                msg, level = self.log_queue.get_nowait()
                self._write_log(msg, level)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    def _write_log(self, msg: str, level: str):
        self.log_text.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if level != "sep":
            self.log_text.insert("end", f"[{ts}] ", "ts")
        self.log_text.insert("end", msg + "\n", level)
        self.log_text.config(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # =========================================================================
    # SAVE / LOAD
    # =========================================================================

    def _save_template(self):
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            title="Save Response Template")
        if not path:
            return
        data = {
            "iso124": {k: v.get() for k, v in self.svars124.items()},
            "iso125": {k: v.get() for k, v in self.svars125.items()},
            "iso126": {k: v.get() for k, v in self.svars126.items()},
        }
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self._log(f"Template saved: {path}", "success")
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))

    def _load_template(self):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            title="Load Response Template")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            return
        for section, var_dict in [("iso124", self.svars124),
                                   ("iso125", self.svars125),
                                   ("iso126", self.svars126)]:
            for k, v in data.get(section, {}).items():
                if k in var_dict:
                    var_dict[k].set(v)
        self._log(f"Template loaded: {path}", "success")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    root = tk.Tk()
    app  = FalconSimulator(root)
    root.protocol("WM_DELETE_WINDOW",
                  lambda: (app._stop_server(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
