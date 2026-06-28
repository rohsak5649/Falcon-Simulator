#!/usr/bin/env python3
"""
Euronet Falcon TCP Simulator
Developed by Rohan Sakhare
Internal Tool — IDFC First Bank / Euronet Integration
"""

import socket
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import datetime
import json
import queue
import copy

# =============================================================================
# FIELD DEFINITIONS
# =============================================================================

# FIXED: corrected inbound header field sizes to match actual incoming message
# Old sizes were wrong (extHeaderLength=10, appDataLength=10, sourceApplication=8, etc.)
# New correct sizes: appDataLength=8, extHeaderLength=4, sourceApplication=10,
#                    destinationApplication=10, externalHeaderData=20, RESERVED_01=17
# Total = 8+4+9+10+10+10+1+20+17 = 89 bytes
INBOUND_HEADER_FIELDS = [
    ("appDataLength",           8),
    ("extHeaderLength",         4),
    ("tranCode",                9),
    ("sourceApplication",      10),
    ("destinationApplication", 10),
    ("errorCode",              10),
    ("filler",                  1),
    ("externalHeaderData",     20),
    ("RESERVED_01",            17),   # trailing reserved bytes in inbound header
]
INBOUND_HEADER_SIZE = sum(s for _, s in INBOUND_HEADER_FIELDS)  # 89

# ISO 125 outbound fields  (total = 969 bytes)
ISO125_FIELDS = [
    ("responseRecordVersion",    1),
    ("scoreCount",               2),
    ("scoreName1",  22), ("errorCode1",  4), ("score1",  4),
    ("reason11",     4), ("reason12",    4), ("reason13",4),
    ("scoreName2",  22), ("errorCode2",  4), ("score2",  4),
    ("reason21",     4), ("reason22",    4), ("reason23",4),
    ("scoreName3",  22), ("errorCode3",  4), ("score3",  4),
    ("reason31",     4), ("reason32",    4), ("reason33",4),
    ("scoreName4",  22), ("errorCode4",  4), ("score4",  4),
    ("reason41",     4), ("reason42",    4), ("reason43",4),
    ("scoreName5",  22), ("errorCode5",  4), ("score5",  4),
    ("reason51",     4), ("reason52",    4), ("reason53",4),
    ("scoreName6",  22), ("errorCode6",  4), ("score6",  4),
    ("reason61",     4), ("reason62",    4), ("reason63",4),
    ("scoreName7",  22), ("errorCode7",  4), ("score7",  4),
    ("reason71",     4), ("reason72",    4), ("reason73",4),
    ("scoreName8",  22), ("errorCode8",  4), ("score8",  4),
    ("reason81",     4), ("reason82",    4), ("reason83",4),
    ("segmentID1",   8), ("segmentID2",  8), ("segmentID3", 8),
    ("filler11",     2), ("filler12",    4), ("filler13",   2),
    ("segmentID4",   8), ("segmentID5",  8), ("segmentID6", 8),
    ("segmentID7",   8), ("filler21",    4), ("filler22",   4),
    ("segmentID8",   8), ("filler3",     4),
    ("decisionCount", 2),
    ("decisionType1", 32), ("decisionCode1",  32),
    ("decisionType2", 32), ("decisionCode2",  32),
    ("decisionType3", 32), ("decisionCode3",  32),
    ("decisionType4", 32), ("decisionCode4",  32),
    ("decisionType5", 32), ("decisionCode5",  32),
    ("decisionType6", 32), ("decisionCode6",  32),
    ("decisionType7", 32), ("decisionCode7",  32),
    ("decisionType8", 32), ("decisionCode8",  32),
    ("decisionType9",  32),
]

# ISO 126 outbound fields  (total = 100 bytes)
ISO126_FIELDS = [
    ("decisionCode9",   32),
    ("decisionType10",  32),
    ("decisionCode10",  32),
    ("scoringServerID",  4),
]

# ISO 124 outbound field order/sizes for editor display  (72 bytes total)
ISO124_FIELDS = [
    ("appDataLength",           8),   # auto-computed — shown read-only
    ("extHeaderLength",         4),
    ("tranCode",                9),
    ("sourceApplication",      10),
    ("destinationApplication", 10),
    ("errorCode",              10),
    ("filler",                  1),
    ("externalHeaderData",     20),   # echoed from inbound request
    ("RESERVED_01",            17),
]

# =============================================================================
# EXT10 FIELD DEFINITIONS
# =============================================================================

# Inbound EXT10 request body fields
EXT10_REQUEST_FIELDS = [
    ("workflow",                      16), ("recordType",                  8),
    ("dataSpecificationVersion",       5), ("clientIdFromHeader",         16),
    ("recordCreationDate",             8), ("recordCreationTime",          6),
    ("recordCreationMilliseconds",     3), ("gmtOffset",                   6),
    ("customerIdFromHeader",          20), ("customerAcctNumber",         40),
    ("externalTransactionId",         32), ("serviceId",                  19),
    ("transactionDate",                8), ("transactionTime",             6),
    ("validity",                       4), ("entityType",                  4),
    ("extSource",                     48), ("notificationName",           48),
    ("notificationStatus",            10),
    ("score1",   4), ("score2",   4), ("score3",   4),
    ("userData01",  4), ("userData02",  4), ("userData03",  4), ("userData04",  4),
    ("userData05",  4), ("userData06",  8), ("userData07",  8), ("userData08",  8),
    ("userData09",  8), ("userData10",  8), ("userData11",  8),
    ("userData12", 16), ("userData13", 16), ("userData14", 16), ("userData15", 16),
    ("userData16", 16), ("userData17", 16),
    ("userData18", 32), ("userData19", 32), ("userData20", 32), ("userData21", 32),
    ("userData22", 32), ("userData23", 32), ("userData24", 32), ("userData25", 32),
    ("userData26", 32), ("userData27", 32),
    ("userData28", 64), ("userData29", 64), ("userData30", 64), ("userData31", 64),
    ("userData32", 64),
    ("userData33", 255), ("userData34", 255),
]

# EXT10 response body fields
EXT10_RESPONSE_FIELDS = [
    ("workflow",                      16), ("recordType",                  8),
    ("dataSpecificationVersion",       5), ("clientIdFromHeader",         16),
    ("recordCreationDate",             8), ("recordCreationTime",          6),
    ("recordCreationMilliseconds",     3), ("gmtOffset",                   6),
    ("customerIdFromHeader",          20), ("customerAcctNumber",         40),
    ("externalTransactionId",         32), ("Response",                    2),
]
EXT10_RESPONSE_BODY_SIZE = sum(s for _, s in EXT10_RESPONSE_FIELDS)  # 162

# =============================================================================
# DBTRANS25 REQUEST FIELDS
# =============================================================================

# Inbound DBTrans25 body fields (display only)
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

# Derived sizes — must come AFTER field lists are defined
INBOUND_BODY_SIZE        = sum(s for _, s in DBTRANS25_REQUEST_FIELDS)
INBOUND_PREFIX_LEN       = 2    # leading framing bytes sent by the client
# Fixed header bytes BEFORE externalHeaderData (appDataLength+extHeaderLength+tranCode+...+filler)
INBOUND_FIXED_BEFORE_EXT = sum(s for n, s in INBOUND_HEADER_FIELDS
                                if n not in ("externalHeaderData", "RESERVED_01"))  # 52
# RESERVED_01 bytes that follow externalHeaderData
INBOUND_RESERVED_SIZE    = sum(s for n, s in INBOUND_HEADER_FIELDS
                                if n == "RESERVED_01")                               # 17
# Default total (with extHeaderLength=20); re-computed per-message in _handle_client
INBOUND_TOTAL_SIZE = (INBOUND_PREFIX_LEN + INBOUND_FIXED_BEFORE_EXT
                      + 20 + INBOUND_RESERVED_SIZE + INBOUND_BODY_SIZE)

# tranCode prefixes used to distinguish request types
# Adjust TRANCODE_EXT10 if your actual EXT10 tranCode differs
TRANCODE_DBTRAN25 = "100000101"
TRANCODE_EXT10    = "100000110"

# =============================================================================
# DEFAULT RESPONSE VALUES — DBTRAN25
# =============================================================================

DEFAULT_ISO124 = {
    "appDataLength":          "00001069",   # auto-recalculated on every send
    "extHeaderLength":        "0020",
    "tranCode":               "200000102",
    "sourceApplication":      "PMAX      ",
    "destinationApplication": "IDFCTANGO ",
    "errorCode":              "0000000000",
    "filler":                 " ",
    "externalHeaderData":     "DBTRAN251718532397  ",  # echoed from request at send time
}

DEFAULT_ISO125 = {
    "responseRecordVersion":  "4",
    "scoreCount":             " 1",
    "scoreName1":  "FFM.FRD.CARD          ",
    "errorCode1":  "   0",  "score1":   "  12",
    "reason11":    "   2",  "reason12": "  12",  "reason13": "   3",
    "scoreName2":  " " * 22, "errorCode2": "    ", "score2": "    ",
    "reason21":    "    ",   "reason22":   "    ", "reason23": "    ",
    "scoreName3":  " " * 22, "errorCode3": "    ", "score3": "    ",
    "reason31":    "    ",   "reason32":   "    ", "reason33": "    ",
    "scoreName4":  " " * 22, "errorCode4": "    ", "score4": "    ",
    "reason41":    "    ",   "reason42":   "    ", "reason43": "    ",
    "scoreName5":  " " * 22, "errorCode5": "    ", "score5": "    ",
    "reason51":    "    ",   "reason52":   "    ", "reason53": "    ",
    "scoreName6":  " " * 22, "errorCode6": "    ", "score6": "    ",
    "reason61":    "    ",   "reason62":   "    ", "reason63": "    ",
    "scoreName7":  " " * 22, "errorCode7": "    ", "score7": "    ",
    "reason71":    "    ",   "reason72":   "    ", "reason73": "    ",
    "scoreName8":  " " * 22, "errorCode8": "    ", "score8": "    ",
    "reason81":    "    ",   "reason82":   "    ", "reason83": "    ",
    "segmentID1":  "gid180a1", "segmentID2": "        ", "segmentID3": "        ",
    "filler11":    "  ",      "filler12":   "    ",      "filler13":   "  ",
    "segmentID4":  "        ", "segmentID5": "        ", "segmentID6": "        ",
    "segmentID7":  "        ", "filler21":   "    ",      "filler22":   "    ",
    "segmentID8":  "        ", "filler3":    "    ",
    "decisionCount": " 0",
    "decisionType1":  " " * 32, "decisionCode1":  " " * 32,
    "decisionType2":  " " * 32, "decisionCode2":  " " * 32,
    "decisionType3":  " " * 32, "decisionCode3":  " " * 32,
    "decisionType4":  " " * 32, "decisionCode4":  " " * 32,
    "decisionType5":  " " * 32, "decisionCode5":  " " * 32,
    "decisionType6":  " " * 32, "decisionCode6":  " " * 32,
    "decisionType7":  " " * 32, "decisionCode7":  " " * 32,
    "decisionType8":  " " * 32, "decisionCode8":  " " * 32,
    "decisionType9":  " " * 32,
}

DEFAULT_ISO126 = {
    "decisionCode9":   " " * 32,
    "decisionType10":  " " * 32,
    "decisionCode10":  " " * 32,
    "scoringServerID": "    ",
}

# =============================================================================
# DEFAULT RESPONSE VALUES — EXT10
# =============================================================================

DEFAULT_EXT10_RESPONSE = {
    "workflow":                   " " * 16,
    "recordType":                 " " * 8,
    "dataSpecificationVersion":   "00001",
    "clientIdFromHeader":         " " * 16,
    "recordCreationDate":         " " * 8,
    "recordCreationTime":         " " * 6,
    "recordCreationMilliseconds": " " * 3,
    "gmtOffset":                  " " * 6,
    "customerIdFromHeader":       " " * 20,
    "customerAcctNumber":         " " * 40,
    "externalTransactionId":      " " * 32,
    "Response":                   "00",      # 2 bytes — "00" = success
}

# =============================================================================
# UTILITIES
# =============================================================================

def fw(val: str, size: int) -> str:
    """Pad right with spaces or truncate to exact fixed width."""
    s = str(val) if val is not None else ""
    if len(s) >= size:
        return s[:size]
    return s + (" " * (size - len(s)))


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

    # ── Apple Vision Pro / Futuristic palette ─────────────────────────────
    BG      = "#06060f"   # deep space void
    PANEL   = "#0b0b1e"   # dark glass panel
    CARD    = "#111130"   # elevated card
    CARD2   = "#181848"   # lighter elevated card
    ACCENT  = "#2e86ff"   # electric blue
    ACCENT2 = "#bf5af2"   # apple purple
    TXT     = "#f0f0ff"   # near-white with blue tint
    TXT2    = "#5a5a80"   # muted blue-grey
    GREEN   = "#30d158"   # apple system green
    RED     = "#ff453a"   # apple system red
    YELLOW  = "#ffd60a"   # apple system yellow
    BORDER  = "#1a1a50"   # subtle glowing border
    ORANGE  = "#ff9f0a"   # apple system orange
    BLUE    = "#0a84ff"   # deep electric blue
    TEAL    = "#5ac8fa"   # vision pro teal
    # Font choices: prefer Apple system fonts, fall back gracefully
    FONT_MONO  = ("SF Mono",   10)
    FONT_MONO9 = ("SF Mono",    9)
    FONT_UI    = ("SF Pro Display", 10)
    FONT_TITLE = ("SF Pro Display", 14, "bold")

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🦅  Euronet Falcon TCP Simulator  —  Developed by Rohan Sakhare")
        self.root.geometry("1480x960")
        self.root.minsize(1100, 720)
        self.root.configure(bg=self.BG)

        self.server_socket = None
        self.server_thread = None
        self.running       = False
        self.client_conn   = None
        self.log_queue     = queue.Queue()
        self._bound_ip     = ""
        self._bound_port   = 0

        # ── Response delay (seconds) — 0 = immediate ──────────────────────────
        self.response_delay_seconds: float = 0.0

        # ── Last received externalHeaderData + extHeaderLength for echo-back ─
        # Updated every time a request is parsed; used in _build_response()
        self._last_external_header_data: str = "DBTRAN251718532397  "
        self._last_ext_header_length:    str = "0020"   # echoed dynamically from request

        # ── Last detected request type ────────────────────────────────────────
        # "DBTRAN25" or "EXT10" — set in _handle_client, read in _build_response
        self._last_request_type: str = "DBTRAN25"

        # ── ACTIVE response dicts ─────────────────────────────────────────────
        # ONLY updated by _save_response(). _build_response() reads ONLY these.
        self.active124:         dict = copy.deepcopy(DEFAULT_ISO124)
        self.active125:         dict = copy.deepcopy(DEFAULT_ISO125)
        self.active126:         dict = copy.deepcopy(DEFAULT_ISO126)
        self.active_ext10_resp: dict = copy.deepcopy(DEFAULT_EXT10_RESPONSE)

        # ── UI StringVar dicts (live editing, NOT used for sending) ───────────
        self.svars124:         dict = {}
        self.svars125:         dict = {}
        self.svars126:         dict = {}
        self.svars_ext10_resp: dict = {}

        self._build_ui()
        self._poll_log()

    # =========================================================================
    # ✅  SAVE RESPONSE  — the ONE place active dicts are updated
    # =========================================================================

    def _save_response(self):
        """
        Snapshot every StringVar into the active dicts.
        _build_response() will use these values for the next send.
        """
        for svars, active in (
            (self.svars124,         self.active124),
            (self.svars125,         self.active125),
            (self.svars126,         self.active126),
            (self.svars_ext10_resp, self.active_ext10_resp),
        ):
            for key, var in svars.items():
                active[key] = var.get()

        self._set_save_state(True)
        self._log("✅  Response saved — next request will use updated values.", "success")

    def _reset_response(self):
        """
        Reset ALL response fields (ISO 124 / 125 / 126 + EXT10) back to their
        hardcoded DEFAULT_* values.  Both the UI StringVars and the active
        dicts (used for sending) are restored in one step.
        """
        # ── Restore active dicts ──────────────────────────────────────────────
        self.active124          = copy.deepcopy(DEFAULT_ISO124)
        self.active125          = copy.deepcopy(DEFAULT_ISO125)
        self.active126          = copy.deepcopy(DEFAULT_ISO126)
        self.active_ext10_resp  = copy.deepcopy(DEFAULT_EXT10_RESPONSE)

        # ── Update every StringVar so the UI reflects the reset values ────────
        for default, svars in (
            (DEFAULT_ISO124,         self.svars124),
            (DEFAULT_ISO125,         self.svars125),
            (DEFAULT_ISO126,         self.svars126),
            (DEFAULT_EXT10_RESPONSE, self.svars_ext10_resp),
        ):
            for key, var in svars.items():
                var.set(default.get(key, ""))

        self._set_save_state(True)
        self._log("🔄  Response reset to defaults — all fields restored.", "warn")

    def _apply_delay(self):
        """Read the delay Entry, validate, and store in self.response_delay_seconds."""
        raw = self.delay_var.get().strip()
        try:
            val = float(raw)
            if val < 0:
                raise ValueError("negative")
        except ValueError:
            # Reset Entry to last good value
            self.delay_var.set(f"{self.response_delay_seconds:g}")
            messagebox.showwarning(
                "Invalid Delay",
                f"Please enter a non-negative number (e.g. 0, 1, 2.5).\nGot: '{raw}'")
            return
        self.response_delay_seconds = val
        if val == 0:
            self._delay_indicator.config(text="INSTANT", fg=self.GREEN)
        else:
            self._delay_indicator.config(
                text=f"{val:g}s delay", fg=self.YELLOW)
        self._log(
            f"⏱  Response delay set to {val:g} second(s)."
            + ("  (immediate responses)" if val == 0 else ""),
            "info")

    def _set_immediate(self):
        """Reset delay to 0 (immediate response)."""
        self.response_delay_seconds = 0.0
        self.delay_var.set("0")
        self._delay_indicator.config(text="INSTANT", fg=self.GREEN)
        self._log("⚡  Response delay cleared — responses are now immediate.", "success")

    def _set_save_state(self, saved: bool):
        if saved:
            self.save_indicator.config(text="  saved", fg=self.GREEN)
            self.save_resp_btn.config(bg=self.ACCENT, text="  Save Response")
        else:
            self.save_indicator.config(text="  unsaved", fg=self.YELLOW)
            self.save_resp_btn.config(bg="#8b4500", text="  Save Response  *")

    def _on_field_changed(self, *_):
        self._set_save_state(False)

    # =========================================================================
    # BUILD RESPONSE
    # =========================================================================

    def _build_response(self) -> str:
        """
        Assemble the complete outbound message.

        If the last received request was EXT10:
          → Build an EXT10 response (ISO-124 header + EXT10 body, 162 bytes).
          → Response body is built from EXT10_RESPONSE_FIELDS + active_ext10_resp.
          → The first 11 fields (workflow … externalTransactionId) are echoed
            verbatim from the inbound EXT10 request body.
          → Only 'Response' (2 bytes, default "00") is user-configurable.

        Otherwise (DBTran25):
          → ISO 124 fixed part  = 8+4+9+10+10+10+1 = 52 bytes
          → externalHeaderData  = dynamic (= inbound extHeaderLength, e.g. 20 or 28)
          → ISO 125             = 969 bytes
          → ISO 126             = 100 bytes

        externalHeaderData and extHeaderLength are always echoed from the inbound request.
        """
        # extHeaderLength: echoed directly from inbound (zero-padded, 4 chars)
        echo_ext_hdr_len = fw(self._last_ext_header_length, 4)
        # externalHeaderData: echo the EXACT bytes received from inbound.
        echo_ext_hdr = self._last_external_header_data   # exact bytes, dynamic length

        if self._last_request_type == "EXT10":
            # ── EXT10 response ────────────────────────────────────────────────
            resp_body = self.active_ext10_resp
            body_str  = "".join(fw(resp_body.get(n, ""), sz) for n, sz in EXT10_RESPONSE_FIELDS)
            app_len_8 = str(len(body_str)).zfill(8)

            s124 = self.active124
            iso124 = (
                app_len_8 +
                echo_ext_hdr_len +
                fw(s124.get("tranCode",               "200000110"), 9) +
                fw(s124.get("sourceApplication",      "PMAX      "), 10) +
                fw(s124.get("destinationApplication", "IDFCTANGO "), 10) +
                fw(s124.get("errorCode",              "0000000000"), 10) +
                fw(s124.get("filler",                 " "),          1) +
                echo_ext_hdr
            )
            return iso124 + body_str

        # ── DBTran25 response (original path, unchanged) ──────────────────────
        s124 = self.active124
        s125 = self.active125
        s126 = self.active126

        iso125 = "".join(fw(s125.get(n, ""), sz) for n, sz in ISO125_FIELDS)
        iso126 = "".join(fw(s126.get(n, ""), sz) for n, sz in ISO126_FIELDS)

        app_data  = iso125 + iso126
        app_len_8 = str(len(app_data)).zfill(8)

        iso124 = (
            app_len_8 +                                                      # [8]
            echo_ext_hdr_len +                                               # [4] dynamic
            fw(s124.get("tranCode",               "200000102"),        9) +   # [9]
            fw(s124.get("sourceApplication",      "PMAX      "),      10) +   # [10]
            fw(s124.get("destinationApplication", "IDFCTANGO "),      10) +   # [10]
            fw(s124.get("errorCode",              "0000000000"),      10) +   # [10]
            fw(s124.get("filler",                 " "),                1) +   # [1]
            echo_ext_hdr                                               # [dynamic] echoed
        )
        return iso124 + app_data

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

    def _build_ui(self):
        self._apply_styles()

        # -- Vision Pro Banner -----------------------------------------------
        banner = tk.Frame(self.root, bg="#04040e", height=64)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Frame(banner, bg=self.ACCENT, width=4).pack(side="left", fill="y")
        tk.Label(banner, text="   EURONET FALCON TCP SIMULATOR",
                 bg="#04040e", fg=self.TXT,
                 font=("Helvetica Neue", 15, "bold")).pack(side="left", pady=18)
        badge = tk.Frame(banner, bg="#0a2040", padx=10, pady=3)
        badge.pack(side="left", padx=16, pady=18)
        tk.Label(badge, text="v1.0.3",
                 bg="#0a2040", fg=self.TEAL,
                 font=("Helvetica Neue", 9, "bold")).pack()
        tk.Label(banner, text="Developed by rsakhare@euronetworldwide.com",
                 bg="#04040e", fg=self.TXT2,
                 font=("Helvetica Neue", 9)).pack(side="left", padx=4)
        self._status_frame = tk.Frame(banner, bg="#04040e")
        self._status_frame.pack(side="right", padx=24)
        self.dot = tk.Label(self._status_frame, text="  STOPPED",
                            bg="#04040e", fg=self.RED,
                            font=("Helvetica Neue", 12, "bold"))
        self.dot.pack(pady=20)
        tk.Frame(self.root, bg=self.ACCENT, height=1).pack(fill="x")

        # -- Control bar row 1 -----------------------------------------------
        ctrl = tk.Frame(self.root, bg=self.PANEL, height=62)
        ctrl.pack(fill="x")
        ctrl.pack_propagate(False)

        def lbl(t):
            return tk.Label(ctrl, text=t, bg=self.PANEL, fg=self.TXT2,
                            font=("Helvetica Neue", 10))
        def ent(var, w):
            return tk.Entry(ctrl, textvariable=var, width=w,
                            bg=self.CARD2, fg=self.TXT,
                            insertbackground=self.TEAL,
                            relief="flat", font=("Helvetica Neue", 11),
                            highlightthickness=1,
                            highlightcolor=self.ACCENT,
                            highlightbackground=self.BORDER)
        def btn(text, cmd, bg, fg="white", **kw):
            return tk.Button(ctrl, text=text, command=cmd,
                             bg=bg, fg=fg,
                             font=("Helvetica Neue", 10, "bold"),
                             relief="flat", padx=14,
                             activebackground=self.CARD2,
                             activeforeground=self.TXT,
                             cursor="hand2", **kw)

        lbl("Listen IP:").pack(side="left", padx=(16, 4), pady=16)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        ent(self.ip_var, 15).pack(side="left", padx=4)
        lbl("Port:").pack(side="left", padx=(10, 4))
        self.port_var = tk.StringVar(value="8070")
        ent(self.port_var, 7).pack(side="left", padx=4)

        self.start_btn = btn("  START", self._start_server, self.ACCENT)
        self.start_btn.pack(side="left", padx=12)
        self.stop_btn = btn("  STOP", self._stop_server, self.CARD,
                            fg=self.RED, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        # -- Response Delay controls -----------------------------------------
        tk.Frame(ctrl, bg=self.BORDER, width=1).pack(
            side="left", fill="y", pady=10, padx=(16, 6))
        lbl("  Delay:").pack(side="left", padx=(4, 2))
        self.delay_var = tk.StringVar(value="0")
        self._delay_entry = tk.Entry(
            ctrl, textvariable=self.delay_var, width=5,
            bg=self.CARD2, fg=self.ACCENT,
            insertbackground=self.TEAL,
            relief="flat", font=("Helvetica Neue", 11, "bold"),
            highlightthickness=1,
            highlightcolor=self.ACCENT,
            highlightbackground=self.BORDER,
            justify="center")
        self._delay_entry.pack(side="left", padx=2)
        lbl("sec").pack(side="left", padx=(0, 4))
        self._delay_entry.bind("<Return>",   lambda e: self._apply_delay())
        self._delay_entry.bind("<FocusOut>", lambda e: self._apply_delay())
        btn("Set", self._apply_delay, "#1a3a1a", fg=self.GREEN
            ).pack(side="left", padx=2)
        btn("Immediate", self._set_immediate, "#0a1e40", fg=self.TEAL
            ).pack(side="left", padx=(2, 6))
        self._delay_indicator = tk.Label(
            ctrl, text="INSTANT",
            bg=self.PANEL, fg=self.GREEN,
            font=("Helvetica Neue", 9, "bold"))
        self._delay_indicator.pack(side="left", padx=(0, 4))

        # Right side (pack right-to-left)
        btn("Clear Log",    self._clear_log,     self.CARD,    fg=self.TXT2
            ).pack(side="right", padx=10)
        btn("Load Template", self._load_template, "#0a1a30", fg=self.TEAL
            ).pack(side="right", padx=3)
        btn("Save Template", self._save_template, "#0a1a30", fg=self.TEAL
            ).pack(side="right", padx=3)

        # -- Save Response bar (always visible, Vision Pro style) ------------
        tk.Frame(self.root, bg=self.BORDER, height=1).pack(fill="x")
        ctrl2 = tk.Frame(self.root, bg="#08081c", height=48)
        ctrl2.pack(fill="x")
        ctrl2.pack_propagate(False)
        tk.Frame(ctrl2, bg=self.GREEN, width=3).pack(side="left", fill="y")
        self.save_indicator = tk.Label(ctrl2, text="  saved", fg=self.GREEN,
                                       bg="#08081c",
                                       font=("Helvetica Neue", 10, "bold"))
        self.save_indicator.pack(side="left", padx=(14, 6), pady=12)
        self.save_resp_btn = tk.Button(
            ctrl2, text="  Save Response", command=self._save_response,
            bg=self.ACCENT, fg="white",
            font=("Helvetica Neue", 11, "bold"),
            relief="flat", padx=22,
            activebackground=self.BLUE,
            activeforeground="white",
            cursor="hand2")
        self.save_resp_btn.pack(side="left", padx=8, pady=8)
        tk.Button(ctrl2, text="  Reset", command=self._reset_response,
                  bg=self.CARD, fg=self.YELLOW,
                  font=("Helvetica Neue", 10, "bold"),
                  relief="flat", padx=14,
                  activebackground=self.CARD2,
                  activeforeground=self.YELLOW,
                  cursor="hand2"
                  ).pack(side="left", padx=4, pady=8)
        tk.Label(ctrl2,
                 text="  Edit fields in ISO 124 / 125 / 126 or EXT10 tabs, "
                      "then click Save Response to apply for the next request.",
                 bg="#08081c", fg=self.TXT2,
                 font=("Helvetica Neue", 9)
                 ).pack(side="left", padx=12)
        tk.Frame(self.root, bg=self.BORDER, height=1).pack(fill="x")

        # ── Main paned area ───────────────────────────────────────────────────
        pane = tk.PanedWindow(self.root, orient="horizontal",
                              bg=self.BG, sashwidth=5, sashrelief="flat")
        pane.pack(fill="both", expand=True)

        left  = tk.Frame(pane, bg=self.BG)
        right = tk.Frame(pane, bg=self.BG)
        pane.add(left,  minsize=620)
        pane.add(right, minsize=380)

        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        t0 = tk.Frame(nb, bg=self.BG)
        nb.add(t0, text="  📥 Incoming Request  ")
        self._build_request_tab(t0)

        t1 = tk.Frame(nb, bg=self.BG)
        nb.add(t1, text="  ISO 124 (Header)  ")
        self._build_editor_tab(t1, "ISO 124 — Response Header",
                               DEFAULT_ISO124, ISO124_FIELDS, self.svars124)

        t2 = tk.Frame(nb, bg=self.BG)
        nb.add(t2, text="  ISO 125 (Scores)  ")
        self._build_editor_tab(t2, "ISO 125 — Falcon Score + Decision Response",
                               DEFAULT_ISO125, ISO125_FIELDS, self.svars125)

        t3 = tk.Frame(nb, bg=self.BG)
        nb.add(t3, text="  ISO 126 (Decision overflow)  ")
        self._build_editor_tab(t3, "ISO 126 — Decision Code 9 + Decision 10 + Scoring Server ID",
                               DEFAULT_ISO126, ISO126_FIELDS, self.svars126)

        # ── EXT10 response editor tab ─────────────────────────────────────────
        t4 = tk.Frame(nb, bg=self.BG)
        nb.add(t4, text="  🔷 EXT10 Response  ")
        self._build_ext10_editor_tab(t4)

        # ── Raw Data Parser tab ─────────────────────────────────────────────────
        t5 = tk.Frame(nb, bg=self.BG)
        nb.add(t5, text="  🔍 Raw Parser  ")
        self._build_raw_parser_tab(t5)

        self._build_log_panel(right)

    def _apply_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        # Notebook
        s.configure("TNotebook",
                    background=self.BG, borderwidth=0, tabmargins=[0, 4, 0, 0])
        s.configure("TNotebook.Tab",
                    background=self.CARD, foreground=self.TXT2,
                    padding=[16, 7],
                    font=("Helvetica Neue", 10))
        s.map("TNotebook.Tab",
              background=[("selected", "#0d0d2e")],
              foreground=[("selected", self.ACCENT)])
        # Frames
        s.configure("TFrame", background=self.BG)
        # Scrollbars
        s.configure("TScrollbar",
                    background=self.CARD2,
                    troughcolor=self.PANEL,
                    arrowcolor=self.TXT2,
                    borderwidth=0,
                    arrowsize=10)
        s.map("TScrollbar",
              background=[("active", self.BORDER)])

    # ── Request viewer tab ────────────────────────────────────────────────────

    def _build_request_tab(self, parent):
        top = tk.Frame(parent, bg=self.BG)
        top.pack(fill="x", padx=10, pady=(8, 3))

        # Section pill header
        hdr_pill = tk.Frame(top, bg=self.CARD2, padx=12, pady=4)
        hdr_pill.pack(side="left")
        tk.Label(hdr_pill, text="▸  INCOMING REQUEST",
                 bg=self.CARD2, fg=self.TEAL,
                 font=("Helvetica Neue", 10, "bold")).pack(side="left")
        tk.Label(hdr_pill, text="  parsed field-by-field",
                 bg=self.CARD2, fg=self.TXT2,
                 font=("Helvetica Neue", 9)).pack(side="left")

        tk.Button(top, text="🗑  Clear", command=self._clear_request,
                  bg=self.CARD, fg=self.RED,
                  font=("Helvetica Neue", 9, "bold"),
                  relief="flat", padx=10, cursor="hand2",
                  activebackground=self.CARD2, activeforeground=self.RED
                  ).pack(side="right")

        self.req_text = scrolledtext.ScrolledText(
            parent, bg="#050514", fg=self.TXT, font=("Menlo", 10),
            relief="flat", selectbackground=self.ACCENT,
            selectforeground="#ffffff", insertbackground=self.TEAL,
            state="disabled", padx=8, pady=6)
        self.req_text.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        for tag, fg, bold in [
            ("sec",  self.ACCENT,   True),   ("fld",  self.ACCENT2, False),
            ("val",  self.TXT,      False),   ("raw",  self.YELLOW,  False),
            ("ts",   self.TXT2,     False),   ("sep",  self.BORDER,  False),
            ("err",  self.RED,      False),   ("echo", self.GREEN,   False),
            ("resv", self.ORANGE,   False),
        ]:
            self.req_text.tag_configure(
                tag, foreground=fg,
                font=("Menlo", 10, "bold") if bold else ("Menlo", 10))

    def _clear_request(self):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")
        self.req_text.config(state="disabled")

    # ── Generic editor tab ────────────────────────────────────────────────────

    def _build_editor_tab(self, parent, title: str, defaults: dict,
                          fields: list, var_dict: dict):
        """
        Scrollable field editor.
        StringVars go into var_dict.  Any change marks response as unsaved.
        appDataLength is shown read-only (auto-computed on send).
        externalHeaderData is shown read-only (echoed from inbound request).
        """
        hf = tk.Frame(parent, bg=self.BG)
        hf.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(hf, text=title, bg=self.BG, fg=self.ACCENT,
                 font=("Helvetica Neue", 10, "bold")).pack(side="left")

        note = tk.Frame(parent, bg="#0a0a28", pady=5)
        note.pack(fill="x", padx=8, pady=(3, 6))
        tk.Frame(note, bg=self.YELLOW, width=3).pack(side="left", fill="y")
        tk.Label(note,
                 text="  ✏️  Edit values then click  ✔ Save Response  to apply."
                      "  Fields are fixed-width — auto padded/trimmed on send.",
                 bg="#0a0a28", fg=self.YELLOW,
                 font=("Helvetica Neue", 9)
                 ).pack(side="left", padx=6)

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
        hdr = tk.Frame(inner, bg=self.CARD2)
        hdr.pack(fill="x", padx=2, pady=(2, 1))
        for col, w in [("Field Name", 32), ("Size", 6),
                       ("Active (sent)", 26), ("Edit value", 0)]:
            tk.Label(hdr, text=col, bg=self.CARD2, fg=self.TEAL,
                     font=("Helvetica Neue", 9, "bold"), width=w,
                     anchor="w").pack(side="left", padx=6, pady=4)

        # Choose which active dict to read for the "Active" column
        if var_dict is self.svars124:
            active_src = self.active124
        elif var_dict is self.svars125:
            active_src = self.active125
        elif var_dict is self.svars126:
            active_src = self.active126
        else:
            active_src = self.active_ext10_resp

        for name, size in fields:
            default_val = defaults.get(name, "")
            active_val  = active_src.get(name, default_val)
            is_auto     = (name == "appDataLength")
            is_echo     = (name == "externalHeaderData" and var_dict is self.svars124)
            is_ext_len  = (name == "extHeaderLength"    and var_dict is self.svars124)

            row = tk.Frame(inner, bg=self.PANEL)
            row.pack(fill="x", padx=2, pady=1)

            tk.Label(row, text=name, bg=self.PANEL, fg=self.ACCENT2,
                     font=("Menlo", 9), width=32, anchor="w"
                     ).pack(side="left", padx=6)

            # Size column
            size_display = (
                "auto" if is_auto
                else "dyn"  if (is_echo or is_ext_len)
                else str(size)
            )
            tk.Label(row, text=size_display, bg=self.PANEL, fg=self.TXT2,
                     font=("Menlo", 9), width=6, anchor="w"
                     ).pack(side="left", padx=2)

            # Active value column
            tk.Label(row,
                     text="(auto-computed)"       if is_auto
                          else "(dynamic from request)" if is_ext_len
                          else "(echoed from request)"  if is_echo
                          else repr(active_val),
                     bg=self.PANEL,
                     fg=self.TXT2 if (is_auto or is_echo or is_ext_len) else self.GREEN,
                     font=("Menlo", 8), width=26, anchor="w"
                     ).pack(side="left", padx=4)

            # Edit column
            var = tk.StringVar(value=str(default_val))
            var_dict[name] = var

            if is_auto:
                tk.Label(row, text="auto — always recalculated on send",
                         bg=self.PANEL, fg=self.TXT2,
                         font=("Menlo", 9, "italic")
                         ).pack(side="left", padx=8)
            elif is_ext_len:
                tk.Label(row,
                         text="dynamic — echoed from inbound extHeaderLength",
                         bg=self.PANEL, fg=self.YELLOW,
                         font=("Menlo", 9, "italic")
                         ).pack(side="left", padx=8)
            elif is_echo:
                tk.Label(row, text="echoed from inbound externalHeaderData",
                         bg=self.PANEL, fg=self.GREEN,
                         font=("Menlo", 9, "italic")
                         ).pack(side="left", padx=8)
            else:
                var.trace_add("write", self._on_field_changed)
                tk.Entry(row, textvariable=var,
                         bg=self.CARD2, fg=self.TXT,
                         insertbackground=self.TEAL, relief="flat",
                         font=("Menlo", 9),
                         highlightthickness=1,
                         highlightcolor=self.ACCENT,
                         highlightbackground=self.BORDER,
                         width=60
                         ).pack(side="left", padx=4, pady=2,
                                fill="x", expand=True)

    # ── EXT10 response editor tab ─────────────────────────────────────────────

    def _build_ext10_editor_tab(self, parent):
        """
        Dedicated editor for EXT10 response body fields.
        Identical UX to _build_editor_tab but targets EXT10_RESPONSE_FIELDS
        and self.svars_ext10_resp / self.active_ext10_resp.
        """
        hf = tk.Frame(parent, bg=self.BG)
        hf.pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(hf,
                 text="EXT10 Response Body — sent automatically when an EXT10 request arrives",
                 bg=self.BG, fg=self.ACCENT,
                 font=("Helvetica Neue", 10, "bold")).pack(side="left")

        note = tk.Frame(parent, bg="#0a0a28", pady=5)
        note.pack(fill="x", padx=8, pady=(3, 6))
        tk.Frame(note, bg=self.YELLOW, width=3).pack(side="left", fill="y")
        tk.Label(note,
                 text="  ✏️  Edit 'Response' value then click  ✔ Save Response  to apply."
                      "  All other fields are echoed from the inbound EXT10 request.",
                 bg="#0a0a28", fg=self.YELLOW,
                 font=("Helvetica Neue", 9)
                 ).pack(side="left", padx=6)

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
        for col, w in [("Field Name", 32), ("Size", 6),
                       ("Active (sent)", 26), ("Edit value", 0)]:
            tk.Label(hdr, text=col, bg=self.CARD, fg=self.ACCENT,
                     font=("Consolas", 9, "bold"), width=w,
                     anchor="w").pack(side="left", padx=6, pady=3)

        # Fields auto-echoed verbatim from the EXT10 request body
        ECHOED_FROM_REQUEST = {
            "workflow", "recordType", "dataSpecificationVersion",
            "clientIdFromHeader", "recordCreationDate", "recordCreationTime",
            "recordCreationMilliseconds", "gmtOffset",
            "customerIdFromHeader", "customerAcctNumber", "externalTransactionId",
        }

        for name, size in EXT10_RESPONSE_FIELDS:
            default_val = DEFAULT_EXT10_RESPONSE.get(name, "")
            active_val  = self.active_ext10_resp.get(name, default_val)
            is_echo     = name in ECHOED_FROM_REQUEST

            row = tk.Frame(inner, bg=self.PANEL)
            row.pack(fill="x", padx=2, pady=1)

            tk.Label(row, text=name, bg=self.PANEL, fg=self.ACCENT2,
                     font=("Consolas", 9), width=32, anchor="w"
                     ).pack(side="left", padx=6)

            tk.Label(row, text="echo" if is_echo else str(size),
                     bg=self.PANEL, fg=self.TXT2,
                     font=("Consolas", 9), width=6, anchor="w"
                     ).pack(side="left", padx=2)

            tk.Label(row,
                     text="(echoed from request)" if is_echo else repr(active_val),
                     bg=self.PANEL,
                     fg=self.TXT2 if is_echo else self.GREEN,
                     font=("Menlo", 8), width=26, anchor="w"
                     ).pack(side="left", padx=4)

            var = tk.StringVar(value=str(default_val))
            self.svars_ext10_resp[name] = var

            if is_echo:
                tk.Label(row, text="echoed from EXT10 request body (auto)",
                         bg=self.PANEL, fg=self.GREEN,
                         font=("Menlo", 9, "italic")
                         ).pack(side="left", padx=8)
            else:
                var.trace_add("write", self._on_field_changed)
                tk.Entry(row, textvariable=var,
                         bg=self.CARD, fg=self.TXT,
                         insertbackground=self.TXT, relief="flat",
                         font=("Menlo", 9), width=60
                         ).pack(side="left", padx=4, pady=2,
                                fill="x", expand=True)

    # ── Log panel ─────────────────────────────────────────────────────────────

    # ── Raw Data Parser tab ───────────────────────────────────────────────────

    def _build_raw_parser_tab(self, parent):
        """
        A dedicated tab where the user can paste raw ASCII or hex bytes and
        click Parse to see every header + body field broken out in the same
        colour-coded format as the live Incoming Request viewer.
        """
        # ── Title + info bar ─────────────────────────────────────────────────
        hf = tk.Frame(parent, bg=self.BG)
        hf.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(hf, text="🔍  Raw Data Parser ",
                 bg=self.BG, fg=self.ACCENT,
                 font=("Consolas", 10, "bold")).pack(side="left")

        # ── Options bar ──────────────────────────────────────────────────────
        opts = tk.Frame(parent, bg=self.BG)
        opts.pack(fill="x", padx=8, pady=(0, 4))

        # Format selector
        tk.Label(opts, text="Input format:", bg=self.BG, fg=self.TXT2,
                 font=("Consolas", 9)).pack(side="left", padx=(0, 6))
        self._parser_fmt = tk.StringVar(value="ascii")
        for val, lbl_text in [("ascii", "ASCII"), ("hex", "HEX")]:
            tk.Radiobutton(
                opts, text=lbl_text, variable=self._parser_fmt, value=val,
                bg=self.PANEL, fg=self.TXT, selectcolor=self.CARD2,
                activebackground=self.PANEL, activeforeground=self.TEAL,
                font=("Helvetica Neue", 9), cursor="hand2"
            ).pack(side="left", padx=4)

        # Prefix info label (auto-behaviour — no checkbox needed)
        tk.Frame(opts, bg=self.BORDER, width=2).pack(
            side="left", fill="y", pady=2, padx=(10, 6))        
        
        # Force-type override
        tk.Frame(opts, bg=self.BORDER, width=1).pack(
            side="left", fill="y", pady=4, padx=(10, 6))
        tk.Label(opts, text="Force type:", bg=self.PANEL, fg=self.TXT2,
                 font=("Helvetica Neue", 9)).pack(side="left", padx=(0, 4))
        self._parser_force_type = tk.StringVar(value="auto")
        for val, lbl_text in [("auto", "Auto-detect"), ("DBTRAN25", "DBTran25"), ("EXT10", "EXT10")]:
            tk.Radiobutton(
                opts, text=lbl_text, variable=self._parser_force_type, value=val,
                bg=self.PANEL, fg=self.TXT, selectcolor=self.CARD2,
                activebackground=self.PANEL, activeforeground=self.TEAL,
                font=("Helvetica Neue", 9), cursor="hand2"
            ).pack(side="left", padx=3)

        # ── Paned layout: input top, output bottom ────────────────────────────
        vpane = tk.PanedWindow(parent, orient="vertical",
                               bg=self.BG, sashwidth=5, sashrelief="flat")
        vpane.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # ── Input panel ──────────────────────────────────────────────────────
        inp_frame = tk.Frame(vpane, bg=self.BG)
        vpane.add(inp_frame, minsize=120)

        inp_top = tk.Frame(inp_frame, bg=self.BG)
        inp_top.pack(fill="x", pady=(2, 2))
        tk.Label(inp_top, text="  Raw Input", bg=self.BG, fg=self.TEAL,
                 font=("Helvetica Neue", 9, "bold")).pack(side="left")
        self._parser_byte_lbl = tk.Label(
            inp_top, text="", bg=self.BG, fg=self.TXT2,
            font=("Helvetica Neue", 9))
        self._parser_byte_lbl.pack(side="left", padx=12)
        tk.Button(inp_top, text="Clear Input",
                  command=self._clear_raw_input,
                  bg=self.CARD, fg=self.RED,
                  font=("Helvetica Neue", 9, "bold"), relief="flat",
                  padx=10, cursor="hand2",
                  activebackground=self.CARD2, activeforeground=self.RED
                  ).pack(side="right", padx=4)
        tk.Button(inp_top, text="  Parse",
                  command=self._parse_raw_input,
                  bg=self.ACCENT, fg="white",
                  font=("Helvetica Neue", 10, "bold"), relief="flat",
                  padx=16, cursor="hand2",
                  activebackground=self.BLUE, activeforeground="white"
                  ).pack(side="right", padx=4)

        self._parser_input = scrolledtext.ScrolledText(
            inp_frame, bg="#040412", fg=self.TEAL,
            font=("Menlo", 10), relief="flat",
            selectbackground=self.ACCENT, selectforeground="#ffffff",
            insertbackground=self.TEAL, height=8, wrap="char",
            padx=8, pady=6)
        self._parser_input.pack(fill="both", expand=True)
        self._parser_input.bind("<KeyRelease>", self._update_parser_byte_count)

        # ── Output panel ─────────────────────────────────────────────────────
        out_frame = tk.Frame(vpane, bg=self.BG)
        vpane.add(out_frame, minsize=200)

        out_top = tk.Frame(out_frame, bg=self.BG)
        out_top.pack(fill="x", pady=(4, 2))
        tk.Label(out_top, text="  Parsed Fields", bg=self.BG, fg=self.TEAL,
                 font=("Helvetica Neue", 9, "bold")).pack(side="left")
        self._parser_status_lbl = tk.Label(
            out_top, text="", bg=self.BG, fg=self.TXT2,
            font=("Helvetica Neue", 9))
        self._parser_status_lbl.pack(side="left", padx=12)
        tk.Button(out_top, text="Clear Output",
                  command=self._clear_raw_output,
                  bg=self.CARD, fg=self.RED,
                  font=("Helvetica Neue", 9, "bold"), relief="flat",
                  padx=10, cursor="hand2",
                  activebackground=self.CARD2, activeforeground=self.RED
                  ).pack(side="right", padx=4)

        self._parser_output = scrolledtext.ScrolledText(
            out_frame, bg="#050514", fg=self.TXT,
            font=("Menlo", 10), relief="flat",
            selectbackground=self.ACCENT, selectforeground="#ffffff",
            insertbackground=self.TEAL, state="disabled", wrap="word",
            padx=8, pady=6)
        self._parser_output.pack(fill="both", expand=True)

        # Reuse the same colour tags as req_text
        for tag, fg, bold in [
            ("sec",  self.ACCENT,  True),   ("fld",  self.ACCENT2, False),
            ("val",  self.TXT,     False),   ("raw",  self.YELLOW,  False),
            ("ts",   self.TXT2,    False),   ("sep",  self.BORDER,  False),
            ("err",  self.RED,     True),    ("echo", self.GREEN,   False),
            ("resv", self.ORANGE,  False),   ("warn", self.YELLOW,  False),
            ("ok",   self.GREEN,   True),    ("info", self.ACCENT2, False),
        ]:
            self._parser_output.tag_configure(
                tag, foreground=fg,
                font=("Menlo", 10, "bold") if bold else ("Menlo", 10))

    def _update_parser_byte_count(self, _event=None):
        """Live byte counter shown next to the input label."""
        raw = self._parser_input.get("1.0", "end-1c")
        fmt = self._parser_fmt.get()
        if fmt == "hex":
            clean = raw.replace(" ", "").replace("\n", "").replace("\r", "")
            try:
                n = len(bytes.fromhex(clean))
                self._parser_byte_lbl.config(
                    text=f"{n} byte(s)  [{len(clean)//2*2} hex chars]",
                    fg=self.GREEN)
            except ValueError:
                self._parser_byte_lbl.config(
                    text="⚠ invalid hex", fg=self.RED)
        else:
            n = len(raw.encode("ascii", errors="replace"))
            self._parser_byte_lbl.config(
                text=f"{n} byte(s)", fg=self.TXT2)

    def _clear_raw_input(self):
        self._parser_input.delete("1.0", "end")
        self._parser_byte_lbl.config(text="", fg=self.TXT2)

    def _clear_raw_output(self):
        self._parser_output.config(state="normal")
        self._parser_output.delete("1.0", "end")
        self._parser_output.config(state="disabled")
        self._parser_status_lbl.config(text="")

    def _parse_raw_input(self):
        """
        Read the pasted raw data, decode it according to the chosen format
        (ASCII / HEX), optionally strip the 2-byte framing prefix, then
        call _parse_request() and render the result in _parser_output.
        """
        raw_text = self._parser_input.get("1.0", "end-1c").strip()
        if not raw_text:
            messagebox.showwarning("Empty Input", "Please paste some raw data first.")
            return

        fmt = self._parser_fmt.get()

        # ── Decode to bytes ───────────────────────────────────────────────────
        if fmt == "hex":
            clean_hex = raw_text.replace(" ", "").replace("\n", "").replace("\r", "")
            try:
                raw_bytes = bytes.fromhex(clean_hex)
            except ValueError as ex:
                self._display_parsed_raw_error(f"HEX decode error: {ex}")
                return
        else:
            # ASCII — encode back to bytes so prefix stripping works uniformly
            try:
                raw_bytes = raw_text.encode("ascii", errors="replace")
            except Exception as ex:
                self._display_parsed_raw_error(f"ASCII encode error: {ex}")
                return

        total_bytes = len(raw_bytes)

        # ── Auto-prepend the 2-byte "00" framing prefix (invisible to user) ───
        # The Falcon protocol always frames messages with a leading ASCII "00".
        # We silently add those 2 bytes so the user only needs to paste the
        # actual payload, then immediately strip them before parsing.
        raw_bytes  = b"00" + raw_bytes   # prepend silently
        prefix_hex = raw_bytes[:2].hex() # = "3030" (ASCII '0','0')
        raw_bytes  = raw_bytes[2:]       # strip back off — net effect: parse user data as-is

        # ── Decode to str for the parser ──────────────────────────────────────
        try:
            raw_str = raw_bytes.decode("ascii", errors="replace")
        except Exception:
            raw_str = raw_bytes.decode("latin-1", errors="replace")

        # ── Determine extHeaderLength from bytes ──────────────────────────────
        min_for_ext_len = INBOUND_FIXED_BEFORE_EXT  # 52
        if len(raw_str) < min_for_ext_len:
            self._display_parsed_raw_error(
                f"Data too short ({len(raw_str)} bytes after prefix strip).\n"
                f"Need at least {min_for_ext_len} bytes for the fixed header portion.")
            return

        try:
            ext_len = int(raw_str[8 : 8 + 4].strip())
        except ValueError:
            ext_len = 20  # safe fallback

        # ── Call the existing parser ──────────────────────────────────────────
        hdr, body = self._parse_request(raw_str, ext_len)

        # ── Apply forced type override ────────────────────────────────────────
        force = self._parser_force_type.get()
        if force != "auto":
            detected_type = force
        else:
            tran = hdr.get("tranCode", "").strip()
            if tran.startswith("100000110") or "EXT10" in tran.upper():
                detected_type = "EXT10"
            else:
                detected_type = "DBTRAN25"

        # ── Render ────────────────────────────────────────────────────────────
        self._display_parsed_raw(
            hdr, body, raw_str, detected_type, total_bytes, prefix_hex, ext_len)

    def _display_parsed_raw_error(self, msg: str):
        """Show an error message in the parser output panel."""
        out = self._parser_output
        out.config(state="normal")
        out.delete("1.0", "end")
        out.insert("end", "⛔  Parse Error\n", "err")
        out.insert("end", "─" * 60 + "\n", "sep")
        out.insert("end", msg + "\n", "warn")
        out.config(state="disabled")
        out.see("1.0")
        self._parser_status_lbl.config(text="⛔ Parse failed", fg=self.RED)

    def _display_parsed_raw(self, hdr: dict, body: dict, raw_str: str,
                            req_type: str, total_bytes: int,
                            prefix_hex: str, ext_len: int):
        """
        Render the parsed header + body into _parser_output using the same
        colour-coded format as _display_request.
        """
        out = self._parser_output
        out.config(state="normal")
        out.delete("1.0", "end")

        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # ── Summary banner ────────────────────────────────────────────────────
        out.insert("end", f"Parsed at: {ts}\n", "ts")
        out.insert("end", "─" * 70 + "\n", "sep")
        out.insert("end",
                   f"  Total bytes: {total_bytes}"
                   + (f"  |  Framing prefix (stripped): {prefix_hex}" if prefix_hex else "")
                   + f"  |  Payload: {len(raw_str)} bytes"
                   + f"  |  extHeaderLength: {ext_len}"
                   + f"  |  Detected type: {req_type}\n",
                   "info")
        out.insert("end", "─" * 70 + "\n", "sep")

        # ── Header section ────────────────────────────────────────────────────
        out.insert("end", "\n▸ HEADER  (ISO 124 — inbound)\n", "sec")
        has_error = False
        for k, v in hdr.items():
            if k.startswith("_"):
                tag = "err"
                has_error = True
                out.insert("end", f"  ⚠  {v}\n", tag)
                continue
            out.insert("end", f"  {k:<44}", "fld")
            if k == "externalHeaderData":
                out.insert("end", f"  [{v.strip()}]  ← echoed in response\n", "echo")
            elif k == "RESERVED_01":
                out.insert("end", f"  [{v}]  (reserved)\n", "resv")
            else:
                out.insert("end", f"  [{v.strip()}]\n", "val")

        # ── Body section ──────────────────────────────────────────────────────
        if body:
            body_start = INBOUND_FIXED_BEFORE_EXT + ext_len + INBOUND_RESERVED_SIZE
            out.insert("end",
                       f"\n▸ BODY  ({req_type} Request)"
                       f"  — raw byte offset {body_start}"
                       f"  (fixed={INBOUND_FIXED_BEFORE_EXT}"
                       f" + extLen={ext_len}"
                       f" + reserved={INBOUND_RESERVED_SIZE})\n",
                       "sec")
            for k, v in body.items():
                out.insert("end", f"  {k:<44}", "fld")
                out.insert("end", f"  [{v.strip()}]\n", "val")
        else:
            out.insert("end", "\n  (no body parsed — message may be too short)\n", "warn")

        # ── Raw section ───────────────────────────────────────────────────────
        out.insert("end", "\n─ RAW STRING ─\n", "sep")
        out.insert("end", raw_str + "\n", "raw")

        out.config(state="disabled")
        out.see("1.0")

        # Update status label
        n_hdr  = sum(1 for k in hdr if not k.startswith("_"))
        n_body = len(body)
        status = (f"✅ {n_hdr} header field(s)  +  {n_body} body field(s)  "
                  f"|  {req_type}")
        self._parser_status_lbl.config(
            text=status, fg=self.RED if has_error else self.GREEN)

    # ── Log panel ─────────────────────────────────────────────────────────────

    def _build_log_panel(self, parent):
        # Log panel header
        log_hdr = tk.Frame(parent, bg="#050514", height=36)
        log_hdr.pack(fill="x")
        log_hdr.pack_propagate(False)
        tk.Frame(log_hdr, bg=self.ACCENT2, width=3).pack(side="left", fill="y")
        tk.Label(log_hdr, text="  💻  ACTIVITY LOG",
                 bg="#050514", fg=self.ACCENT2,
                 font=("Helvetica Neue", 11, "bold")).pack(side="left", padx=8, pady=6)
        tk.Button(log_hdr, text="✕ Clear", command=self._clear_log,
                  bg="#050514", fg=self.TXT2,
                  font=("Helvetica Neue", 9), relief="flat",
                  cursor="hand2", activeforeground=self.RED
                  ).pack(side="right", padx=8)

        self.log_text = scrolledtext.ScrolledText(
            parent, bg="#050514", fg=self.TXT, font=("Menlo", 10),
            relief="flat", selectbackground=self.ACCENT,
            selectforeground="#ffffff", insertbackground=self.TEAL,
            state="disabled", wrap="word", padx=8, pady=6)
        self.log_text.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        for tag, fg in [
            ("ts",      self.TXT2),     ("info",    self.TEAL),
            ("success", self.GREEN),    ("error",   self.RED),
            ("warn",    self.YELLOW),   ("raw",     self.ORANGE),
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
        self._set_dot(f"  LISTENING  {ip}:{port}", self.GREEN)
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
        self._set_dot("  STOPPED", self.RED)
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

            # ── Single-connection enforcement ──────────────────────────────────
            # Only ONE client may be connected at a time on the configured port.
            # If a second connection arrives while one is active, reject it.
            if self.client_conn is not None:
                self._log(
                    f"⛔  Rejected new connection from {cip}:{cport} "
                    f"— already serving an active client. Only 1 connection allowed.",
                    "warn")
                try:
                    conn.close()
                except Exception:
                    pass
                continue

            self._log(f"Client connected: {cip}:{cport}", "success")
            self._set_dot(f"  CONNECTED  {cip}:{cport}", self.ACCENT)
            self.client_conn = conn
            self._handle_client(conn, addr)
            self._log(f"Client disconnected: {cip}:{cport}", "warn")
            self.client_conn = None
            self._set_dot(
                f"  LISTENING  {self._bound_ip}:{self._bound_port}",
                self.GREEN)

    def _handle_client(self, conn: socket.socket, addr):
        buf = b""
        conn.settimeout(120.0)
        try:
            while self.running:
                # ── Receive chunks until the full message is buffered ──────────
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

                # ── Dynamic buffer gating ────────────────────────────────────
                # The header contains a dynamic-length externalHeaderData field.
                # Phase 1: wait for enough bytes to read extHeaderLength (at offset 10–13
                #          of the raw buf, i.e. prefix(2)+appDataLength(8)+extHeaderLength(4)).
                min_to_read_ext_len = INBOUND_PREFIX_LEN + INBOUND_FIXED_BEFORE_EXT  # 54
                if len(buf) < min_to_read_ext_len:
                    self._log(f"Buffering… {len(buf)}/{min_to_read_ext_len}+ bytes", "info")
                    continue

                # Phase 2: parse extHeaderLength and compute actual total expected bytes.
                ext_len_raw = buf[INBOUND_PREFIX_LEN + 8 : INBOUND_PREFIX_LEN + 8 + 4]
                try:
                    ext_len = int(ext_len_raw.decode("ascii", errors="replace").strip())
                except ValueError:
                    ext_len = 20   # safe fallback

                actual_total = (INBOUND_PREFIX_LEN + INBOUND_FIXED_BEFORE_EXT
                                + ext_len + INBOUND_RESERVED_SIZE + INBOUND_BODY_SIZE)

                if len(buf) < actual_total:
                    self._log(
                        f"Buffering… {len(buf)}/{actual_total} bytes "
                        f"(extHeaderLength={ext_len})", "info")
                    continue   # keep reading, do NOT respond yet

                # ── Full message is in buf — process exactly once ──────────────
                # Strip leading 2-byte framing prefix before parsing.
                prefix_hex = buf[:4].hex()   # diagnostic: log the raw prefix
                payload = buf[2:]            # actual ISO-124 content starts here

                try:
                    raw = payload.decode("ascii", errors="replace")
                except Exception:
                    raw = payload.decode("latin-1", errors="replace")

                self._log("─" * 55, "sep")
                self._log(
                    f"Received complete request from {addr[0]}:{addr[1]}"
                    f"  |  total={len(buf)} bytes"
                    f"  |  prefix hex: {prefix_hex}", "info")
                self._log(f"RAW IN ↓\n{raw}", "raw")

                hdr_d, body_d = self._parse_request(raw, ext_len)

                # ── Detect request type from tranCode ────────────────────────
                tran_raw = hdr_d.get("tranCode", "").strip()
                if tran_raw.startswith("100000110") or "EXT10" in tran_raw.upper():
                    self._last_request_type = "EXT10"
                else:
                    self._last_request_type = "DBTRAN25"
                self._log(
                    f"🏷  Request type detected: {self._last_request_type}  "
                    f"(tranCode=[{tran_raw}])", "info")

                # ── Echo-back: capture externalHeaderData + extHeaderLength ──
                # Read externalHeaderData (echoed verbatim in response)
                if "externalHeaderData" in hdr_d:
                    self._last_external_header_data = hdr_d["externalHeaderData"]

                # Read extHeaderLength directly from the inbound header and
                # echo it back as-is (zero-padded to 4 digits).
                # e.g. inbound extHeaderLength = "0032"  →  response extHeaderLength = "0032"
                if "extHeaderLength" in hdr_d:
                    raw_hl = hdr_d["extHeaderLength"].strip()
                    # Keep it exactly 4 chars, zero-padded
                    try:
                        self._last_ext_header_length = str(int(raw_hl)).zfill(4)
                    except ValueError:
                        self._last_ext_header_length = raw_hl.zfill(4)[:4]

                    self._log(
                        f"📋  externalHeaderData: [{self._last_external_header_data.strip()}]  "
                        f"|  extHeaderLength from request: [{raw_hl}]  "
                        f"→  will echo [{self._last_ext_header_length}]",
                        "info")

                # ── If EXT10: echo header fields from request into active response ─
                if self._last_request_type == "EXT10" and body_d:
                    ECHO_FIELDS = [
                        "workflow", "recordType", "dataSpecificationVersion",
                        "clientIdFromHeader", "recordCreationDate", "recordCreationTime",
                        "recordCreationMilliseconds", "gmtOffset",
                        "customerIdFromHeader", "customerAcctNumber", "externalTransactionId",
                    ]
                    for ef in ECHO_FIELDS:
                        if ef in body_d:
                            self.active_ext10_resp[ef] = body_d[ef]

                self.root.after(0,
                    lambda h=hdr_d, b=body_d, r=raw:
                        self._display_request(h, b, r))

                # ── Send exactly ONE response per complete request ─────────────
                # Prepend the 2-byte "00" framing prefix that the Falcon plugin
                # expects on every incoming message (mirrors the plugin-side:
                #   strRawMessage = "00" + m_renMsg.GetTxValue(...)  )
                resp   = self._build_response()
                framed = "00" + resp          # add the 2-byte prefix

                # ── Configurable response delay ───────────────────────────────
                delay = self.response_delay_seconds
                if delay > 0:
                    self._log(
                        f"⏳  Waiting {delay:g}s before sending "
                        f"{self._last_request_type} response…", "warn")
                    time.sleep(delay)

                try:
                    conn.sendall(framed.encode("ascii"))
                    delay_note = f" (after {delay:g}s delay)" if delay > 0 else ""
                    self._log(
                        f"✅  {self._last_request_type} Response sent "
                        f"({len(framed)} bytes, incl. 2-byte '00' prefix) "
                        f"— 1 response per request{delay_note}",
                        "success")
                    self._log(f"RAW OUT ↓\n{resp}", "raw")
                except Exception as ex:
                    self._log(f"Send error: {ex}", "error")

                # Clear buffer — ready for the next independent request
                buf = b""
        except Exception as ex:
            self._log(f"Client handler error: {ex}", "error")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # =========================================================================
    # PARSE + DISPLAY REQUEST
    # =========================================================================

    def _parse_request(self, raw: str, ext_len: int = 20):
        """
        Parse the inbound ISO-124 payload.

        ext_len: actual externalHeaderData byte count, pre-computed in _handle_client
                 from the extHeaderLength field of the BUFFERED bytes.  Passing it
                 as a parameter guarantees the header-parser and body-parser always
                 agree on the split point, regardless of any decoding edge-cases.

        body_start is computed EXPLICITLY:
            INBOUND_FIXED_BEFORE_EXT  (52)   — fixed header fields
          + ext_len                           — dynamic externalHeaderData
          + INBOUND_RESERVED_SIZE     (17)   — RESERVED_01
        """
        hdr, body = {}, {}

        if len(raw) < INBOUND_FIXED_BEFORE_EXT:
            hdr["_error"] = f"Message too short ({len(raw)} < {INBOUND_FIXED_BEFORE_EXT})"
            return hdr, body

        # ── 1) Parse fixed header fields before externalHeaderData (52 bytes) ──
        pos = 0
        for name, size in INBOUND_HEADER_FIELDS:
            if name in ("externalHeaderData", "RESERVED_01"):
                break
            hdr[name] = raw[pos : pos + size]
            pos += size
        # pos should equal INBOUND_FIXED_BEFORE_EXT (52) here

        # ── 2) Parse externalHeaderData using the passed ext_len ───────────────
        hdr["externalHeaderData"] = raw[pos : pos + ext_len]
        pos += ext_len

        # ── 3) Parse RESERVED_01 (always INBOUND_RESERVED_SIZE = 17 bytes) ─────
        hdr["RESERVED_01"] = raw[pos : pos + INBOUND_RESERVED_SIZE]
        pos += INBOUND_RESERVED_SIZE

        # ── 4) Compute body start position EXPLICITLY ──────────────────────────
        # This is independent of the accumulated pos above, so any subtle
        # discrepancy in the header-loop cannot misplace the body.
        body_start = INBOUND_FIXED_BEFORE_EXT + ext_len + INBOUND_RESERVED_SIZE

        self._log(
            f"🔍  Parse offsets — fixed_hdr={INBOUND_FIXED_BEFORE_EXT}"
            f"  ext_len={ext_len}"
            f"  reserved={INBOUND_RESERVED_SIZE}"
            f"  body_start={body_start}"
            f"  raw_len={len(raw)}",
            "info"
        )

        if body_start > len(raw):
            hdr["_warn"] = (
                f"body_start ({body_start}) > raw length ({len(raw)}); "
                "body will be empty — message may be truncated"
            )
            return hdr, body

        # ── 5) Parse body from the correct offset — choose fields by tranCode ──
        tran_for_parse = hdr.get("tranCode", "").strip()
        if tran_for_parse.startswith("100000110") or "EXT10" in tran_for_parse.upper():
            body = parse_fields(raw[body_start:], EXT10_REQUEST_FIELDS)
        else:
            body = parse_fields(raw[body_start:], DBTRANS25_REQUEST_FIELDS)

        return hdr, body

    def _display_request(self, hdr: dict, body: dict, raw: str):
        self.req_text.config(state="normal")
        self.req_text.delete("1.0", "end")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.req_text.insert("end", f"Received: {ts}\n", "ts")
        self.req_text.insert("end", "─" * 70 + "\n", "sep")
        self.req_text.insert("end", "\n▸ HEADER  (ISO 124 incoming)\n", "sec")

        for k, v in hdr.items():
            if k.startswith("_"):
                tag = "err" if k == "_error" else "warn"
                self.req_text.insert("end", f"  ⚠  {v}\n", tag)
                continue
            self.req_text.insert("end", f"  {k:<44}", "fld")
            if k == "externalHeaderData":
                self.req_text.insert(
                    "end", f"  [{v.strip()}]  ← will be echoed in response\n", "echo")
            elif k == "RESERVED_01":
                self.req_text.insert(
                    "end", f"  [{v}]  (reserved — not echoed)\n", "resv")
            else:
                self.req_text.insert("end", f"  [{v.strip()}]\n", "val")

        if body:
            # Compute body_start for the diagnostic label
            try:
                _ext_diag = int(hdr.get("extHeaderLength", "20").strip())
            except (ValueError, AttributeError):
                _ext_diag = 20
            _bstart = INBOUND_FIXED_BEFORE_EXT + _ext_diag + INBOUND_RESERVED_SIZE
            # Determine body label from request type
            _rtype = self._last_request_type
            self.req_text.insert(
                "end",
                f"\n▸ BODY  ({_rtype} Request)"
                f"  — raw byte offset {_bstart}"
                f"  (fixed={INBOUND_FIXED_BEFORE_EXT}"
                f" + extLen={_ext_diag}"
                f" + reserved={INBOUND_RESERVED_SIZE})\n",
                "sec")
            for k, v in body.items():
                self.req_text.insert("end", f"  {k:<44}", "fld")
                self.req_text.insert("end", f"  [{v.strip()}]\n", "val")

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
    # SAVE / LOAD TEMPLATE  (JSON file on disk)
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
            "iso124":         copy.deepcopy(self.active124),
            "iso125":         copy.deepcopy(self.active125),
            "iso126":         copy.deepcopy(self.active126),
            "ext10_response": copy.deepcopy(self.active_ext10_resp),
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
            ("iso124",         self.svars124,          self.active124),
            ("iso125",         self.svars125,          self.active125),
            ("iso126",         self.svars126,          self.active126),
            ("ext10_response", self.svars_ext10_resp,  self.active_ext10_resp),
        ):
            for k, v in data.get(section, {}).items():
                active[k] = v           # commit immediately
                if k in var_dict:
                    var_dict[k].set(v)  # update UI

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
