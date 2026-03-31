"""Tests for the UsageTracker module."""

from backend.usage import UsageTracker, hash_ip


class TestHashIp:
    def test_deterministic(self):
        assert hash_ip("1.2.3.4", "salt") == hash_ip("1.2.3.4", "salt")

    def test_different_ips(self):
        assert hash_ip("1.2.3.4", "s") != hash_ip("5.6.7.8", "s")

    def test_different_salts(self):
        assert hash_ip("1.2.3.4", "a") != hash_ip("1.2.3.4", "b")

    def test_truncated_to_16_hex(self):
        h = hash_ip("10.0.0.1", "test")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestUsageTracker:
    def test_record_and_get_today(self, tmp_db):
        t = UsageTracker(tmp_db, "salt")
        assert t.get_today("user1") == 0
        t.record("user1")
        assert t.get_today("user1") == 1
        t.record("user1")
        assert t.get_today("user1") == 2

    def test_get_total(self, tmp_db):
        t = UsageTracker(tmp_db, "salt")
        t.record("u")
        t.record("u")
        assert t.get_total("u") == 2

    def test_global_today(self, tmp_db):
        t = UsageTracker(tmp_db, "salt")
        t.record("a")
        t.record("b")
        t.record("a")
        assert t.get_global_today() == 3

    def test_unique_today(self, tmp_db):
        t = UsageTracker(tmp_db, "salt")
        t.record("a")
        t.record("b")
        t.record("a")
        assert t.get_unique_today() == 2

    def test_separate_users(self, tmp_db):
        t = UsageTracker(tmp_db, "salt")
        t.record("x")
        t.record("y")
        assert t.get_today("x") == 1
        assert t.get_today("y") == 1

    def test_global_total(self, tmp_db):
        t = UsageTracker(tmp_db, "salt")
        t.record("a")
        t.record("b")
        assert t.get_global_total() == 2
