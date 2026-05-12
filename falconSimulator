#!/usr/bin/env python3
"""
Euronet Falcon TCP Simulator
Developed by Rohan Sakhare
Internal Tool — IDFC First Bank / Euronet Integration
"""

import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import datetime
import json
import os
import queue

# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE FIELD DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

# Header fields (ISO 124 equivalent)
HEADER_FIELDS = [
    ("extHeaderLength",        10),
    ("appDataLength",          10),
    ("tranCode",                9),
    ("sourceApplication",       8),
    ("destinationApplication",  8),
    ("errorCode",              10),
    ("filler",                  1),
    ("externalHeaderData",     40),
]

# DBTrans25 request fields
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

# DBTrans25 response fields (ISO 125)
DBTRANS25_RESPONSE_FIELDS = [
    ("responseRecordVersion",    1),
    ("scoreCount",               2),
    ("scoreName1",              22),
    ("errorCode1",               4),
    ("score1",                   4),
    ("reason11",                 4),
    ("reason12",                 4),
    ("reason13",                 4),
    ("scoreName2",              22),
    ("errorCode2",               4),
    ("score2",                   4),
    ("reason21",                 4),
    ("reason22",                 4),
    ("reason23",                 4),
    ("scoreName3",              22),
    ("errorCode3",               4),
    ("score3",                   4),
    ("reason31",                 4),
    ("reason32",                 4),
    ("reason33",                 4),
    ("scoreName4",              22),
    ("errorCode4",               4),
    ("score4",                   4),
    ("reason41",                 4),
    ("reason42",                 4),
    ("reason43",                 4),
    ("scoreName5",              22),
    ("errorCode5",               4),
    ("score5",                   4),
    ("reason51",                 4),
    ("reason52",                 4),
    ("reason53",                 4),
    ("scoreName6",              22),
    ("errorCode6",               4),
    ("score6",                   4),
    ("reason61",                 4),
    ("reason62",                 4),
    ("reason63",                 4),
    ("scoreName7",              22),
    ("errorCode7",               4),
    ("score7",                   4),
    ("reason71",                 4),
    ("reason72",                 4),
    ("reason73",                 4),
    ("scoreName8",              22),
    ("errorCode8",               4),
    ("score8",                   4),
    ("reason81",                 4),
    ("reason82",                 4),
    ("reason83",                 4),
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
    ("decisionCode9",           32),
    ("decisionType10",          32),
    ("decisionCode10",          32),
    ("scoringServerID",          4),
]

# Response header fields (ISO 124 response)
RESPONSE_HEADER_FIELDS = [
    ("appDataLength",           8),
    ("extHeaderLength",         4),
    ("tranCode",                9),
    ("sourceApplication",      10),
    ("destinationApplication", 10),
    ("errorCode",              10),
    ("filler",                  1),
    ("externalHeaderData",     20),
]

# ─────────────────────────────────────────────────────────────────────────────
# PARSER / BUILDER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def parse_fixed_fields(raw: str, fields: list) -> dict:
    result = {}
    pos = 0
    for name, size in fields:
        chunk = raw[pos:pos+size]
        result[name] = chunk
        pos += size
    return result

def build_fixed_message(values: dict, fields: list) -> str:
    msg = ""
    for name, size in fields:
        val = values.get(name, "")
        val = str(val)
        if len(val) > size:
            val = val[:size]
        else:
            val = val.ljust(size)
        msg += val
    return msg

def parse_incoming_message(raw: str) -> dict:
    """Parse the full incoming request message into named fields."""
    result = {"_raw": raw, "_sections": {}}

    # Header: first 56 bytes (10+10+9+8+8+10+1) = 56, then extHeaderData is 40 → total 96
    hdr_total = sum(s for _, s in HEADER_FIELDS)
    hdr = parse_fixed_fields(raw[:hdr_total], HEADER_FIELDS)
    result["_sections"]["header"] = hdr

    # App data starts after header
    try:
        ext_hdr_len = int(hdr.get("extHeaderLength", "40").strip() or "40")
    except:
        ext_hdr_len = 40
    app_start = hdr_total
    app_raw = raw[app_start:]
    req = parse_fixed_fields(app_raw, DBTRANS25_REQUEST_FIELDS)
    result["_sections"]["request"] = req

    result.update(hdr)
    result.update(req)
    return result

# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT RESPONSE TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_RESPONSE_ISO124 = {
    "appDataLength":           "00001069",
    "extHeaderLength":         "0020",
    "tranCode":                "200000102",
    "sourceApplication":       "PMAX      ",
    "destinationApplication":  "IDFCTANGO ",
    "errorCode":               "0000000000",
    "filler":                  " ",
    "externalHeaderData":      "DBTRAN251718532397  ",
}

DEFAULT_RESPONSE_ISO125 = {
    "responseRecordVersion":  "4",
    "scoreCount":             " 1",
    "scoreName1":             "FFM.FRD.CARD          ",
    "errorCode1":             "   0",
    "score1":                 "  12",
    "reason11":               "   2",
    "reason12":               "  12",
    "reason13":               "   3",
    "scoreName2":             "                      ",
    "errorCode2":             "    ",
    "score2":                 "    ",
    "reason21":               "    ",
    "reason22":               "    ",
    "reason23":               "    ",
    "scoreName3":             "                      ",
    "errorCode3":             "    ",
    "score3":                 "    ",
    "reason31":               "    ",
    "reason32":               "    ",
    "reason33":               "    ",
    "scoreName4":             "                      ",
    "errorCode4":             "    ",
    "score4":                 "    ",
    "reason41":               "    ",
    "reason42":               "    ",
    "reason43":               "    ",
    "scoreName5":             "                      ",
    "errorCode5":             "    ",
    "score5":                 "    ",
    "reason51":               "    ",
    "reason52":               "    ",
    "reason53":               "    ",
    "scoreName6":             "                      ",
    "errorCode6":             "    ",
    "score6":                 "    ",
    "reason61":               "    ",
    "reason62":               "    ",
    "reason63":               "    ",
    "scoreName7":             "                      ",
    "errorCode7":             "    ",
    "score7":                 "    ",
    "reason71":               "    ",
    "reason72":               "    ",
    "reason73":               "    ",
    "scoreName8":             "                      ",
    "errorCode8":             "    ",
    "score8":                 "    ",
    "reason81":               "    ",
    "reason82":               "    ",
    "reason83":               "    ",
    "segmentID1":             "gid180a1",
    "segmentID2":             "        ",
    "segmentID3":             "        ",
    "filler11":               "  ",
    "filler12":               "    ",
    "filler13":               "  ",
    "segmentID4":             "        ",
    "segmentID5":             "        ",
    "segmentID6":             "        ",
    "segmentID7":             "        ",
    "filler21":               "    ",
    "filler22":               "    ",
    "segmentID8":             "        ",
    "filler3":                "    ",
    "decisionCount":          " 0",
    "decisionType1":          " " * 32,
    "decisionCode1":          " " * 32,
    "decisionType2":          " " * 32,
    "decisionCode2":          " " * 32,
    "decisionType3":          " " * 32,
    "decisionCode3":          " " * 32,
    "decisionType4":          " " * 32,
    "decisionCode4":          " " * 32,
    "decisionType5":          " " * 32,
    "decisionCode5":          " " * 32,
    "decisionType6":          " " * 32,
    "decisionCode6":          " " * 32,
    "decisionType7":          " " * 32,
    "decisionCode7":          " " * 32,
    "decisionType8":          " " * 32,
    "decisionCode8":          " " * 32,
    "decisionType9":          " " * 32,
    "decisionCode9":          " " * 32,
    "decisionType10":         " " * 32,
    "decisionCode10":         " " * 32,
    "scoringServerID":        "    ",
}

DEFAULT_RESPONSE_ISO126 = {
    "decisionCode10_ext":     " " * 32,
    "scoringServerID_ext":    " " * 32,
    "padding":                " " * 36,
}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

class FalconSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Euronet Falcon TCP Simulator  —  Developed by Rohan Sakhare")
        self.root.geometry("1400x900")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#1e1e2e")

        self.server_socket = None
        self.server_thread = None
        self.running = False
        self.client_conn = None
        self.client_addr = None
        self.log_queue = queue.Queue()

        # Response templates (editable)
        self.resp_iso124 = dict(DEFAULT_RESPONSE_ISO124)
        self.resp_iso125 = dict(DEFAULT_RESPONSE_ISO125)
        self.resp_iso126 = dict(DEFAULT_RESPONSE_ISO126)

        # UI entry vars for response fields
        self.resp_vars_124 = {}
        self.resp_vars_125 = {}
        self.resp_vars_126 = {}

        self._build_ui()
        self._poll_log_queue()

    # ─── UI CONSTRUCTION ────────────────────────────────────────────────────

    def _build_ui(self):
        DARK_BG    = "#1e1e2e"
        PANEL_BG   = "#181825"
        CARD_BG    = "#313244"
        ACCENT     = "#cba6f7"
        ACCENT2    = "#89b4fa"
        TEXT_PRI   = "#cdd6f4"
        TEXT_SEC   = "#a6adc8"
        GREEN      = "#a6e3a1"
        RED        = "#f38ba8"
        YELLOW     = "#f9e2af"
        BORDER     = "#45475a"

        self._colors = dict(
            DARK_BG=DARK_BG, PANEL_BG=PANEL_BG, CARD_BG=CARD_BG,
            ACCENT=ACCENT, ACCENT2=ACCENT2, TEXT_PRI=TEXT_PRI,
            TEXT_SEC=TEXT_SEC, GREEN=GREEN, RED=RED, YELLOW=YELLOW, BORDER=BORDER
        )

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",        background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab",    background=CARD_BG, foreground=TEXT_SEC,
                        padding=[14, 6], font=("Consolas", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", PANEL_BG)],
                  foreground=[("selected", ACCENT)])
        style.configure("TFrame",           background=DARK_BG)
        style.configure("TLabel",           background=DARK_BG, foreground=TEXT_PRI,
                        font=("Consolas", 10))
        style.configure("TEntry",           fieldbackground=CARD_BG, foreground=TEXT_PRI,
                        insertcolor=TEXT_PRI, borderwidth=1, relief="flat")
        style.configure("TScrollbar",       background=CARD_BG, troughcolor=PANEL_BG,
                        arrowcolor=TEXT_SEC)
        style.configure("Vertical.TScrollbar", background=CARD_BG)

        # ── TOP BANNER ──
        banner = tk.Frame(self.root, bg="#11111b", height=52)
        banner.pack(fill="x", side="top")
        banner.pack_propagate(False)

        tk.Label(banner, text="🦅  EURONET FALCON TCP SIMULATOR",
                 bg="#11111b", fg=ACCENT,
                 font=("Consolas", 14, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(banner, text="Developed by Rohan Sakhare",
                 bg="#11111b", fg=TEXT_SEC,
                 font=("Consolas", 10)).pack(side="left", padx=4)

        # status dot
        self.status_dot = tk.Label(banner, text="●  STOPPED",
                                   bg="#11111b", fg=RED,
                                   font=("Consolas", 11, "bold"))
        self.status_dot.pack(side="right", padx=20)

        # ── SERVER CONTROL BAR ──
        ctrl = tk.Frame(self.root, bg=PANEL_BG, height=54)
        ctrl.pack(fill="x", side="top")
        ctrl.pack_propagate(False)

        tk.Label(ctrl, text="Listen IP:", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Consolas", 10)).pack(side="left", padx=(16, 4), pady=14)
        self.ip_var = tk.StringVar(value="0.0.0.0")
        ip_entry = tk.Entry(ctrl, textvariable=self.ip_var, width=15,
                            bg=CARD_BG, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                            relief="flat", font=("Consolas", 11), bd=0)
        ip_entry.pack(side="left", padx=4)

        tk.Label(ctrl, text="Port:", bg=PANEL_BG, fg=TEXT_SEC,
                 font=("Consolas", 10)).pack(side="left", padx=(12, 4))
        self.port_var = tk.StringVar(value="1234")
        port_entry = tk.Entry(ctrl, textvariable=self.port_var, width=7,
                              bg=CARD_BG, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                              relief="flat", font=("Consolas", 11), bd=0)
        port_entry.pack(side="left", padx=4)

        self.start_btn = tk.Button(ctrl, text="▶  START",
                                   command=self._start_server,
                                   bg="#40a02b", fg="white",
                                   font=("Consolas", 10, "bold"),
                                   relief="flat", padx=14, cursor="hand2")
        self.start_btn.pack(side="left", padx=14)

        self.stop_btn = tk.Button(ctrl, text="■  STOP",
                                  command=self._stop_server, state="disabled",
                                  bg=CARD_BG, fg=RED,
                                  font=("Consolas", 10, "bold"),
                                  relief="flat", padx=14, cursor="hand2")
        self.stop_btn.pack(side="left", padx=2)

        tk.Button(ctrl, text="🗑  Clear Log",
                  command=self._clear_log,
                  bg=CARD_BG, fg=TEXT_SEC,
                  font=("Consolas", 10),
                  relief="flat", padx=10, cursor="hand2").pack(side="right", padx=16)

        tk.Button(ctrl, text="💾  Save Response",
                  command=self._save_response_template,
                  bg=CARD_BG, fg=ACCENT2,
                  font=("Consolas", 10),
                  relief="flat", padx=10, cursor="hand2").pack(side="right", padx=4)

        tk.Button(ctrl, text="📂  Load Response",
                  command=self._load_response_template,
                  bg=CARD_BG, fg=ACCENT2,
                  font=("Consolas", 10),
                  relief="flat", padx=10, cursor="hand2").pack(side="right", padx=4)

        # ── MAIN SPLIT ──
        main = tk.PanedWindow(self.root, orient="horizontal",
                              bg=DARK_BG, sashwidth=5, sashrelief="flat")
        main.pack(fill="both", expand=True)

        # LEFT: Notebook for request view + response editor
        left_frame = tk.Frame(main, bg=DARK_BG)
        main.add(left_frame, minsize=560)

        nb = ttk.Notebook(left_frame)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        # Tab 1: Last Request
        req_frame = tk.Frame(nb, bg=DARK_BG)
        nb.add(req_frame, text="  📥 Incoming Request  ")
        self._build_request_tab(req_frame)

        # Tab 2: ISO 124 Response
        tab124 = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab124, text="  ISO 124 (Header)  ")
        self._build_response_tab(tab124, "ISO 124 — Response Header", DEFAULT_RESPONSE_ISO124,
                                 self.resp_vars_124, self.resp_iso124)

        # Tab 3: ISO 125 Response
        tab125 = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab125, text="  ISO 125 (Scores)  ")
        self._build_response_tab(tab125, "ISO 125 — Falcon Score Response", DEFAULT_RESPONSE_ISO125,
                                 self.resp_vars_125, self.resp_iso125)

        # Tab 4: ISO 126 Response
        tab126 = tk.Frame(nb, bg=DARK_BG)
        nb.add(tab126, text="  ISO 126 (Decisions)  ")
        self._build_iso126_tab(tab126)

        # RIGHT: Log panel
        right_frame = tk.Frame(main, bg=DARK_BG)
        main.add(right_frame, minsize=380)
        self._build_log_panel(right_frame)

    def _build_request_tab(self, parent):
        C = self._colors
        tk.Label(parent, text="Last received request — parsed fields",
                 bg=C["DARK_BG"], fg=C["TEXT_SEC"],
                 font=("Consolas", 9)).pack(anchor="w", padx=8, pady=(6, 2))

        self.req_text = scrolledtext.ScrolledText(
            parent, bg=C["PANEL_BG"], fg=C["TEXT_PRI"],
            font=("Consolas", 10), relief="flat",
            selectbackground=C["ACCENT"], selectforeground="#11111b",
            insertbackground=C["TEXT_PRI"], state="disabled")
        self.req_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # Tag colours for request display
        self.req_text.tag_configure("section",  foreground=C["ACCENT"],  font=("Consolas", 10, "bold"))
        self.req_text.tag_configure("field",    foreground=C["ACCENT2"])
        self.req_text.tag_configure("value",    foreground=C["TEXT_PRI"])
        self.req_text.tag_configure("raw",      foreground=C["YELLOW"])
        self.req_text.tag_configure("ts",       foreground=C["GREEN"])

    def _build_response_tab(self, parent, title, defaults, var_dict, store_dict):
        C = self._colors
        tk.Label(parent, text=title,
                 bg=C["DARK_BG"], fg=C["ACCENT"],
                 font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        tk.Label(parent, text="All fields are fixed-length. Edit values below — simulator pads/trims automatically.",
                 bg=C["DARK_BG"], fg=C["TEXT_SEC"],
                 font=("Consolas", 9)).pack(anchor="w", padx=8)

        canvas = tk.Canvas(parent, bg=C["DARK_BG"], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)

        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=6, pady=4)

        inner = tk.Frame(canvas, bg=C["DARK_BG"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win, width=canvas.winfo_width())

        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # Column headers
        hdr_row = tk.Frame(inner, bg=C["CARD_BG"])
        hdr_row.pack(fill="x", padx=4, pady=(4, 0))
        for txt, w in [("Field Name", 28), ("Size", 5), ("Value", 40)]:
            tk.Label(hdr_row, text=txt, bg=C["CARD_BG"], fg=C["ACCENT"],
                     font=("Consolas", 9, "bold"), width=w, anchor="w").pack(side="left", padx=4)

        for name, val in defaults.items():
            row = tk.Frame(inner, bg=C["PANEL_BG"])
            row.pack(fill="x", padx=4, pady=1)

            # Find size hint
            size_hint = ""
            for fname, fsize in (RESPONSE_HEADER_FIELDS + DBTRANS25_RESPONSE_FIELDS):
                if fname == name:
                    size_hint = str(fsize)
                    break
            if not size_hint:
                size_hint = str(len(str(val)))

            tk.Label(row, text=name, bg=C["PANEL_BG"], fg=C["ACCENT2"],
                     font=("Consolas", 9), width=28, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=size_hint, bg=C["PANEL_BG"], fg=C["TEXT_SEC"],
                     font=("Consolas", 9), width=5, anchor="w").pack(side="left", padx=2)

            var = tk.StringVar(value=str(val))
            var_dict[name] = var
            ent = tk.Entry(row, textvariable=var, bg=C["CARD_BG"], fg=C["TEXT_PRI"],
                           insertbackground=C["TEXT_PRI"], relief="flat",
                           font=("Consolas", 9), width=48)
            ent.pack(side="left", padx=4, pady=2, fill="x", expand=True)

            var.trace_add("write", lambda *a, n=name, v=var, d=store_dict: d.update({n: v.get()}))

    def _build_iso126_tab(self, parent):
        C = self._colors
        tk.Label(parent, text="ISO 126 — Overflow decisions + scoring server ID",
                 bg=C["DARK_BG"], fg=C["ACCENT"],
                 font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        tk.Label(parent, text="Fixed 100-byte overflow block.",
                 bg=C["DARK_BG"], fg=C["TEXT_SEC"],
                 font=("Consolas", 9)).pack(anchor="w", padx=8)

        fields_126 = [
            ("decisionType10",  "Decision Type 10 (32)",  32),
            ("decisionCode10",  "Decision Code 10 (32)",  32),
            ("scoringServerID", "Scoring Server ID (4)",    4),
            ("padding",         "Padding (32)",            32),
        ]

        inner = tk.Frame(parent, bg=C["DARK_BG"])
        inner.pack(fill="both", expand=True, padx=8, pady=8)

        for key, label, size in fields_126:
            row = tk.Frame(inner, bg=C["PANEL_BG"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=C["PANEL_BG"], fg=C["ACCENT2"],
                     font=("Consolas", 9), width=32, anchor="w").pack(side="left", padx=6)
            var = tk.StringVar(value=self.resp_iso126.get(key, " "*size))
            self.resp_vars_126[key] = var
            ent = tk.Entry(row, textvariable=var, bg=C["CARD_BG"], fg=C["TEXT_PRI"],
                           insertbackground=C["TEXT_PRI"], relief="flat",
                           font=("Consolas", 9), width=50)
            ent.pack(side="left", padx=4, pady=3)
            var.trace_add("write", lambda *a, k=key, v=var: self.resp_iso126.update({k: v.get()}))

    def _build_log_panel(self, parent):
        C = self._colors
        tk.Label(parent, text="📋  Activity Log",
                 bg=C["DARK_BG"], fg=C["ACCENT"],
                 font=("Consolas", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 2))

        self.log_text = scrolledtext.ScrolledText(
            parent, bg=C["PANEL_BG"], fg=C["TEXT_PRI"],
            font=("Consolas", 10), relief="flat",
            selectbackground=C["ACCENT"], selectforeground="#11111b",
            insertbackground=C["TEXT_PRI"], state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.log_text.tag_configure("ts",      foreground=C["TEXT_SEC"])
        self.log_text.tag_configure("info",    foreground=C["ACCENT2"])
        self.log_text.tag_configure("success", foreground=C["GREEN"])
        self.log_text.tag_configure("error",   foreground=C["RED"])
        self.log_text.tag_configure("warn",    foreground=C["YELLOW"])
        self.log_text.tag_configure("raw",     foreground="#fab387", font=("Consolas", 9))
        self.log_text.tag_configure("sep",     foreground="#45475a")

    # ─── SERVER LOGIC ───────────────────────────────────────────────────────

    def _start_server(self):
        ip   = self.ip_var.get().strip()
        port_str = self.port_var.get().strip()
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Port", f"Port must be a number 1–65535. Got: '{port_str}'")
            return

        if self.running:
            self._log("Server already running.", "warn")
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((ip, port))
            self.server_socket.listen(1)
            self.running = True
        except Exception as ex:
            messagebox.showerror("Bind Error", str(ex))
            self._log(f"Failed to bind: {ex}", "error")
            return

        self.server_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.server_thread.start()

        self._log(f"Server started on {ip}:{port}", "success")
        self.status_dot.config(text=f"●  LISTENING  {ip}:{port}",
                               fg=self._colors["GREEN"])
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

    def _stop_server(self):
        self.running = False
        if self.client_conn:
            try:
                self.client_conn.close()
            except:
                pass
            self.client_conn = None
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        self._log("Server stopped.", "warn")
        self.status_dot.config(text="●  STOPPED", fg=self._colors["RED"])
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _accept_loop(self):
        self._log("Waiting for connection…", "info")
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                conn, addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except Exception as ex:
                if self.running:
                    self._log(f"Accept error: {ex}", "error")
                break

            self.client_conn = conn
            self.client_addr = addr
            self._log(f"Client connected: {addr[0]}:{addr[1]}", "success")
            self.root.after(0, lambda a=addr: self.status_dot.config(
                text=f"●  CONNECTED  {a[0]}:{a[1]}",
                fg=self._colors["ACCENT"]))
            self._handle_client(conn, addr)
            self._log(f"Client disconnected: {addr[0]}:{addr[1]}", "warn")
            self.root.after(0, lambda: self.status_dot.config(
                text=f"●  LISTENING  {self.ip_var.get()}:{self.port_var.get()}",
                fg=self._colors["GREEN"]))

    def _handle_client(self, conn, addr):
        buffer = b""
        conn.settimeout(120.0)
        try:
            while self.running:
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    continue
                except Exception as ex:
                    self._log(f"Recv error: {ex}", "error")
                    break

                if not data:
                    break

                buffer += data
                # Try to decode and process
                try:
                    raw_str = buffer.decode("ascii", errors="replace")
                except:
                    raw_str = buffer.decode("latin-1", errors="replace")

                self._log("─" * 60, "sep")
                self._log(f"Received {len(data)} bytes from {addr[0]}:{addr[1]}", "info")
                self._log(f"RAW ↓\n{raw_str}", "raw")

                # Parse and display request
                parsed = parse_incoming_message(raw_str)
                self.root.after(0, lambda p=parsed, r=raw_str: self._display_request(p, r))

                # Build and send response
                response = self._build_response(parsed)
                try:
                    conn.sendall(response.encode("ascii"))
                    self._log(f"Response sent ({len(response)} bytes)", "success")
                    self._log(f"RAW RESPONSE ↓\n{response}", "raw")
                except Exception as ex:
                    self._log(f"Send error: {ex}", "error")

                buffer = b""
        except Exception as ex:
            self._log(f"Client handler error: {ex}", "error")
        finally:
            try:
                conn.close()
            except:
                pass
            self.client_conn = None

    # ─── RESPONSE BUILDER ───────────────────────────────────────────────────

    def _build_response(self, parsed_req: dict) -> str:
        """Build the full response string = ISO124 + ISO125 + ISO126."""

        # Collect current UI values
        h = {k: v.get() for k, v in self.resp_vars_124.items()} if self.resp_vars_124 else dict(self.resp_iso124)
        s = {k: v.get() for k, v in self.resp_vars_125.items()} if self.resp_vars_125 else dict(self.resp_iso125)
        x = {k: v.get() for k, v in self.resp_vars_126.items()} if self.resp_vars_126 else dict(self.resp_iso126)

        # Build ISO 125 (app data)
        iso125 = self._build_block(s, DBTRANS25_RESPONSE_FIELDS)

        # Build ISO 126 (overflow)
        iso126 = ""
        for key in ["decisionType10", "decisionCode10", "scoringServerID", "padding"]:
            sizes = {"decisionType10": 32, "decisionCode10": 32, "scoringServerID": 4, "padding": 32}
            val = x.get(key, "")
            iso126 += self._pad(val, sizes[key])

        app_data = iso125 + iso126
        app_data_len = len(app_data)

        # Update appDataLength in header
        h["appDataLength"] = str(app_data_len).zfill(8)

        # Build ISO 124 header
        ext_hdr = h.get("externalHeaderData", "DBTRAN251718532397  ")
        ext_hdr_len = len(ext_hdr.rstrip())
        ext_hdr_padded = self._pad(ext_hdr, 20)
        h["externalHeaderData"] = ext_hdr_padded
        h["extHeaderLength"] = str(20).zfill(4)

        iso124 = (
            self._pad(h.get("appDataLength", "00001069"),          8)  +
            self._pad(h.get("extHeaderLength", "0020"),            4)  +
            self._pad(h.get("tranCode", "200000102"),              9)  +
            self._pad(h.get("sourceApplication", "PMAX      "),   10)  +
            self._pad(h.get("destinationApplication","IDFCTANGO "),10)  +
            self._pad(h.get("errorCode", "0000000000"),           10)  +
            self._pad(h.get("filler", " "),                        1)  +
            ext_hdr_padded
        )

        return iso124 + app_data

    def _build_block(self, values: dict, field_defs: list) -> str:
        msg = ""
        for name, size in field_defs:
            val = str(values.get(name, ""))
            msg += self._pad(val, size)
        return msg

    def _pad(self, val: str, size: int) -> str:
        val = str(val)
        if len(val) > size:
            return val[:size]
        return val.ljust(size)

    # ─── REQUEST DISPLAY ────────────────────────────────────────────────────

    def _display_request(self, parsed: dict, raw: str):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.req_text.insert("end", f"Received: {ts}\n", "ts")
        self.req_text.insert("end", "─" * 70 + "\n", "section")

        sections = parsed.get("_sections", {})

        for section_name, section_data in sections.items():
            label = "HEADER (ISO 124)" if section_name == "header" else "REQUEST BODY (DBTrans25)"
            self.req_text.insert("end", f"\n▸ {label}\n", "section")
            for k, v in section_data.items():
                disp_v = v.strip() if isinstance(v, str) else str(v)
                self.req_text.insert("end", f"  {k:<40}", "field")
                self.req_text.insert("end", f"  [{disp_v}]\n", "value")

        self.req_text.insert("end", "\n─ RAW ─\n", "section")
        self.req_text.insert("end", raw + "\n", "raw")
        self.req_text.config(state="disabled")
        self.req_text.see("end")

    # ─── LOG ────────────────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info"):
        self.log_queue.put((message, level))

    def _poll_log_queue(self):
        try:
            while True:
                msg, level = self.log_queue.get_nowait()
                self._write_log(msg, level)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _write_log(self, message: str, level: str):
        self.log_text.config(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if level != "sep":
            self.log_text.insert("end", f"[{ts}] ", "ts")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.config(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ─── SAVE / LOAD RESPONSE TEMPLATE ──────────────────────────────────────

    def _save_response_template(self):
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(defaultextension=".json",
                                  filetypes=[("JSON", "*.json"), ("All", "*.*")],
                                  title="Save Response Template")
        if not path:
            return
        data = {
            "iso124": {k: v.get() for k, v in self.resp_vars_124.items()},
            "iso125": {k: v.get() for k, v in self.resp_vars_125.items()},
            "iso126": {k: v.get() for k, v in self.resp_vars_126.items()},
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._log(f"Response template saved: {path}", "success")

    def _load_response_template(self):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")],
                                title="Load Response Template")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as ex:
            messagebox.showerror("Load Error", str(ex))
            return

        for section, var_dict in [("iso124", self.resp_vars_124),
                                   ("iso125", self.resp_vars_125),
                                   ("iso126", self.resp_vars_126)]:
            for k, v in data.get(section, {}).items():
                if k in var_dict:
                    var_dict[k].set(v)
        self._log(f"Response template loaded: {path}", "success")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app = FalconSimulator(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app._stop_server(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
