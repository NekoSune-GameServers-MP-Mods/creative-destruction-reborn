import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from game_tickets import TicketRegistry


class GameTicketTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000
        self.registry = TicketRegistry(ttl=30, capacity=2, clock=lambda: self.now)
        self.session = "session-a-verified-12345678"

    def test_ticket_one_use_and_purpose_bound(self):
        ticket = self.registry.issue(42, "gateway", self.session)
        self.assertIsNone(self.registry.redeem(ticket, "battle", self.session))
        self.assertIsNone(self.registry.redeem(ticket, "gateway", "session-b-verified-12345678"))
        self.assertEqual(self.registry.redeem(ticket, "gateway", self.session), 42)
        self.assertIsNone(self.registry.redeem(ticket, "gateway", self.session))

    def test_expiration_and_capacity(self):
        first = self.registry.issue(42, "gateway", self.session)
        self.registry.issue(43, "battle", self.session)
        with self.assertRaises(RuntimeError):
            self.registry.issue(44, "gateway", self.session)
        self.now += 30
        self.assertIsNone(self.registry.redeem(first, "gateway", self.session))
        self.assertTrue(self.registry.issue(44, "gateway", self.session))

    def test_revoke_and_invalid_input(self):
        ticket = self.registry.issue(42, "gateway", self.session)
        self.registry.revoke_session(self.session)
        self.assertIsNone(self.registry.redeem(ticket, "gateway", self.session))
        self.assertIsNone(self.registry.redeem("invalid", "gateway", self.session))
        with self.assertRaises(ValueError):
            self.registry.issue(0, "gateway", self.session)
        with self.assertRaises(ValueError):
            self.registry.issue(3, "other", self.session)

    def test_concurrent_redeem_single_winner(self):
        ticket = self.registry.issue(42, "gateway", self.session)
        results = []
        def redeem():
            results.append(self.registry.redeem(ticket, "gateway", self.session))
        threads = [threading.Thread(target=redeem) for _ in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results.count(42), 1)
        self.assertEqual(results.count(None), 11)


if __name__ == "__main__":
    unittest.main()
