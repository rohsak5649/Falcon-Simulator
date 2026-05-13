#!/usr/bin/env python3
"""
Euronet Falcon TCP Simulator
Developed by Rohan Sakhare
Internal Tool — IDFC First Bank / Euronet Integration

KEY FIX: appDataLength is 9 bytes (not 8), matching C++ vcDBTrans25Header definition.
         Response body is 1067 bytes (exact per vcDBTrans25Response field sizes).
         externalHeaderData length is variable — read from extHeaderLength field.
"""

import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import datetime
import json
import queue
import copy

# =============================================================================
# EXACT FIELD DEFINITIONS — Sourced directly from C++ FalconPlugin.cpp
# =============================================================================

# ── Inbound header (what we receive) ─────────────────────────────────────────
# C++ vcDBTrans25Header:  9+4+9+10+10+10+1+variable+17 = 70 + extHdrLen bytes
INBOUND_HEADER_FIXED = [
    ("appDataLength",           9),   # ← 9, NOT 8!
    ("extHeaderLength",         4),
    ("tranCode",                9),
    ("sourceApplication",      10),
    ("destinationApplication", 10),
    ("errorCode",              10),
    ("filler",                  1),
    # externalHeaderData length = int(extHeaderLength)  — parsed dynamically
    # RESERVED_01              17
]
INBOUND_FIXED_BEFORE_EXT = sum(s for _, s in INBOUND_HEADER_FIXED)   # = 53
INBOUND_RESERVED_AFTER  = 17

# ── Response body fields — EXACT sizes from C++ vcDBTrans25Response ───────────
# NOTE: error_code_2 is 2 bytes in C++ (typo in original — preserved faithfully)
RESPONSE_BODY_FIELDS = [
    ("response_record_version",  1),
    ("score_count",              2),

    ("score_name_1",  22), ("error_code_1",  4), ("score_1",  4),
    ("reason_1_1",     4), ("reason_1_2",    4), ("reason_1_3", 4),

    ("score_name_2",  22), ("error_code_2",  2), ("score_2",  4),  # error_code_2 = 2!
    ("reason_2_1",     4), ("reason_2_2",    4), ("reason_2_3", 4),

    ("score_name_3",  22), ("error_code_3",  4), ("score_3",  4),
    ("reason_3_1",     4), ("reason_3_2",    4), ("reason_3_3", 4),

    ("score_name_4",  22), ("error_code_4",  4), ("score_4",  4),
    ("reason_4_1",     4), ("reason_4_2",    4), ("reason_4_3", 4),

    ("score_name_5",  22), ("error_code_5",  4), ("score_5",  4),
    ("reason_5_1",     4), ("reason_5_2",    4), ("reason_5_3", 4),

    ("score_name_6",  22), ("error_code_6",  4), ("score_6",  4),
    ("reason_6_1",     4), ("reason_6_2",    4), ("reason_6_3", 4),

    ("score_name_7",  22), ("error_code_7",  4), ("score_7",  4),
    ("reason_7_1",     4), ("reason_7_2",    4), ("reason_7_3", 4),

    ("score_name_8",  22), ("error_code_8",  4), ("score_8",  4),
    ("reason_8_1",     4), ("reason_8_2",    4), ("reason_8_3", 4),

    ("segment_id_1",  8), ("segment_id_2",  8), ("segment_id_3", 8),
    ("filler1_1",     2), ("filler1_2",     4), ("filler1_3",    2),
    ("segment_id_4",  8), ("segment_id_5",  8), ("segment_id_6", 8),
    ("segment_id_7",  8), ("filler2_1",     4), ("filler2_2",    4),
    ("segment_id_8",  8), ("filler3",       4),

    ("decision_count", 2),

    ("decision_type_1",  32), ("decision_code_1",  32),
    ("decision_type_2",  32), ("decision_code_2",  32),
    ("decision_type_3",  32), ("decision_code_3",  32),
    ("decision_type_4",  32), ("decision_code_4",  32),
    ("decision_type_5",  32), ("decision_code_5",  32),
    ("decision_type_6",  32), ("decision_code_6",  32),
    ("decision_type_7",  32), ("decision_code_7",  32),
    ("decision_type_8",  32), ("decision_code_8",  32),
    ("decision_type_9",  32), ("decision_code_9",  32),
    ("decision_type_10", 32), ("decision_code_10", 32),

    ("scoring_server_id", 4),
]
RESPONSE_BODY_SIZE = sum(s for _, s in RESPONSE_BODY_FIELDS)  # = 1067

# ── Inbound DBTrans25 body fields (for display only) ─────────────────────────
DBTRANS25_REQUEST_FIELDS = [
    ("workflow",                        16), ("recordType",                    8),
    ("dataSpecificationVersion",         5), ("clientIdFromHeader",           16),
    ("recordCreationDate",               8), ("recordCreationTime",            6),
    ("recordCreationMilliseconds",       3), ("gmtOffset",                     6),
    ("customerIdFromHeader",            20), ("customerAcctNumber",           40),
    ("externalTransactionId",           32), ("pan",                          19),
    ("authPostFlag",                     1), ("cardPostalCode",                9),
    ("cardCountryCode",                  3), ("openDate",                      8),
    ("plasticIssueDate",                 8), ("plasticIssueType",              1),
    ("acctExpireDate",                   8), ("cardExpireDate",                8),
    ("dailyMerchandiseLimit",           10), ("dailyCashLimit",               10),
    ("customerGender",                   1), ("customerDateOfBirth",           8),
    ("numberOfCards",                    3), ("incomeOrCashBack",             10),
    ("cardType",                         1), ("cardUse",                       1),
    ("transactionDate",                  8), ("transactionTime",               6),
    ("transactionAmount",               13), ("transactionCurrencyCode",       3),
    ("transactionCurrencyConversionRate",13),("authDecisionCode",              1),
    ("transactionType",                  1), ("mcc",                           4),
    ("merchantPostalCode",               9), ("merchantCountryCode",           3),
    ("pinVerifyCode",                    1), ("cvvVerifyCode",                 1),
    ("posEntryMode",                     1), ("postDate",                      8),
    ("authPostMiscIndicator",            1), ("mismatchIndicator",             1),
    ("caseCreationIndicator",            1), ("userIndicator01",               1),
    ("userIndicator02",                  1), ("userData01",                   10),
    ("userData02",                      10), ("onUsMerchantId",               10),
    ("merchantDataProvided",             1), ("cardholderDataProvided",        1),
    ("externalScore1",                   4), ("externalScore2",                4),
    ("externalScore3",                   4), ("customerPresent",               1),
    ("atmOwner",                         1), ("randomDigits",                  2),
    ("portfolio",                       14), ("clientId",                     14),
    ("acquirerBin",                      6), ("merchantName",                 40),
    ("merchantCity",                    30), ("merchantState",                 3),
    ("caseSuppressionIndicator",         1), ("userIndicator03",               5),
    ("userIndicator04",                  5), ("userData03",                   15),
    ("userData04",                      20), ("userData05",                   40),
    ("realtimeRequest",                  1), ("padResponse",                   1),
    ("padActionExpireDate",              8), ("cardMasterAcctNumber",         19),
    ("cardAipStatic",                    1), ("cardAipDynamic",                1),
    ("RESERVED_01",                      1), ("cardAipVerify",                 1),
    ("cardAipRisk",                      1), ("cardAipIssuerAuthentication",   1),
    ("cardAipCombined",                  1), ("cardDailyLimitCode",            1),
    ("availableBalance",                13), ("availableDailyCashLimit",      13),
    ("availableDailyMerchandiseLimit",  13), ("atmHostMcc",                    4),
    ("atmProcessingCode",                6), ("atmCameraPresent",              1),
    ("cardPinType",                      1), ("cardMediaType",                 1),
    ("cvv2Present",                      1), ("cvv2Response",                  1),
    ("avsResponse",                      1), ("transactionCategory",           1),
    ("acquirerId",                      12), ("acquirerCountry",               3),
    ("terminalId",                      16), ("terminalType",                  1),
    ("terminalEntryCapability",          1), ("posConditionCode",              2),
    ("networkId",                        1), ("RESERVED_02",                   1),
    ("authExpireDateVerify",             1), ("authSecondaryVerify",           1),
    ("authBeneficiary",                  1), ("authResponseCode",              1),
    ("authReversalReason",               1), ("authCardIssuer",                1),
    ("terminalVerificationResults",     10), ("cardVerificationResults",      10),
    ("cryptogramValid",                  1), ("atcCard",                       5),
    ("atcHost",                          5), ("RESERVED_03",                   2),
    ("offlineLowerLimit",                2), ("offlineUpperLimit",             2),
    ("recurringAuthFrequency",           2), ("recurringAuthExpireDate",       8),
    ("linkedAcctType",                   1), ("cardIncentive",                 1),
    ("cardPinLength",                    2), ("cardPinSetDate",                8),
    ("processorAuthReasonCode",          5), ("standinAdvice",                 1),
    ("merchantId",                      16), ("cardOrder",                     1),
    ("cashbackAmount",                  13), ("userData06",                   13),
    ("userData07",                      40), ("paymentInstrumentId",          30),
    ("avsRequest",                       1), ("cvrOfflinePinVerificationPerformed", 1),
    ("cvrOfflinePinVerificationFailed",  1), ("cvrPinTryLimitExceeded",        1),
    ("posUnattended",                    1), ("posOffPremises",                1),
    ("posCardCapture",                   1), ("posSecurity",                   1),
    ("authId",                           6), ("userData08",                   10),
    ("userData09",                      10), ("userIndicator05",               1),
    ("userIndicator06",                  1), ("userIndicator07",               5),
    ("userIndicator08",                  5), ("modelControl1",                 1),
    ("modelControl2",                    1), ("modelControl3",                 1),
    ("modelControl4",                    1), ("RESERVED_04",                   3),
    ("segmentId1",                       6), ("segmentId2",                    6),
    ("segmentId3",                       6), ("segmentId4",                    6),
]

# =============================================================================
# DEFAULT RESPONSE VALUES
# =============================================================================

# ── Response header defaults ──────────────────────────────────────────────────
DEFAULT_RESP_HEADER = {
    # appDataLength (9 bytes) is AUTO-COMPUTED — always = RESPONSE_BODY_SIZE zero-padded to 9
    "extHeaderLength":        "0020",         # 4 bytes — must match externalHeaderData length
    "tranCode":               "200000102",    # 9 bytes
    "sourceApplication":      "PMAX",         # 10 bytes — padded to 10
    "destinationApplication": "IDFCTANGO",    # 10 bytes — padded to 10
    "errorCode":              "0000000000",   # 10 bytes
    "filler":                 " ",            # 1 byte
    "externalHeaderData":     "DBTRAN251718532397  ", # variable — 20 bytes here
    # RESERVED_01 (17 bytes) is AUTO-FILLED with spaces
}

# ── Response body defaults ────────────────────────────────────────────────────
DEFAULT_RESP_BODY = {
    "response_record_version": "4",
    "score_count":             " 1",
    "score_name_1":  "FFM.FRD.CARD          ",
    "error_code_1":  "   0",
    "score_1":       "  12",
    "reason_1_1":    "   2",
    "reason_1_2":    "  12",
    "reason_1_3":    "   3",
    "score_name_2":  " " * 22, "error_code_2": "  ", "score_2": "    ",
    "reason_2_1":    "    ",   "reason_2_2":   "    ", "reason_2_3": "    ",
    "score_name_3":  " " * 22, "error_code_3": "    ", "score_3": "    ",
    "reason_3_1":    "    ",   "reason_3_2":   "    ", "reason_3_3": "    ",
    "score_name_4":  " " * 22, "error_code_4": "    ", "score_4": "    ",
    "reason_4_1":    "    ",   "reason_4_2":   "    ", "reason_4_3": "    ",
    "score_name_5":  " " * 22, "error_code_5": "    ", "score_5": "    ",
    "reason_5_1":    "    ",   "reason_5_2":   "    ", "reason_5_3": "    ",
    "score_name_6":  " " * 22, "error_code_6": "    ", "score_6": "    ",
    "reason_6_1":    "    ",   "reason_6_2":   "    ", "reason_6_3": "    ",
    "score_name_7":  " " * 22, "error_code_7": "    ", "score_7": "    ",
    "reason_7_1":    "    ",   "reason_7_2":   "    ", "reason_7_3": "    ",
    "score_name_8":  " " * 22, "error_code_8": "    ", "score_8": "    ",
    "reason_8_1":    "    ",   "reason_8_2":   "    ", "reason_8_3": "    ",
    "segment_id_1":  "gid180a1", "segment_id_2": "        ", "segment_id_3": "        ",
    "filler1_1":     "  ",      "filler1_2":    "    ",      "filler1_3":    "  ",
    "segment_id_4":  "        ", "segment_id_5": "        ", "segment_id_6": "        ",
    "segment_id_7":  "        ", "filler2_1":    "    ",      "filler2_2":    "    ",
    "segment_id_8":  "        ", "filler3":      "    ",
    "decision_count": " 0",
    "decision_type_1":  " " * 32, "decision_code_1":  " " * 32,
    "decision_type_2":  " " * 32, "decision_code_2":  " " * 32,
    "decision_type_3":  " " * 32, "decision_code_3":  " " * 32,
    "decision_type_4":  " " * 32, "decision_code_4":  " " * 32,
    "decision_type_5":  " " * 32, "decision_code_5":  " " * 32,
    "decision_type_6":  " " * 32, "decision_code_6":  " " * 32,
    "decision_type_7":  " " * 32, "decision_code_7":  " " * 32,
    "decision_type_8":  " " * 32, "decision_code_8":  " " * 32,
    "decision_type_9":  " " * 32, "decision_code_9":  " " * 32,
    "decision_type_10": " " * 32, "decision_code_10": " " * 32,
    "scoring_server_id": "    ",
}

# =============================================================================
# UTILITIES
# =============================================================================

def fw(val: str, size: int, pad: str = " ", right_align: bool = False) -> str:
    """Fixed-width: pad or truncate to exact size. Default left-align + right-pad."""
    s = str(val) if val is not None else ""
    if len(s) >= size:
        return s[:size]
    if right_align:
        return s.rjust(size, pad)
    return s.ljust(size, pad)


def parse_fields(raw: str, fields: list) -> dict:
    result, pos = {}, 0
    for name, size in fields:
        result[name] = raw[pos: pos + size]
        pos += size
    return result


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class FalconSimulator:

    # ── Catppuccin Mocha palette ──────────────────────────────────────────────
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
    TEAL    = "#94e2d5"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Euronet Falcon TCP Simulator  —  Developed by Rohan Sakhare")
        self.root.geometry("1520x960")
        self.root.minsize(1100, 700)
        self.root.configure(bg=self.BG)

        self.server_socket  = None
        self.server_thread  = None
        self.running        = False
        self.client_conn    = None
        self.log_queue      = queue.Queue()
        self._bound_ip      = ""
        self._bound_port    = 0
        self._last_ext_hdr  = ""   # mirrors the ext header received — for echo-back

        # ── Active response dicts — ONLY updated by _save_response() ─────────
        self.active_hdr:  dict = copy.deepcopy(DEFAULT_RESP_HEADER)
        self.active_body: dict = copy.deepcopy(DEFAULT_RESP_BODY)

        # ── StringVar dicts (live UI editing — not sent until saved) ─────────
        self.svars_hdr:  dict = {}
        self.svars_body: dict = {}

        self._build_ui()
        self._poll_log()

    # =========================================================================
    # SAVE / UNSAVED STATE
    # =========================================================================

    def _save_response(self):
        for svars, active in (
            (self.svars_hdr,  self.active_hdr),
            (self.svars_body, self.active_body),
        ):
            for key, var in svars.items():
                active[key] = var.get()
        self._set_save_state(True)
        self._log("✅  Response saved — will be used for next request.", "success")

    def _set_save_state(self, saved: bool):
        if saved:
            self.save_indicator.config(text="● saved", fg=self.GREEN)
            self.save_resp_btn.config(bg="#40a02b", text="✅  Save Response")
        else:
            self.save_indicator.config(text="⚠ unsaved", fg=self.YELLOW)
            self.save_resp_btn.config(bg="#c07000", text="✅  Save Response *")

    def _on_field_changed(self, *_):
        self._set_save_state(False)

    # =========================================================================
    # BUILD RESPONSE — THE CORE FIX
    # =========================================================================

    def _build_response(self, echo_ext_hdr: str = "") -> str:
        """
        Assemble the complete fixed-length outbound Falcon message.

        Outbound layout (matching C++ vcDBTrans25Header for the RESPONSE direction):
          [9]  appDataLength       ← zero-padded, AUTO = RESPONSE_BODY_SIZE (1067)
          [4]  extHeaderLength     ← length of externalHeaderData field
          [9]  tranCode
          [10] sourceApplication
          [10] destinationApplication
          [10] errorCode
          [1]  filler
          [N]  externalHeaderData  ← N = int(extHeaderLength), padded to N
          [17] RESERVED_01         ← always 17 spaces
          ---- body (1067 bytes) ----

        Total = 9+4+9+10+10+10+1+N+17 + 1067  bytes
        """
        h = self.active_hdr
        b = self.active_body

        # externalHeaderData: if echo mode is on, use what we received
        ext_hdr_str = echo_ext_hdr if echo_ext_hdr else h.get("externalHeaderData", "")

        # extHeaderLength must match actual ext_hdr_str length
        ext_hdr_len = len(ext_hdr_str)
        ext_hdr_len_field = str(ext_hdr_len).zfill(4)   # 4-byte field, zero-padded

        # Build body
        body_parts = []
        for name, size in RESPONSE_BODY_FIELDS:
            val = b.get(name, "")
            body_parts.append(fw(val, size))
        body_str = "".join(body_parts)

        assert len(body_str) == RESPONSE_BODY_SIZE, \
            f"Body size mismatch: {len(body_str)} != {RESPONSE_BODY_SIZE}"

        # appDataLength = body size, 9 bytes, zero-padded (THE KEY FIX)
        app_data_len_field = str(RESPONSE_BODY_SIZE).zfill(9)   # "000001067"

        # Build header
        header = (
            app_data_len_field +                                           # [9]
            ext_hdr_len_field +                                            # [4]
            fw(h.get("tranCode",               "200000102"),       9) +    # [9]
            fw(h.get("sourceApplication",      "PMAX"),           10) +    # [10]
            fw(h.get("destinationApplication", "IDFCTANGO"),      10) +    # [10]
            fw(h.get("errorCode",              "0000000000"),     10) +    # [10]
            fw(h.get("filler",                 " "),               1) +    # [1]
            fw(ext_hdr_str,                               ext_hdr_len) +   # [N]
            fw("",                                                17)       # [17] RESERVED_01
        )

        full_msg = header + body_str
        return full_msg

    # =========================================================================
    # BUILD UI
    # =========================================================================

    def _build_ui(self):
        self._apply_styles()

        # ── Banner ────────────────────────────────────────────────────────────
        banner = tk.Frame(self.root, bg="#11111b", height=54)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner,
                 text="🦅  EURONET FALCON TCP SIMULATOR",
                 bg="#11111b", fg=self.ACCENT,
                 font=("Consolas", 14, "bold")
                 ).pack(side="left", padx=20, pady=12)
        tk.Label(banner,
                 text="Developed by Rohan Sakhare  |  IDFC First Bank / Euronet",
                 bg="#11111b", fg=self.TXT2,
                 font=("Consolas", 10)
                 ).pack(side="left", padx=4)
        # Size info badge
        tk.Label(banner,
                 text=f"  Body={RESPONSE_BODY_SIZE}B  appDataLen=9B  Header=9+4+9+10+10+10+1+N+17",
                 bg="#11111b", fg=self.TEAL,
                 font=("Consolas", 9)
                 ).pack(side="left", padx=12)
        self.dot = tk.Label(banner, text="●  STOPPED",
                            bg="#11111b", fg=self.RED,
                            font=("Consolas", 11, "bold"))
        self.dot.pack(side="right", padx=20)

        # ── Control bar ───────────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg=self.PANEL, height=58)
        ctrl.pack(fill="x")
        ctrl.pack_propagate(False)

        def lbl(t):
            return tk.Label(ctrl, text=t, bg=self.PANEL, fg=self.TXT2,
                            font=("Consolas", 10))
        def ent(var, w):
            return tk.Entry(ctrl, textvariable=var, width=w,
                            bg=self.CARD, fg=self.TXT,
                            insertbackground=self.TXT,
                            relief="flat", font=("Consolas", 11), bd=2)
        def btn(text, cmd, bg, fg="white", **kw):
            return tk.Button(ctrl, text=text, command=cmd,
                             bg=bg, fg=fg, font=("Consolas", 10, "bold"),
                             relief="flat", padx=12, cursor="hand2", **kw)

        lbl("Listen IP:").pack(side="left", padx=(16, 4), pady=16)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        ent(self.ip_var, 15).pack(side="left", padx=4)
        lbl("Port:").pack(side="left", padx=(10, 4))
        self.port_var = tk.StringVar(value="8070")
        ent(self.port_var, 7).pack(side="left", padx=4)

        self.start_btn = btn("▶  START", self._start_server, "#40a02b")
        self.start_btn.pack(side="left", padx=12)
        self.stop_btn  = btn("■  STOP",  self._stop_server,  self.CARD,
                             fg=self.RED, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        # Echo-header toggle
        self.echo_hdr_var = tk.BooleanVar(value=True)
        tk.Checkbutton(ctrl,
                       text="Echo ext header from request",
                       variable=self.echo_hdr_var,
                       bg=self.PANEL, fg=self.TEAL,
                       selectcolor=self.CARD,
                       activebackground=self.PANEL,
                       font=("Consolas", 9)
                       ).pack(side="left", padx=12)

        # Right side
        btn("🗑  Clear Log",     self._clear_log,      self.CARD, fg=self.TXT2
            ).pack(side="right", padx=12)
        btn("📂  Load Template", self._load_template,  self.CARD, fg=self.ACCENT2
            ).pack(side="right", padx=4)
        btn("💾  Save Template", self._save_template,  self.CARD, fg=self.ACCENT2
            ).pack(side="right", padx=4)

        tk.Frame(ctrl, bg=self.BORDER, width=2).pack(
            side="right", fill="y", pady=8, padx=8)

        self.save_resp_btn = btn("✅  Save Response", self._save_response, "#40a02b")
        self.save_resp_btn.pack(side="right", padx=6)

        self.save_indicator = tk.Label(ctrl, text="● saved", fg=self.GREEN,
                                       bg=self.PANEL, font=("Consolas", 9, "bold"))
        self.save_indicator.pack(side="right", padx=(0, 2))

        # ── Main paned area ───────────────────────────────────────────────────
        pane = tk.PanedWindow(self.root, orient="horizontal",
                              bg=self.BG, sashwidth=5, sashrelief="flat")
        pane.pack(fill="both", expand=True)

        left  = tk.Frame(pane, bg=self.BG)
        right = tk.Frame(pane, bg=self.BG)
        pane.add(left,  minsize=680)
        pane.add(right, minsize=380)

        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        t0 = tk.Frame(nb, bg=self.BG)
        nb.add(t0, text="  📥 Incoming Request  ")
        self._build_request_tab(t0)

        t1 = tk.Frame(nb, bg=self.BG)
        nb.add(t1, text="  📤 Response Header  ")
        self._build_header_editor_tab(t1)

        t2 = tk.Frame(nb, bg=self.BG)
        nb.add(t2, text="  📊 Response Body (Scores + Decisions)  ")
        self._build_body_editor_tab(t2)

        t3 = tk.Frame(nb, bg=self.BG)
        nb.add(t3, text="  📐 Field Size Reference  ")
        self._build_size_reference_tab(t3)

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
        s.configure("TFrame",     background=self.BG)
        s.configure("TScrollbar", background=self.CARD,
                    troughcolor=self.PANEL, arrowcolor=self.TXT2)

    # ── Request viewer ────────────────────────────────────────────────────────

    def _build_request_tab(self, parent):
        top = tk.Frame(parent, bg=self.BG)
        top.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(top, text="Last received request — parsed fields",
                 bg=self.BG, fg=self.TXT2, font=("Consolas", 9)).pack(side="left")
        tk.Button(top, text="🗑  Clear", command=self._clear_request,
                  bg=self.CARD, fg=self.RED, font=("Consolas", 9),
                  relief="flat", padx=8, cursor="hand2").pack(side="right")

        self.req_text = scrolledtext.ScrolledText(
            parent, bg=self.PANEL, fg=self.TXT, font=("Consolas", 10),
            relief="flat", selectbackground=self.ACCENT,
            selectforeground="#11111b", insertbackground=self.TXT,
            state="disabled")
        self.req_text.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        for tag, fg, bold in [
            ("sec",  self.ACCENT,  True),
            ("fld",  self.ACCENT2, False),
            ("val",  self.TXT,     False),
            ("raw",  self.YELLOW,  False),
            ("ts",   self.TXT2,    False),
            ("sep",  self.BORDER,  False),
            ("err",  self.RED,     False),
            ("info", self.TEAL,    False),
        ]:
            self.req_text.tag_configure(
                tag, foreground=fg,
                font=("Consolas", 10, "bold") if bold else ("Consolas", 10))

    def _clear_request(self):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")
        self.req_text.config(state="disabled")

    # ── Response header editor ────────────────────────────────────────────────

    def _build_header_editor_tab(self, parent):
        info = tk.Frame(parent, bg="#1a1a2e", pady=6)
        info.pack(fill="x", padx=8, pady=(6, 2))
        lines = [
            "  📐 RESPONSE HEADER LAYOUT (C++ vcDBTrans25Header):",
            f"  [9]  appDataLength         AUTO = {RESPONSE_BODY_SIZE} → '{str(RESPONSE_BODY_SIZE).zfill(9)}'   ← THE KEY FIX (was 8 bytes before)",
            "  [4]  extHeaderLength        AUTO from externalHeaderData length",
            "  [9]  tranCode",
            "  [10] sourceApplication",
            "  [10] destinationApplication",
            "  [10] errorCode",
            "  [1]  filler",
            "  [N]  externalHeaderData     N = extHeaderLength value",
            "  [17] RESERVED_01            AUTO = 17 spaces",
        ]
        for line in lines:
            tk.Label(info, text=line, bg="#1a1a2e", fg=self.TEAL,
                     font=("Consolas", 9), anchor="w").pack(fill="x", padx=4)

        note = tk.Frame(parent, bg="#2a2a3e", pady=3)
        note.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(note,
                 text="  ✏  Edit fields below, then click  ✅ Save Response  to apply."
                      "  appDataLength and RESERVED_01 are auto-computed.",
                 bg="#2a2a3e", fg=self.YELLOW, font=("Consolas", 9)
                 ).pack(side="left")

        # Scrollable editor
        canvas = tk.Canvas(parent, bg=self.BG, highlightthickness=0)
        sb     = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=6)

        inner  = tk.Frame(canvas, bg=self.BG)
        wid    = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(wid, width=canvas.winfo_width())

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(ev, lambda e, c=canvas: c.yview_scroll(
                -1*(e.delta//120) if e.num not in (4,5) else (-1 if e.num==4 else 1), "units"))

        # Column headers
        hdr_row = tk.Frame(inner, bg=self.CARD)
        hdr_row.pack(fill="x", padx=2, pady=(2, 1))
        for col, w in [("Field", 30), ("Size", 8), ("Active value", 28), ("Edit", 0)]:
            tk.Label(hdr_row, text=col, bg=self.CARD, fg=self.ACCENT,
                     font=("Consolas", 9, "bold"), width=w, anchor="w"
                     ).pack(side="left", padx=6, pady=3)

        # Auto fields (read-only display)
        auto_fields = [
            ("appDataLength",  9,
             f"AUTO = {str(RESPONSE_BODY_SIZE).zfill(9)}  (body={RESPONSE_BODY_SIZE} bytes, 9-char zero-padded)"),
            ("extHeaderLength", 4,
             "AUTO = len(externalHeaderData) zero-padded to 4"),
            ("RESERVED_01",   17,
             "AUTO = 17 spaces"),
        ]
        for fname, fsize, desc in auto_fields:
            row = tk.Frame(inner, bg="#0d0d1a")
            row.pack(fill="x", padx=2, pady=1)
            tk.Label(row, text=fname, bg="#0d0d1a", fg=self.TXT2,
                     font=("Consolas", 9), width=30, anchor="w").pack(side="left", padx=6)
            tk.Label(row, text=str(fsize), bg="#0d0d1a", fg=self.TXT2,
                     font=("Consolas", 9), width=8, anchor="w").pack(side="left", padx=2)
            tk.Label(row, text="", bg="#0d0d1a", fg=self.TXT2,
                     width=28, anchor="w").pack(side="left", padx=4)
            tk.Label(row, text=desc, bg="#0d0d1a", fg=self.TXT2,
                     font=("Consolas", 8, "italic")).pack(side="left", padx=8)

        # Editable header fields
        editable_hdr = [
            ("tranCode",               9,  "tranCode"),
            ("sourceApplication",     10,  "sourceApplication"),
            ("destinationApplication",10,  "destinationApplication"),
            ("errorCode",             10,  "errorCode"),
            ("filler",                 1,  "filler"),
            ("externalHeaderData",    20,  "externalHeaderData  ← length determines extHeaderLength"),
        ]
        for fname, fsize, label in editable_hdr:
            default_val = DEFAULT_RESP_HEADER.get(fname, "")
            active_val  = self.active_hdr.get(fname, default_val)

            row = tk.Frame(inner, bg=self.PANEL)
            row.pack(fill="x", padx=2, pady=1)

            tk.Label(row, text=label, bg=self.PANEL, fg=self.ACCENT2,
                     font=("Consolas", 9), width=30, anchor="w").pack(side="left", padx=6)
            tk.Label(row, text=str(fsize), bg=self.PANEL, fg=self.TXT2,
                     font=("Consolas", 9), width=8, anchor="w").pack(side="left", padx=2)
            tk.Label(row, text=repr(active_val), bg=self.PANEL, fg=self.GREEN,
                     font=("Consolas", 8), width=28, anchor="w").pack(side="left", padx=4)

            var = tk.StringVar(value=str(default_val))
            self.svars_hdr[fname] = var
            var.trace_add("write", self._on_field_changed)
            tk.Entry(row, textvariable=var,
                     bg=self.CARD, fg=self.TXT, insertbackground=self.TXT,
                     relief="flat", font=("Consolas", 9), width=60
                     ).pack(side="left", padx=4, pady=2, fill="x", expand=True)

    # ── Response body editor ──────────────────────────────────────────────────

    def _build_body_editor_tab(self, parent):
        info = tk.Frame(parent, bg="#1a1a2e", pady=4)
        info.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(info,
                 text=f"  📐 RESPONSE BODY — {RESPONSE_BODY_SIZE} bytes total  "
                      f"(exact per C++ vcDBTrans25Response)",
                 bg="#1a1a2e", fg=self.TEAL, font=("Consolas", 9, "bold")
                 ).pack(side="left", padx=4)
        tk.Label(info,
                 text="  ⚠  error_code_2 = 2 bytes (matches C++ typo in original)",
                 bg="#1a1a2e", fg=self.YELLOW, font=("Consolas", 9)
                 ).pack(side="left", padx=8)

        note = tk.Frame(parent, bg="#2a2a3e", pady=3)
        note.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(note,
                 text="  ✏  Edit values below, then click  ✅ Save Response.",
                 bg="#2a2a3e", fg=self.YELLOW, font=("Consolas", 9)
                 ).pack(side="left")

        canvas = tk.Canvas(parent, bg=self.BG, highlightthickness=0)
        sb     = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=6)

        inner  = tk.Frame(canvas, bg=self.BG)
        wid    = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(wid, width=canvas.winfo_width())

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(ev, lambda e, c=canvas: c.yview_scroll(
                -1*(e.delta//120) if e.num not in (4,5) else (-1 if e.num==4 else 1), "units"))

        hdr_row = tk.Frame(inner, bg=self.CARD)
        hdr_row.pack(fill="x", padx=2, pady=(2, 1))
        for col, w in [("Field", 30), ("Size", 6), ("Active", 26), ("Edit", 0)]:
            tk.Label(hdr_row, text=col, bg=self.CARD, fg=self.ACCENT,
                     font=("Consolas", 9, "bold"), width=w, anchor="w"
                     ).pack(side="left", padx=6, pady=3)

        # Group separator colours
        section_starts = {
            "response_record_version": ("📊 HEADER", self.ACCENT),
            "score_name_1": ("🏅 SCORE 1", self.ACCENT2),
            "score_name_2": ("🏅 SCORE 2", self.ACCENT2),
            "score_name_3": ("🏅 SCORE 3", self.ACCENT2),
            "score_name_4": ("🏅 SCORE 4", self.ACCENT2),
            "score_name_5": ("🏅 SCORE 5", self.ACCENT2),
            "score_name_6": ("🏅 SCORE 6", self.ACCENT2),
            "score_name_7": ("🏅 SCORE 7", self.ACCENT2),
            "score_name_8": ("🏅 SCORE 8", self.ACCENT2),
            "segment_id_1": ("📦 SEGMENTS + FILLERS", self.ORANGE),
            "decision_count": ("✅ DECISIONS", self.GREEN),
            "scoring_server_id": ("🖥 SERVER ID", self.TEAL),
        }

        offset = 0
        for name, size in RESPONSE_BODY_FIELDS:
            if name in section_starts:
                label, colour = section_starts[name]
                sep = tk.Frame(inner, bg=colour, height=1)
                sep.pack(fill="x", padx=2, pady=(6, 0))
                tk.Label(inner, text=f"  {label}", bg=self.BG, fg=colour,
                         font=("Consolas", 9, "bold"), anchor="w"
                         ).pack(fill="x", padx=4)

            default_val = DEFAULT_RESP_BODY.get(name, "")
            active_val  = self.active_body.get(name, default_val)
            is_warn     = (name == "error_code_2")   # highlight the 2-byte anomaly

            row_bg = "#1a1a2e" if is_warn else self.PANEL
            row = tk.Frame(inner, bg=row_bg)
            row.pack(fill="x", padx=2, pady=1)

            lbl_fg = self.YELLOW if is_warn else self.ACCENT2
            tk.Label(row, text=f"{name}  [offset {offset}]",
                     bg=row_bg, fg=lbl_fg,
                     font=("Consolas", 9), width=30, anchor="w").pack(side="left", padx=6)
            tk.Label(row, text=str(size), bg=row_bg, fg=self.TXT2,
                     font=("Consolas", 9), width=6, anchor="w").pack(side="left", padx=2)
            tk.Label(row, text=repr(active_val), bg=row_bg, fg=self.GREEN,
                     font=("Consolas", 8), width=26, anchor="w").pack(side="left", padx=4)

            var = tk.StringVar(value=str(default_val))
            self.svars_body[name] = var
            var.trace_add("write", self._on_field_changed)
            tk.Entry(row, textvariable=var,
                     bg=self.CARD, fg=self.TXT, insertbackground=self.TXT,
                     relief="flat", font=("Consolas", 9), width=60
                     ).pack(side="left", padx=4, pady=2, fill="x", expand=True)

            offset += size

    # ── Field size reference tab ──────────────────────────────────────────────

    def _build_size_reference_tab(self, parent):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        tk.Label(frame,
                 text="📐  Field Size Reference — sourced from C++ FalconPlugin.cpp",
                 bg=self.BG, fg=self.ACCENT, font=("Consolas", 11, "bold")
                 ).pack(anchor="w", pady=(0, 6))

        txt = scrolledtext.ScrolledText(
            frame, bg=self.PANEL, fg=self.TXT, font=("Consolas", 10),
            relief="flat", state="normal")
        txt.pack(fill="both", expand=True)

        lines = [
            "── OUTBOUND RESPONSE HEADER (C++ vcDBTrans25Header) ─────────────────────────",
            f"  appDataLength          [9]   AUTO = {str(RESPONSE_BODY_SIZE).zfill(9)}  ← 9 BYTES! (was 8 = BUG)",
            "  extHeaderLength        [4]   AUTO = len(externalHeaderData) zero-padded",
            "  tranCode               [9]",
            "  sourceApplication     [10]",
            "  destinationApplication[10]",
            "  errorCode             [10]",
            "  filler                 [1]",
            "  externalHeaderData    [N]   N = extHeaderLength value",
            "  RESERVED_01           [17]  AUTO = spaces",
            "",
            f"── OUTBOUND RESPONSE BODY (C++ vcDBTrans25Response) — {RESPONSE_BODY_SIZE} bytes total ────────",
        ]
        for name, size in RESPONSE_BODY_FIELDS:
            note = "  ⚠ 2 bytes (not 4!)" if name == "error_code_2" else ""
            lines.append(f"  {name:<35} [{size}]{note}")

        lines += [
            "",
            "── INBOUND HEADER (C++ vcDBTrans25Header inbound) ─────────────────────────",
            "  appDataLength          [9]",
            "  extHeaderLength        [4]",
            "  tranCode               [9]",
            "  sourceApplication     [10]",
            "  destinationApplication[10]",
            "  errorCode             [10]",
            "  filler                 [1]",
            "  externalHeaderData    [N]   N = int(extHeaderLength)",
            "  RESERVED_01           [17]",
        ]

        txt.insert("end", "\n".join(lines))
        txt.config(state="disabled")

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _build_log_panel(self, parent):
        tk.Label(parent, text="📋  Activity Log",
                 bg=self.BG, fg=self.ACCENT,
                 font=("Consolas", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 2))

        self.log_text = scrolledtext.ScrolledText(
            parent, bg=self.PANEL, fg=self.TXT, font=("Consolas", 10),
            relief="flat", selectbackground=self.ACCENT,
            selectforeground="#11111b", insertbackground=self.TXT,
            state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        for tag, fg in [
            ("ts",      self.TXT2),
            ("info",    self.ACCENT2),
            ("success", self.GREEN),
            ("error",   self.RED),
            ("warn",    self.YELLOW),
            ("raw",     self.ORANGE),
            ("sep",     self.BORDER),
        ]:
            self.log_text.tag_configure(tag, foreground=fg)

    # =========================================================================
    # SERVER
    # =========================================================================

    def _start_server(self):
        ip   = self.ip_var.get().strip()
        pstr = self.port_var.get().strip()
        try:
            port = int(pstr)
            assert 1 <= port <= 65535
        except Exception:
            messagebox.showerror("Invalid Port",
                                 f"Port must be 1–65535. Got: '{pstr}'")
            return
        if self.running:
            self._log("Server already running.", "warn")
            return
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

        self.running       = True
        self._bound_ip     = ip
        self._bound_port   = port
        self.server_thread = threading.Thread(target=self._accept_loop, daemon=True)
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
        self.client_conn   = None
        self.server_socket = None
        self._log("Server stopped.", "warn")
        self._set_dot("●  STOPPED", self.RED)
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def _set_dot(self, text: str, colour: str):
        self.root.after(0, lambda: self.dot.config(text=text, fg=colour))

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

    def _handle_client(self, conn: socket.socket, addr):
        buf = b""
        conn.settimeout(120.0)
        try:
            while self.running:
                try:
                    chunk = conn.recv(8192)
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

                self._log("─" * 60, "sep")
                self._log(f"Received {len(chunk)} bytes from {addr[0]}:{addr[1]}", "info")

                # Parse inbound header to get extHeaderLength
                ext_hdr = ""
                if len(raw) >= INBOUND_FIXED_BEFORE_EXT + 4:
                    try:
                        ext_hdr_len_str = raw[INBOUND_FIXED_BEFORE_EXT:
                                               INBOUND_FIXED_BEFORE_EXT + 4]
                        # Already read in INBOUND_HEADER_FIXED as extHeaderLength field
                        # but extHeaderLength is field index 1 (offset 9, size 4)
                        ext_len = int(raw[9:13].strip() or "0")
                        ext_hdr_start = INBOUND_FIXED_BEFORE_EXT
                        ext_hdr = raw[ext_hdr_start: ext_hdr_start + ext_len]
                        self._last_ext_hdr = ext_hdr
                    except Exception:
                        ext_hdr = self._last_ext_hdr

                hdr_d, body_d = self._parse_request(raw)
                self.root.after(0,
                    lambda h=hdr_d, b=body_d, r=raw:
                        self._display_request(h, b, r))

                # Build and send response
                echo_hdr = ext_hdr if self.echo_hdr_var.get() else ""
                resp = self._build_response(echo_ext_hdr=echo_hdr)

                self._log(f"RAW IN  (first 200): {raw[:200]!r}", "raw")

                try:
                    conn.sendall(resp.encode("ascii"))
                    self._log(
                        f"✅ Response sent — {len(resp)} bytes total  "
                        f"(header={len(resp)-RESPONSE_BODY_SIZE}B, body={RESPONSE_BODY_SIZE}B, "
                        f"appDataLen field='{str(RESPONSE_BODY_SIZE).zfill(9)}')",
                        "success")
                    self._log(f"RAW OUT (first 200): {resp[:200]!r}", "raw")
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
        min_size = INBOUND_FIXED_BEFORE_EXT
        if len(raw) < min_size:
            hdr["_error"] = f"Too short ({len(raw)} < {min_size} bytes)"
            return hdr, body

        # Parse fixed header fields
        pos = 0
        for name, size in INBOUND_HEADER_FIXED:
            hdr[name] = raw[pos: pos + size]
            pos += size

        # Read extHeaderLength to know how many bytes for externalHeaderData
        try:
            ext_len = int(hdr.get("extHeaderLength", "0").strip() or "0")
        except ValueError:
            ext_len = 0

        if len(raw) >= pos + ext_len:
            hdr["externalHeaderData"] = raw[pos: pos + ext_len]
            pos += ext_len
        else:
            hdr["externalHeaderData"] = raw[pos:]
            pos = len(raw)

        # RESERVED_01
        hdr["RESERVED_01"] = raw[pos: pos + INBOUND_RESERVED_AFTER]
        pos += INBOUND_RESERVED_AFTER

        # Body
        body = parse_fields(raw[pos:], DBTRANS25_REQUEST_FIELDS)
        return hdr, body

    def _display_request(self, hdr: dict, body: dict, raw: str):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.req_text.insert("end", f"Received: {ts}\n", "ts")
        self.req_text.insert("end", "─" * 70 + "\n", "sep")
        self.req_text.insert("end", "\n▸ INBOUND HEADER\n", "sec")

        offset = 0
        for name, size in INBOUND_HEADER_FIXED:
            val = hdr.get(name, "")
            self.req_text.insert("end", f"  [{offset:4d}+{size:2d}] {name:<28}", "fld")
            self.req_text.insert("end", f"  [{val}]\n", "val")
            offset += size

        # externalHeaderData
        ext_hdr = hdr.get("externalHeaderData", "")
        ext_len = len(ext_hdr)
        self.req_text.insert("end",
            f"  [{offset:4d}+{ext_len:2d}] externalHeaderData           ", "fld")
        self.req_text.insert("end", f"  [{ext_hdr}]\n", "val")
        offset += ext_len

        res = hdr.get("RESERVED_01", "")
        self.req_text.insert("end",
            f"  [{offset:4d}+17] RESERVED_01                 ", "fld")
        self.req_text.insert("end", f"  [{res}]\n", "val")

        if body:
            self.req_text.insert("end", "\n▸ BODY (DBTrans25)\n", "sec")
            for k, v in body.items():
                self.req_text.insert("end", f"  {k:<44}", "fld")
                self.req_text.insert("end", f"  [{v.strip()}]\n", "val")

        self.req_text.insert("end", "\n─ RAW (first 300 chars) ─\n", "sep")
        self.req_text.insert("end", raw[:300] + "\n", "raw")
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
    # SAVE / LOAD TEMPLATE
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
            "resp_header": copy.deepcopy(self.active_hdr),
            "resp_body":   copy.deepcopy(self.active_body),
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

        for section, var_dict, active in (
            ("resp_header", self.svars_hdr,  self.active_hdr),
            ("resp_body",   self.svars_body, self.active_body),
        ):
            for k, v in data.get(section, {}).items():
                active[k] = v
                if k in var_dict:
                    var_dict[k].set(v)

        self._set_save_state(True)
        self._log(f"Template loaded and applied: {path}", "success")


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
