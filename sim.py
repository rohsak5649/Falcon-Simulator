#!/usr/bin/env python3
"""
Euronet Falcon TCP Simulator
Developed by Rohan Sakhare
Internal Tool — IDFC First Bank / Euronet Integration

RESPONSE FIELD SIZES match vcDBTrans25Response from FalconPlugin.cpp exactly:
  - error_code_2 = 2  (NOT 4 — unique exception in score block 2)
  - All decisions (1-10) + scoring_server_id in one contiguous app-data block
  - No ISO 126 split — everything is one flat response body of 1067 bytes
  - extHeaderLength is auto-computed from actual externalHeaderData length
  - appDataLength is auto-computed from actual app-data length
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
# INBOUND HEADER FIELDS (from vcDBTrans25Header in FalconPlugin.cpp)
# Layout: {9,appDataLength}{4,extHeaderLength}{9,tranCode}{10,src}{10,dst}
#         {10,errorCode}{1,filler}{variable,externalHeaderData}{17,RESERVED_01}
# C++ reads: appDataLen=SubString(1,8), extHdrLen=SubString(9,4), tranCode=SubString(12,9) [1-based]
# =============================================================================
INBOUND_HEADER_FIELDS = [
    ("appDataLength",          9),
    ("extHeaderLength",        4),
    ("tranCode",               9),
    ("sourceApplication",     10),
    ("destinationApplication",10),
    ("errorCode",             10),
    ("filler",                 1),
    # externalHeaderData is variable (extHeaderLength chars) then RESERVED_01 (17)
]

# =============================================================================
# OUTBOUND RESPONSE FIELD DEFINITIONS
# Exactly matches vcDBTrans25Response in FalconPlugin.cpp
# CRITICAL: error_code_2 = 2 bytes (NOT 4 — this was the root cause bug)
# ALL decisions 1-10 + scoring_server_id are in one flat body (no ISO125/126 split)
# Total = 1067 bytes
# =============================================================================
RESPONSE_FIELDS = [
    # ── version + count
    ("response_record_version",  1),
    ("score_count",              2),

    # ── Score block 1  (22+4+4+4+4+4 = 42)
    ("score_name_1",  22), ("error_code_1",   4), ("score_1",   4),
    ("reason_1_1",     4), ("reason_1_2",     4), ("reason_1_3",4),

    # ── Score block 2  (22+2+4+4+4+4 = 40)  ← error_code_2 is 2, NOT 4!
    ("score_name_2",  22), ("error_code_2",   2), ("score_2",   4),
    ("reason_2_1",     4), ("reason_2_2",     4), ("reason_2_3",4),

    # ── Score blocks 3-8  (22+4+4+4+4+4 = 42 each)
    ("score_name_3",  22), ("error_code_3",   4), ("score_3",   4),
    ("reason_3_1",     4), ("reason_3_2",     4), ("reason_3_3",4),

    ("score_name_4",  22), ("error_code_4",   4), ("score_4",   4),
    ("reason_4_1",     4), ("reason_4_2",     4), ("reason_4_3",4),

    ("score_name_5",  22), ("error_code_5",   4), ("score_5",   4),
    ("reason_5_1",     4), ("reason_5_2",     4), ("reason_5_3",4),

    ("score_name_6",  22), ("error_code_6",   4), ("score_6",   4),
    ("reason_6_1",     4), ("reason_6_2",     4), ("reason_6_3",4),

    ("score_name_7",  22), ("error_code_7",   4), ("score_7",   4),
    ("reason_7_1",     4), ("reason_7_2",     4), ("reason_7_3",4),

    ("score_name_8",  22), ("error_code_8",   4), ("score_8",   4),
    ("reason_8_1",     4), ("reason_8_2",     4), ("reason_8_3",4),

    # ── Segment IDs + fillers
    ("segment_id_1",   8), ("segment_id_2",   8), ("segment_id_3", 8),
    ("filler1_1",      2), ("filler1_2",      4), ("filler1_3",    2),
    ("segment_id_4",   8), ("segment_id_5",   8), ("segment_id_6", 8),
    ("segment_id_7",   8), ("filler2_1",      4), ("filler2_2",    4),
    ("segment_id_8",   8), ("filler3",        4),

    # ── Decision block (count + 10 type/code pairs = 2+640 = 642)
    ("decision_count",  2),
    ("decision_type_1", 32), ("decision_code_1",  32),
    ("decision_type_2", 32), ("decision_code_2",  32),
    ("decision_type_3", 32), ("decision_code_3",  32),
    ("decision_type_4", 32), ("decision_code_4",  32),
    ("decision_type_5", 32), ("decision_code_5",  32),
    ("decision_type_6", 32), ("decision_code_6",  32),
    ("decision_type_7", 32), ("decision_code_7",  32),
    ("decision_type_8", 32), ("decision_code_8",  32),
    ("decision_type_9", 32), ("decision_code_9",  32),
    ("decision_type_10",32), ("decision_code_10", 32),

    # ── Scoring server ID
    ("scoring_server_id", 4),
]
# Total = 1+2 + 42 + 40 + 5*42 + 86 + 642 + 4 = 1067 bytes

# Inbound DBTrans25 body fields (for request display only)
DBTRANS25_REQUEST_FIELDS = [
    ("workflow",                         16), ("recordType",                     8),
    ("dataSpecificationVersion",          5), ("clientIdFromHeader",            16),
    ("recordCreationDate",                8), ("recordCreationTime",             6),
    ("recordCreationMilliseconds",        3), ("gmtOffset",                      6),
    ("customerIdFromHeader",             20), ("customerAcctNumber",            40),
    ("externalTransactionId",            32), ("pan",                           19),
    ("authPostFlag",                      1), ("cardPostalCode",                 9),
    ("cardCountryCode",                   3), ("openDate",                       8),
    ("plasticIssueDate",                  8), ("plasticIssueType",               1),
    ("acctExpireDate",                    8), ("cardExpireDate",                 8),
    ("dailyMerchandiseLimit",            10), ("dailyCashLimit",                10),
    ("customerGender",                    1), ("customerDateOfBirth",            8),
    ("numberOfCards",                     3), ("incomeOrCashBack",              10),
    ("cardType",                          1), ("cardUse",                        1),
    ("transactionDate",                   8), ("transactionTime",                6),
    ("transactionAmount",                13), ("transactionCurrencyCode",        3),
    ("transactionCurrencyConversionRate",13), ("authDecisionCode",               1),
    ("transactionType",                   1), ("mcc",                            4),
    ("merchantPostalCode",                9), ("merchantCountryCode",            3),
    ("pinVerifyCode",                     1), ("cvvVerifyCode",                  1),
    ("posEntryMode",                      1), ("postDate",                       8),
    ("authPostMiscIndicator",             1), ("mismatchIndicator",              1),
    ("caseCreationIndicator",             1), ("userIndicator01",                1),
    ("userIndicator02",                   1), ("userData01",                    10),
    ("userData02",                       10), ("onUsMerchantId",                10),
    ("merchantDataProvided",              1), ("cardholderDataProvided",         1),
    ("externalScore1",                    4), ("externalScore2",                 4),
    ("externalScore3",                    4), ("customerPresent",                1),
    ("atmOwner",                          1), ("randomDigits",                   2),
    ("portfolio",                        14), ("clientId",                      14),
    ("acquirerBin",                       6), ("merchantName",                  40),
    ("merchantCity",                     30), ("merchantState",                  3),
    ("caseSuppressionIndicator",          1), ("userIndicator03",                5),
    ("userIndicator04",                   5), ("userData03",                    15),
    ("userData04",                       20), ("userData05",                    40),
    ("realtimeRequest",                   1), ("padResponse",                    1),
    ("padActionExpireDate",               8), ("cardMasterAcctNumber",          19),
    ("cardAipStatic",                     1), ("cardAipDynamic",                 1),
    ("RESERVED_01",                       1), ("cardAipVerify",                  1),
    ("cardAipRisk",                       1), ("cardAipIssuerAuthentication",    1),
    ("cardAipCombined",                   1), ("cardDailyLimitCode",             1),
    ("availableBalance",                 13), ("availableDailyCashLimit",       13),
    ("availableDailyMerchandiseLimit",   13), ("atmHostMcc",                     4),
    ("atmProcessingCode",                 6), ("atmCameraPresent",               1),
    ("cardPinType",                       1), ("cardMediaType",                  1),
    ("cvv2Present",                       1), ("cvv2Response",                   1),
    ("avsResponse",                       1), ("transactionCategory",            1),
    ("acquirerId",                       12), ("acquirerCountry",                3),
    ("terminalId",                       16), ("terminalType",                   1),
    ("terminalEntryCapability",           1), ("posConditionCode",               2),
    ("networkId",                         1), ("RESERVED_02",                    1),
    ("authExpireDateVerify",              1), ("authSecondaryVerify",            1),
    ("authBeneficiary",                   1), ("authResponseCode",               1),
    ("authReversalReason",                1), ("authCardIssuer",                 1),
    ("terminalVerificationResults",      10), ("cardVerificationResults",       10),
    ("cryptogramValid",                   1), ("atcCard",                        5),
    ("atcHost",                           5), ("RESERVED_03",                    2),
    ("offlineLowerLimit",                 2), ("offlineUpperLimit",              2),
    ("recurringAuthFrequency",            2), ("recurringAuthExpireDate",        8),
    ("linkedAcctType",                    1), ("cardIncentive",                  1),
    ("cardPinLength",                     2), ("cardPinSetDate",                 8),
    ("processorAuthReasonCode",           5), ("standinAdvice",                  1),
    ("merchantId",                       16), ("cardOrder",                      1),
    ("cashbackAmount",                   13), ("userData06",                    13),
    ("userData07",                       40), ("paymentInstrumentId",           30),
    ("avsRequest",                        1), ("cvrOfflinePinVerificationPerformed",1),
    ("cvrOfflinePinVerificationFailed",   1), ("cvrPinTryLimitExceeded",         1),
    ("posUnattended",                     1), ("posOffPremises",                 1),
    ("posCardCapture",                    1), ("posSecurity",                    1),
    ("authId",                            6), ("userData08",                    10),
    ("userData09",                       10), ("userIndicator05",                1),
    ("userIndicator06",                   1), ("userIndicator07",                5),
    ("userIndicator08",                   5), ("modelControl1",                  1),
    ("modelControl2",                     1), ("modelControl3",                  1),
    ("modelControl4",                     1), ("RESERVED_04",                    3),
    ("segmentId1",                        6), ("segmentId2",                     6),
    ("segmentId3",                        6), ("segmentId4",                     6),
]

# =============================================================================
# OUTBOUND HEADER FIELDS (for editor — ISO 124 equivalent)
# Layout: appDataLength(8) + extHeaderLength(4) + tranCode(9) + sourceApp(10)
#         + destApp(10) + errorCode(10) + filler(1) + externalHeaderData(variable)
# appDataLength and extHeaderLength are AUTO-COMPUTED — shown read-only
# =============================================================================
HEADER_FIELDS_EDITOR = [
    ("appDataLength",           8),   # AUTO — equals len(app_data body)
    ("extHeaderLength",         4),   # AUTO — equals len(externalHeaderData)
    ("tranCode",                9),
    ("sourceApplication",      10),
    ("destinationApplication", 10),
    ("errorCode",              10),
    ("filler",                  1),
    ("externalHeaderData",     20),   # variable length — user edits this string
]

# =============================================================================
# DEFAULT VALUES
# =============================================================================

DEFAULT_HEADER = {
    "appDataLength":          "00001067",   # auto
    "extHeaderLength":        "0020",       # auto
    "tranCode":               "200000102",
    "sourceApplication":      "PMAX      ",
    "destinationApplication": "IDFCTANGO ",
    "errorCode":              "0000000000",
    "filler":                 " ",
    "externalHeaderData":     "DBTRAN251718532397  ",   # 20 chars default
}

DEFAULT_RESPONSE = {
    "response_record_version":  "4",
    "score_count":              " 1",
    # Score 1
    "score_name_1":  "FFM.FRD.CARD          ",
    "error_code_1":  "   0",
    "score_1":       "  12",
    "reason_1_1":    "   2",
    "reason_1_2":    "  12",
    "reason_1_3":    "   3",
    # Score 2  (error_code_2 = 2 bytes)
    "score_name_2":  " " * 22, "error_code_2": "  ", "score_2": "    ",
    "reason_2_1":    "    ",   "reason_2_2":   "    ", "reason_2_3": "    ",
    # Scores 3-8
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
    # Segments
    "segment_id_1":  "gid180a1", "segment_id_2": "        ", "segment_id_3": "        ",
    "filler1_1":     "  ",       "filler1_2":    "    ",     "filler1_3":    "  ",
    "segment_id_4":  "        ", "segment_id_5": "        ", "segment_id_6": "        ",
    "segment_id_7":  "        ", "filler2_1":    "    ",     "filler2_2":    "    ",
    "segment_id_8":  "        ", "filler3":      "    ",
    # Decisions (count=0, all blank)
    "decision_count":    " 0",
    "decision_type_1":   " " * 32, "decision_code_1":  " " * 32,
    "decision_type_2":   " " * 32, "decision_code_2":  " " * 32,
    "decision_type_3":   " " * 32, "decision_code_3":  " " * 32,
    "decision_type_4":   " " * 32, "decision_code_4":  " " * 32,
    "decision_type_5":   " " * 32, "decision_code_5":  " " * 32,
    "decision_type_6":   " " * 32, "decision_code_6":  " " * 32,
    "decision_type_7":   " " * 32, "decision_code_7":  " " * 32,
    "decision_type_8":   " " * 32, "decision_code_8":  " " * 32,
    "decision_type_9":   " " * 32, "decision_code_9":  " " * 32,
    "decision_type_10":  " " * 32, "decision_code_10": " " * 32,
    "scoring_server_id": "    ",
}

# =============================================================================
# UTILITIES
# =============================================================================

def fw(val: str, size: int) -> str:
    """Fixed-width: truncate or right-pad with spaces."""
    s = str(val) if val is not None else ""
    return s[:size] if len(s) >= size else s + " " * (size - len(s))


def parse_fields(raw: str, fields: list) -> dict:
    result, pos = {}, 0
    for name, size in fields:
        result[name] = raw[pos: pos + size]
        pos += size
    return result


def _verify_sizes():
    """Assert RESPONSE_FIELDS total == 1067."""
    total = sum(s for _, s in RESPONSE_FIELDS)
    assert total == 1067, f"RESPONSE_FIELDS total={total} expected 1067"


_verify_sizes()


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class FalconSimulator:

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
        self.root.geometry("1480x940")
        self.root.minsize(1100, 700)
        self.root.configure(bg=self.BG)

        self.server_socket = None
        self.server_thread = None
        self.running       = False
        self.client_conn   = None
        self.log_queue     = queue.Queue()
        self._bound_ip     = ""
        self._bound_port   = 0

        # ACTIVE dicts — only updated by _save_response()
        self.active_header:   dict = copy.deepcopy(DEFAULT_HEADER)
        self.active_response: dict = copy.deepcopy(DEFAULT_RESPONSE)

        # StringVar dicts (live UI — NOT used for sending)
        self.svars_header:   dict = {}
        self.svars_response: dict = {}

        self._build_ui()
        self._poll_log()

    # =========================================================================
    # ✅  SAVE RESPONSE
    # =========================================================================

    def _save_response(self):
        for svars, active in (
            (self.svars_header,   self.active_header),
            (self.svars_response, self.active_response),
        ):
            for key, var in svars.items():
                active[key] = var.get()
        self._set_save_state(True)
        self._log("✅  Response committed — next request will use these values.", "success")

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
    # BUILD RESPONSE  (reads active dicts only)
    # =========================================================================

    def _build_response(self) -> str:
        """
        Assembles the complete outbound fixed-length TCP message:

          Header  (72 bytes minimum, grows with externalHeaderData):
            appDataLength      [8]   ← AUTO: len(app_data), zero-padded
            extHeaderLength    [4]   ← AUTO: len(externalHeaderData), zero-padded
            tranCode           [9]
            sourceApplication  [10]
            destinationApp     [10]
            errorCode          [10]
            filler             [1]
            externalHeaderData [variable — user-defined string]

          App data  [1067 bytes — vcDBTrans25Response layout]:
            response body (RESPONSE_FIELDS) — single contiguous block

        Total = (8+4+9+10+10+10+1+len(extHdr)) + 1067
        """
        h = self.active_header
        r = self.active_response

        # ── App data (1067 bytes) ──────────────────────────────────────────
        app_data = "".join(fw(r.get(name, ""), size) for name, size in RESPONSE_FIELDS)
        app_len  = len(app_data)  # always 1067

        # ── External header data (variable, user-editable) ─────────────────
        ext_hdr_str = h.get("externalHeaderData", "DBTRAN251718532397  ")
        ext_hdr_len = len(ext_hdr_str)   # auto-compute from actual content

        # ── Header (8+4+9+10+10+10+1+ext_hdr_len) ─────────────────────────
        header = (
            str(app_len).zfill(8)  +                          # [8]  appDataLength
            str(ext_hdr_len).zfill(4) +                       # [4]  extHeaderLength (auto)
            fw(h.get("tranCode",               "200000102"), 9)  +   # [9]
            fw(h.get("sourceApplication",      "PMAX      "), 10) +  # [10]
            fw(h.get("destinationApplication", "IDFCTANGO "), 10) +  # [10]
            fw(h.get("errorCode",              "0000000000"), 10) +  # [10]
            fw(h.get("filler",                 " "),           1)  +  # [1]
            ext_hdr_str                                              # [variable]
        )
        return header + app_data

    # =========================================================================
    # UI
    # =========================================================================

    def _build_ui(self):
        self._apply_styles()

        # ── Banner ────────────────────────────────────────────────────────
        banner = tk.Frame(self.root, bg="#11111b", height=52)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text="🦅  EURONET FALCON TCP SIMULATOR",
                 bg="#11111b", fg=self.ACCENT,
                 font=("Consolas", 14, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(banner, text="Developed by Rohan Sakhare  |  IDFC First Bank",
                 bg="#11111b", fg=self.TXT2,
                 font=("Consolas", 10)).pack(side="left", padx=4)
        self.dot = tk.Label(banner, text="●  STOPPED",
                            bg="#11111b", fg=self.RED,
                            font=("Consolas", 11, "bold"))
        self.dot.pack(side="right", padx=20)

        # ── Control bar ───────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg=self.PANEL, height=58)
        ctrl.pack(fill="x")
        ctrl.pack_propagate(False)
        self._build_ctrl_bar(ctrl)

        # ── Main area ─────────────────────────────────────────────────────
        pane = tk.PanedWindow(self.root, orient="horizontal",
                              bg=self.BG, sashwidth=5, sashrelief="flat")
        pane.pack(fill="both", expand=True)
        left  = tk.Frame(pane, bg=self.BG)
        right = tk.Frame(pane, bg=self.BG)
        pane.add(left,  minsize=640)
        pane.add(right, minsize=380)

        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        t0 = tk.Frame(nb, bg=self.BG)
        nb.add(t0, text="  📥 Incoming Request  ")
        self._build_request_tab(t0)

        t1 = tk.Frame(nb, bg=self.BG)
        nb.add(t1, text="  📤 Header (ISO 124)  ")
        self._build_editor_tab(
            t1,
            "Outbound Header  —  appDataLength & extHeaderLength are AUTO-computed",
            DEFAULT_HEADER,
            HEADER_FIELDS_EDITOR,
            self.svars_header,
            auto_fields={"appDataLength", "extHeaderLength"},
            auto_note={
                "appDataLength":  "always len(app data body) = 1067",
                "extHeaderLength":"always len(externalHeaderData string)",
            },
        )

        t2 = tk.Frame(nb, bg=self.BG)
        nb.add(t2, text="  📊 Response Body (vcDBTrans25Response)  ")
        self._build_editor_tab(
            t2,
            "Response Body  —  1067 bytes total  |  ⚠ error_code_2 = 2 bytes (not 4)",
            DEFAULT_RESPONSE,
            RESPONSE_FIELDS,
            self.svars_response,
        )

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

    def _build_ctrl_bar(self, ctrl):
        def lbl(t):
            return tk.Label(ctrl, text=t, bg=self.PANEL, fg=self.TXT2, font=("Consolas", 10))
        def ent(var, w):
            return tk.Entry(ctrl, textvariable=var, width=w, bg=self.CARD, fg=self.TXT,
                            insertbackground=self.TXT, relief="flat", font=("Consolas", 11), bd=2)
        def btn(text, cmd, bg, fg="white", **kw):
            return tk.Button(ctrl, text=text, command=cmd, bg=bg, fg=fg,
                             font=("Consolas", 10, "bold"), relief="flat",
                             padx=12, cursor="hand2", **kw)

        lbl("Listen IP:").pack(side="left", padx=(16, 4), pady=16)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        ent(self.ip_var, 15).pack(side="left", padx=4)
        lbl("Port:").pack(side="left", padx=(10, 4))
        self.port_var = tk.StringVar(value="8070")
        ent(self.port_var, 7).pack(side="left", padx=4)

        self.start_btn = btn("▶  START", self._start_server, "#40a02b")
        self.start_btn.pack(side="left", padx=12)
        self.stop_btn = btn("■  STOP", self._stop_server, self.CARD, fg=self.RED, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        # Right side
        btn("🗑  Clear Log",    self._clear_log,     self.CARD, fg=self.TXT2).pack(side="right", padx=12)
        btn("📂  Load Template", self._load_template, self.CARD, fg=self.ACCENT2).pack(side="right", padx=4)
        btn("💾  Save Template", self._save_template, self.CARD, fg=self.ACCENT2).pack(side="right", padx=4)
        tk.Frame(ctrl, bg=self.BORDER, width=2).pack(side="right", fill="y", pady=8, padx=8)

        self.save_resp_btn = btn("✅  Save Response", self._save_response, "#40a02b")
        self.save_resp_btn.pack(side="right", padx=6)
        self.save_indicator = tk.Label(ctrl, text="● saved", fg=self.GREEN, bg=self.PANEL,
                                       font=("Consolas", 9, "bold"))
        self.save_indicator.pack(side="right", padx=(0, 2))

    # ── Request viewer tab ────────────────────────────────────────────────────

    def _build_request_tab(self, parent):
        top = tk.Frame(parent, bg=self.BG)
        top.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(top, text="Last received inbound request — parsed fields",
                 bg=self.BG, fg=self.TXT2, font=("Consolas", 9)).pack(side="left")
        tk.Button(top, text="🗑  Clear", command=self._clear_request,
                  bg=self.CARD, fg=self.RED, font=("Consolas", 9),
                  relief="flat", padx=8, cursor="hand2").pack(side="right")

        self.req_text = scrolledtext.ScrolledText(
            parent, bg=self.PANEL, fg=self.TXT, font=("Consolas", 10), relief="flat",
            selectbackground=self.ACCENT, selectforeground="#11111b",
            insertbackground=self.TXT, state="disabled")
        self.req_text.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        for tag, fg, bold in [
            ("sec", self.ACCENT,  True), ("fld", self.ACCENT2, False),
            ("val", self.TXT,     False), ("raw", self.YELLOW,  False),
            ("ts",  self.TXT2,    False), ("sep", self.BORDER,  False),
            ("err", self.RED,     False),
        ]:
            self.req_text.tag_configure(
                tag, foreground=fg,
                font=("Consolas", 10, "bold") if bold else ("Consolas", 10))

    def _clear_request(self):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")
        self.req_text.config(state="disabled")

    # ── Generic editor tab ────────────────────────────────────────────────────

    def _build_editor_tab(self, parent, title: str, defaults: dict,
                          fields: list, var_dict: dict,
                          auto_fields: set = None, auto_note: dict = None):
        auto_fields = auto_fields or set()
        auto_note   = auto_note   or {}

        hf = tk.Frame(parent, bg=self.BG)
        hf.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(hf, text=title, bg=self.BG, fg=self.ACCENT,
                 font=("Consolas", 10, "bold")).pack(side="left")

        note = tk.Frame(parent, bg="#2a2a3e", pady=4)
        note.pack(fill="x", padx=8, pady=(2, 6))
        tk.Label(note,
                 text="  ✏  Edit values, then click  ✅ Save Response  to apply.  "
                      "Fields are fixed-width — auto padded/trimmed on send.",
                 bg="#2a2a3e", fg=self.YELLOW, font=("Consolas", 9)).pack(side="left")

        canvas = tk.Canvas(parent, bg=self.BG, highlightthickness=0)
        sb     = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=6, pady=2)

        inner  = tk.Frame(canvas, bg=self.BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _resize(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())

        inner.bind("<Configure>", _resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll( 1, "units"))

        # Column headers
        hdr = tk.Frame(inner, bg=self.CARD)
        hdr.pack(fill="x", padx=2, pady=(2, 1))
        for col, w in [("Field Name", 30), ("Size", 6), ("Active Value (sent)", 24), ("Edit Value", 0)]:
            tk.Label(hdr, text=col, bg=self.CARD, fg=self.ACCENT,
                     font=("Consolas", 9, "bold"), width=w, anchor="w"
                     ).pack(side="left", padx=6, pady=3)

        # Which active dict to pull "current active" value from
        if var_dict is self.svars_header:
            active_src = self.active_header
        else:
            active_src = self.active_response

        for name, size in fields:
            default_val = defaults.get(name, "")
            active_val  = active_src.get(name, default_val)
            is_auto     = name in auto_fields
            is_special  = (name == "error_code_2")  # highlight the unusual field

            row_bg = "#252535" if is_special else self.PANEL
            row = tk.Frame(inner, bg=row_bg)
            row.pack(fill="x", padx=2, pady=1)

            name_color = self.YELLOW if is_special else self.ACCENT2
            tk.Label(row, text=name, bg=row_bg, fg=name_color,
                     font=("Consolas", 9, "bold") if is_special else ("Consolas", 9),
                     width=30, anchor="w").pack(side="left", padx=6)

            size_color = self.ORANGE if is_special else self.TXT2
            tk.Label(row, text=str(size), bg=row_bg, fg=size_color,
                     font=("Consolas", 9, "bold") if is_special else ("Consolas", 9),
                     width=6, anchor="w").pack(side="left", padx=2)

            # Active value column
            if is_auto:
                active_lbl_text = auto_note.get(name, "(auto)")
                active_lbl_fg   = self.TXT2
            else:
                active_lbl_text = repr(active_val)
                active_lbl_fg   = self.GREEN
            tk.Label(row, text=active_lbl_text, bg=row_bg, fg=active_lbl_fg,
                     font=("Consolas", 8), width=24, anchor="w"
                     ).pack(side="left", padx=4)

            var = tk.StringVar(value=str(default_val))
            var_dict[name] = var

            if is_auto:
                tk.Label(row, text="← auto-computed on every send",
                         bg=row_bg, fg=self.TXT2,
                         font=("Consolas", 9, "italic")).pack(side="left", padx=8)
            else:
                var.trace_add("write", self._on_field_changed)
                entry_bg = "#3a3a52" if is_special else self.CARD
                entry = tk.Entry(row, textvariable=var, bg=entry_bg, fg=self.TXT,
                                 insertbackground=self.TXT, relief="flat",
                                 font=("Consolas", 9), width=60)
                entry.pack(side="left", padx=4, pady=2, fill="x", expand=True)
                if is_special:
                    tk.Label(row, text="← ⚠ SIZE=2", bg=row_bg, fg=self.ORANGE,
                             font=("Consolas", 8, "bold")).pack(side="left", padx=2)

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _build_log_panel(self, parent):
        hdr = tk.Frame(parent, bg=self.BG)
        hdr.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(hdr, text="📋  Activity Log",
                 bg=self.BG, fg=self.ACCENT,
                 font=("Consolas", 11, "bold")).pack(side="left")

        # Stats bar
        self.stats_var = tk.StringVar(value="TX: 0  |  RX: 0  |  Bytes sent: 0")
        tk.Label(hdr, textvariable=self.stats_var,
                 bg=self.BG, fg=self.TXT2, font=("Consolas", 8)).pack(side="right", padx=4)
        self._tx_count = 0
        self._rx_count = 0
        self._bytes_sent = 0

        self.log_text = scrolledtext.ScrolledText(
            parent, bg=self.PANEL, fg=self.TXT, font=("Consolas", 10), relief="flat",
            selectbackground=self.ACCENT, selectforeground="#11111b",
            insertbackground=self.TXT, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        for tag, fg in [
            ("ts", self.TXT2), ("info", self.ACCENT2), ("success", self.GREEN),
            ("error", self.RED), ("warn", self.YELLOW), ("raw", self.ORANGE),
            ("sep", self.BORDER), ("proto", self.TEAL),
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
            messagebox.showerror("Invalid Port", f"Port must be 1–65535. Got: '{pstr}'")
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

        self.running     = True
        self._bound_ip   = ip
        self._bound_port = port
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
            self._set_dot(f"●  LISTENING  {self._bound_ip}:{self._bound_port}", self.GREEN)

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

                self._rx_count += 1
                self._log("─" * 60, "sep")
                self._log(f"Received {len(chunk)} bytes from {addr[0]}:{addr[1]}", "info")
                self._log(f"RAW IN ↓\n{raw}", "raw")

                # Parse inbound header
                hdr_d, body_d = self._parse_request(raw)
                self.root.after(0, lambda h=hdr_d, b=body_d, r=raw:
                                self._display_request(h, b, r))

                # Build and send response
                resp = self._build_response()
                try:
                    conn.sendall(resp.encode("ascii"))
                    self._tx_count  += 1
                    self._bytes_sent += len(resp)
                    self._log(f"Response sent ({len(resp)} bytes)", "success")
                    self._log(f"RAW OUT ↓\n{resp}", "raw")
                    # Log key header fields for quick verification
                    self._log(
                        f"  appDataLength={resp[0:8]}  extHdrLen={resp[8:12]}"
                        f"  tranCode={resp[12:21]}", "proto")
                    self.root.after(0, lambda: self.stats_var.set(
                        f"TX: {self._tx_count}  |  RX: {self._rx_count}"
                        f"  |  Bytes sent: {self._bytes_sent}"))
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
    # PARSE + DISPLAY INBOUND REQUEST
    # =========================================================================

    def _parse_request(self, raw: str) -> tuple:
        """
        Parse inbound header using vcDBTrans25Header layout (C++ 1-based):
          SubString(1,9)  = appDataLength      [9]
          SubString(10,4) = extHeaderLength     [4]
          SubString(14,9) = tranCode            [9]
          SubString(23,10)= sourceApplication   [10]
          SubString(33,10)= destApplication     [10]
          SubString(43,10)= errorCode           [10]
          SubString(53,1) = filler              [1]
          SubString(54,N) = externalHeaderData  [N=extHeaderLen]
          SubString(54+N,17) = RESERVED_01      [17]
        Then body starts at: 54 + N + 17 = 71 + N
        """
        hdr, body = {}, {}
        if len(raw) < 71:
            hdr["_error"] = f"Message too short ({len(raw)} bytes)"
            return hdr, body
        try:
            hdr["appDataLength"]         = raw[0:9]
            hdr["extHeaderLength"]       = raw[9:13]
            hdr["tranCode"]              = raw[13:22]
            hdr["sourceApplication"]     = raw[22:32]
            hdr["destinationApplication"]= raw[32:42]
            hdr["errorCode"]             = raw[42:52]
            hdr["filler"]               = raw[52:53]
            try:
                ext_len = int(raw[9:13].strip())
            except ValueError:
                ext_len = 0
            hdr["externalHeaderData"] = raw[53: 53 + ext_len]
            hdr["RESERVED_01"]        = raw[53 + ext_len: 53 + ext_len + 17]
            body_start = 53 + ext_len + 17
            body_raw   = raw[body_start:]
            body = parse_fields(body_raw, DBTRANS25_REQUEST_FIELDS)
        except Exception as ex:
            hdr["_error"] = f"Parse error: {ex}"
        return hdr, body

    def _display_request(self, hdr: dict, body: dict, raw: str):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.req_text.insert("end", f"Received: {ts}\n", "ts")
        self.req_text.insert("end", "─" * 70 + "\n", "sep")
        self.req_text.insert("end", "\n▸ INBOUND HEADER\n", "sec")
        for k, v in hdr.items():
            if k.startswith("_"):
                self.req_text.insert("end", f"  {v}\n", "err")
                continue
            self.req_text.insert("end", f"  {k:<44}", "fld")
            self.req_text.insert("end", f"  [{v.strip()}]\n", "val")
        if body:
            self.req_text.insert("end", "\n▸ BODY  (DBTrans25 Request)\n", "sec")
            for k, v in body.items():
                self.req_text.insert("end", f"  {k:<44}", "fld")
                self.req_text.insert("end", f"  [{v.strip()}]\n", "val")
        self.req_text.insert("end", "\n─ RAW ─\n", "sep")
        self.req_text.insert("end", raw[:2000] + ("…" if len(raw) > 2000 else "") + "\n", "raw")
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
            "header":   copy.deepcopy(self.active_header),
            "response": copy.deepcopy(self.active_response),
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
            ("header",   self.svars_header,   self.active_header),
            ("response", self.svars_response, self.active_response),
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
