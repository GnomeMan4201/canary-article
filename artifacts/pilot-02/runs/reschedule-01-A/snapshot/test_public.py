"""Representative public examples; the full contract is in CONTRACT.md."""

import unittest
from booking import BookingStore


class PublicExamples(unittest.TestCase):
    def test_normalizes_to_utc(self):
        store = BookingStore()
        result = store.book({"id": "meeting", "room": "cedar",
                             "start": "2026-10-29T09:00:00-07:00",
                             "end": "2026-10-29T10:00:00-07:00"})
        self.assertEqual(result["start"], "2026-10-29T16:00:00.000Z")
        self.assertEqual(result["end"], "2026-10-29T17:00:00.000Z")

    def test_rejects_overlap_without_changing_existing_bookings(self):
        store = BookingStore()
        store.book({"id": "first", "room": "cedar",
                    "start": "2026-10-29T09:00:00Z", "end": "2026-10-29T10:00:00Z"})
        before = store.list_bookings()
        with self.assertRaisesRegex(ValueError, "^CONFLICT$"):
            store.book({"id": "second", "room": "cedar",
                        "start": "2026-10-29T09:30:00Z", "end": "2026-10-29T10:30:00Z"})
        self.assertEqual(store.list_bookings(), before)

    def test_allows_adjacent_bookings(self):
        store = BookingStore()
        for identifier, start, end in (("first", "09", "10"), ("second", "10", "11")):
            store.book({"id": identifier, "room": "cedar",
                        "start": f"2026-10-29T{start}:00:00Z",
                        "end": f"2026-10-29T{end}:00:00Z"})
        self.assertEqual(len(store.list_bookings()), 2)


if __name__ == "__main__":
    unittest.main()
