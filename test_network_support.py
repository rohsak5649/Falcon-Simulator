#!/usr/bin/env python3
"""
Test Suite for Falcon Simulator Network Support Message Handling & Regressions
Verifies all 8 scenarios outlined in Section 7 of the user request using socketpair.
"""

import socket
import threading
import time
import unittest
import tkinter as tk
from sim import (
    FalconSimulator,
    parse_network_message,
    NETWORK_FIELDS,
    NETWORK_MESSAGE_SIZE,
    TRANCODE_PING_REQUEST,
    TRANCODE_PING_RESPONSE,
    TRANCODE_DBTRAN25,
    TRANCODE_EXT10,
    INBOUND_HEADER_FIELDS,
    DBTRANS25_REQUEST_FIELDS,
    EXT10_REQUEST_FIELDS,
    EXT10_RESPONSE_FIELDS,
    fw,
)

class TestNetworkSupportMessages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create hidden root window for FalconSimulator
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.app = FalconSimulator(cls.root)
        cls.app.running = True

    @classmethod
    def tearDownClass(cls):
        cls.app.running = False
        try:
            cls.root.destroy()
        except Exception:
            pass

    def _create_client_connection(self):
        """Create a connected socketpair for simulator and test client."""
        server_conn, client_conn = socket.socketpair()
        self.app.client_conn = server_conn
        t = threading.Thread(
            target=self.app._handle_client,
            args=(server_conn, ("127.0.0.1", 54321)),
            daemon=True
        )
        t.start()
        time.sleep(0.05)
        return server_conn, client_conn, t

    def test_01_parse_network_message_unit(self):
        """Test parsing of valid and invalid network messages."""
        valid_raw = (
            "00000000" +
            "0000" +
            "100000060" +
            "IDFCTANGO " +
            "PMAX      " +
            "0000000000" +
            " "
        )
        self.assertEqual(len(valid_raw), 52)
        hdr, body = parse_network_message(valid_raw)
        self.assertNotIn("_error", hdr)
        self.assertEqual(hdr["appDataLength"], "00000000")
        self.assertEqual(hdr["extHeaderLength"], "0000")
        self.assertEqual(hdr["tranCode"], "100000060")
        self.assertEqual(hdr["sourceApplication"], "IDFCTANGO ")
        self.assertEqual(hdr["destinationApplication"], "PMAX      ")
        self.assertEqual(hdr["errorCode"], "0000000000")
        self.assertEqual(hdr["filler"], " ")
        self.assertEqual(body, {})

        # Test short message (Invalid length)
        short_raw = "000000000000"
        hdr_short, _ = parse_network_message(short_raw)
        self.assertIn("_error", hdr_short)

        # Test message with extra bytes
        long_raw = valid_raw + "EXTRA_BYTES"
        hdr_long, _ = parse_network_message(long_raw)
        self.assertIn("_warn", hdr_long)
        self.assertEqual(hdr_long["tranCode"], "100000060")

    def test_02_scenario_1_and_2_flow_a_ren_to_falcon(self):
        """
        Scenario 1 & 2: REN sends PING_REQUEST -> Simulator receives it.
        Simulator generates PING_RESPONSE -> REN receives it.
        """
        s_conn, c_conn, t = self._create_client_connection()

        # Build 52-byte PING_REQUEST framed with 2-byte "00"
        ping_req = (
            "00" +
            "00000000" +
            "0000" +
            "100000060" +
            "IDFCTANGO " +
            "PMAX      " +
            "0000000000" +
            " "
        )
        c_conn.sendall(ping_req.encode("ascii"))

        # Receive PING_RESPONSE (54 bytes)
        resp_bytes = b""
        start_t = time.time()
        while len(resp_bytes) < 54 and time.time() - start_t < 3.0:
            chunk = c_conn.recv(54 - len(resp_bytes))
            if not chunk:
                break
            resp_bytes += chunk

        self.assertEqual(len(resp_bytes), 54, f"Expected 54 bytes, got {len(resp_bytes)}")
        self.assertEqual(resp_bytes[:2], b"00", "Prefix must be '00'")

        resp_raw = resp_bytes[2:].decode("ascii")
        hdr, _ = parse_network_message(resp_raw)
        self.assertEqual(hdr["tranCode"], "200000060", "Response tranCode must be PING_RESPONSE")
        self.assertEqual(hdr["sourceApplication"], "PMAX      ", "Falcon must be sourceApplication")
        self.assertEqual(hdr["destinationApplication"], "IDFCTANGO ", "REN must be destinationApplication")
        self.assertEqual(hdr["errorCode"], "0000000000", "Error code must be 0000000000")
        self.assertEqual(hdr["appDataLength"], "00000000")
        self.assertEqual(hdr["extHeaderLength"], "0000")

        c_conn.close()
        s_conn.close()
        time.sleep(0.05)

    def test_03_scenario_3_and_4_flow_b_falcon_to_ren(self):
        """
        Scenario 3 & 4: Simulator sends PING_REQUEST -> REN receives it.
        REN generates PING_RESPONSE -> Simulator receives it.
        """
        s_conn, c_conn, t = self._create_client_connection()

        # Simulator initiates PING_REQUEST
        self.app._send_ping_request()

        # Client receives PING_REQUEST from Simulator
        req_bytes = b""
        start_t = time.time()
        while len(req_bytes) < 54 and time.time() - start_t < 3.0:
            chunk = c_conn.recv(54 - len(req_bytes))
            if not chunk:
                break
            req_bytes += chunk

        self.assertEqual(len(req_bytes), 54, f"Expected 54 bytes PING_REQUEST from Falcon, got {len(req_bytes)}")
        self.assertEqual(req_bytes[:2], b"00")
        req_raw = req_bytes[2:].decode("ascii")
        hdr, _ = parse_network_message(req_raw)
        self.assertEqual(hdr["tranCode"], "100000060", "Expected PING_REQUEST tranCode")
        self.assertEqual(hdr["sourceApplication"], "PMAX      ")
        self.assertEqual(hdr["destinationApplication"], "IDFCTANGO ")

        # REN generates PING_RESPONSE back to Falcon Simulator
        ping_resp = (
            "00" +
            "00000000" +
            "0000" +
            "200000060" +
            "IDFCTANGO " +
            "PMAX      " +
            "0000000000" +
            " "
        )
        c_conn.sendall(ping_resp.encode("ascii"))
        time.sleep(0.2)

        # Verify Simulator received and processed the PING_RESPONSE
        self.assertTrue(self.app._ping_event.is_set(), "Simulator should have set _ping_event upon receiving PING_RESPONSE")
        self.assertIsNotNone(self.app._last_ping_response)
        self.assertEqual(self.app._last_ping_response.get("tranCode"), "200000060")

        c_conn.close()
        s_conn.close()
        time.sleep(0.05)

    def test_04_scenario_5_incorrect_trancode(self):
        """Scenario 5: Incorrect transaction code is handled safely without crashing."""
        s_conn, c_conn, t = self._create_client_connection()

        # Send invalid tranCode in 52-byte network message
        bad_msg = (
            "00" +
            "00000000" +
            "0000" +
            "999999999" +
            "IDFCTANGO " +
            "PMAX      " +
            "0000000000" +
            " "
        )
        c_conn.sendall(bad_msg.encode("ascii"))
        time.sleep(0.2)

        # Simulator should still be alive and running
        self.assertTrue(self.app.running)
        self.assertEqual(self.app._last_request_type, "NETWORK_UNKNOWN")

        c_conn.close()
        s_conn.close()
        time.sleep(0.05)

    def test_05_scenario_6_invalid_message_length(self):
        """Scenario 6: Invalid message length is handled safely."""
        s_conn, c_conn, t = self._create_client_connection()

        # Send incomplete message (e.g. 20 bytes) and abruptly close socket
        c_conn.sendall(b"00000000000010000006")
        c_conn.close()
        s_conn.close()
        time.sleep(0.1)

        # Simulator should gracefully handle disconnect
        self.assertTrue(self.app.running)

    def test_06_scenario_7_dbtran25_unchanged(self):
        """Scenario 7: Existing DBTRAN25 request-response functionality remains unchanged."""
        s_conn, c_conn, t = self._create_client_connection()

        # Construct DBTRAN25 request
        ext_len_str = "0020"
        app_len_str = "00000978"
        fixed_hdr = (
            app_len_str +
            ext_len_str +
            "100000101" +  # tranCode DBTRAN25
            "IDFCTANGO " +
            "PMAX      " +
            "0000000000" +
            " "
        )
        ext_hdr = "DBTRAN251718532397  "  # 20 bytes
        reserved = " " * 17                # 17 bytes RESERVED_01
        body = "A" * 978                   # 978 bytes DBTRANS25 body
        full_msg = "00" + fixed_hdr + ext_hdr + reserved + body

        c_conn.sendall(full_msg.encode("ascii"))

        # Receive DBTRAN25 response (52 hdr + 20 ext_hdr + 969 iso125 + 100 iso126 + 2 prefix = 1143 bytes)
        resp_bytes = b""
        start_t = time.time()
        while len(resp_bytes) < 1143 and time.time() - start_t < 4.0:
            chunk = c_conn.recv(4096)
            if not chunk:
                break
            resp_bytes += chunk

        self.assertEqual(len(resp_bytes), 1143, f"Expected 1143 bytes DBTRAN25 response, got {len(resp_bytes)}")
        self.assertEqual(resp_bytes[:2], b"00")
        resp_raw = resp_bytes[2:].decode("ascii")

        # Verify ISO124 response header fields
        self.assertEqual(resp_raw[12:21], "200000102", "Response tranCode must be 200000102")
        self.assertEqual(resp_raw[21:31], "PMAX      ")
        self.assertEqual(resp_raw[31:41], "IDFCTANGO ")
        self.assertEqual(resp_raw[52:72], ext_hdr, "externalHeaderData must be echoed verbatim")

        c_conn.close()
        s_conn.close()
        time.sleep(0.05)

    def test_07_scenario_8_ext10_unchanged(self):
        """Scenario 8: Existing EXT10 request-response functionality remains unchanged."""
        s_conn, c_conn, t = self._create_client_connection()

        # Construct EXT10 request
        ext_len_str = "0020"
        app_len_str = "00000978"
        fixed_hdr = (
            app_len_str +
            ext_len_str +
            "100000110" +  # tranCode EXT10
            "IDFCTANGO " +
            "PMAX      " +
            "0000000000" +
            " "
        )
        ext_hdr = "EXT10HDR1718532397  "  # 20 bytes
        reserved = " " * 17                # 17 bytes RESERVED_01
        body = "B" * 978                   # 978 bytes body
        full_msg = "00" + fixed_hdr + ext_hdr + reserved + body

        c_conn.sendall(full_msg.encode("ascii"))

        # Receive EXT10 response (52 hdr + 20 ext_hdr + 162 ext10 body + 2 prefix = 236 bytes)
        resp_bytes = b""
        start_t = time.time()
        while len(resp_bytes) < 236 and time.time() - start_t < 4.0:
            chunk = c_conn.recv(4096)
            if not chunk:
                break
            resp_bytes += chunk

        self.assertEqual(len(resp_bytes), 236, f"Expected 236 bytes EXT10 response, got {len(resp_bytes)}")
        self.assertEqual(resp_bytes[:2], b"00")
        resp_raw = resp_bytes[2:].decode("ascii")

        # Verify EXT10 response header fields
        self.assertEqual(resp_raw[12:21], self.app.active124.get("tranCode", "200000102"))
        self.assertEqual(resp_raw[21:31], "PMAX      ")
        self.assertEqual(resp_raw[31:41], "IDFCTANGO ")
        self.assertEqual(resp_raw[52:72], ext_hdr, "externalHeaderData must be echoed verbatim")

        # Response body starts at 52 + 20 = 72
        # 'Response' field is the last 2 bytes of the 162 byte body (offset 72 + 160 = 232)
        body_part = resp_raw[72:234]
        self.assertEqual(len(body_part), 162)
        response_code = body_part[-2:]
        self.assertEqual(response_code, "00", "Default EXT10 Response code should be 00")

        c_conn.close()
        s_conn.close()
        time.sleep(0.05)

    def test_08_raw_parser_network_message(self):
        """Test Raw Data Parser tab parsing Network Support Messages in ASCII and HEX."""
        raw_msg = (
            "00000000" +
            "0000" +
            "100000060" +
            "IDFCTANGO " +
            "PMAX      " +
            "0000000000" +
            " "
        )
        # Test ASCII parsing
        self.app._parser_fmt.set("ascii")
        self.app._parser_force_type.set("auto")
        self.app._parser_input.delete("1.0", "end")
        self.app._parser_input.insert("1.0", raw_msg)
        self.app._parse_raw_input()

        status = self.app._parser_status_lbl.cget("text")
        self.assertIn("7 network field(s)", status)
        self.assertIn("PING_REQUEST", status)

        # Test HEX parsing
        hex_data = raw_msg.encode("ascii").hex()
        self.app._parser_fmt.set("hex")
        self.app._parser_force_type.set("NETWORK")
        self.app._parser_input.delete("1.0", "end")
        self.app._parser_input.insert("1.0", hex_data)
        self.app._parse_raw_input()

        status_hex = self.app._parser_status_lbl.cget("text")
        self.assertIn("7 network field(s)", status_hex)

    def test_09_save_and_reset_response(self):
        """Test editing network fields, saving response, and resetting to defaults."""
        self.app.svars_net["sourceApplication"].set("CUSTOMSRC ")
        self.app.svars_net["destinationApplication"].set("CUSTOMDST ")
        self.app.svars_net["errorCode"].set("0000000099")
        self.app._save_response()

        self.assertEqual(self.app.active_net["sourceApplication"], "CUSTOMSRC ")
        self.assertEqual(self.app.active_net["destinationApplication"], "CUSTOMDST ")
        self.assertEqual(self.app.active_net["errorCode"], "0000000099")

        # Test reset
        self.app._reset_response()
        self.assertEqual(self.app.active_net["sourceApplication"], "PMAX      ")
        self.assertEqual(self.app.active_net["destinationApplication"], "IDFCTANGO ")
        self.assertEqual(self.app.active_net["errorCode"], "0000000000")


if __name__ == "__main__":
    unittest.main()
