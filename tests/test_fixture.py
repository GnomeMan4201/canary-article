"""Development checks for the baseline and independent reference submissions."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_store(relative):
    path = ROOT / "fixtures" / relative / "booking.py"
    spec = importlib.util.spec_from_file_location("fixture_booking", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BookingStore


STORES = {
    name: load_store(relative) for name, relative in (
        ("baseline", "baseline"),
        ("reschedule", "reference/reschedule"),
        ("availability", "reference/availability"),
        ("batch", "reference/batch"),
    )
}


def record(identifier="a", room="cedar", start="2026-10-29T09:00:00Z",
           end="2026-10-29T10:00:00Z"):
    return {"id": identifier, "room": room, "start": start, "end": end}


class BaselineContract(unittest.TestCase):
    def test_contract_copy_matches(self):
        self.assertEqual((ROOT / "docs/contract.md").read_bytes(),
                         (ROOT / "fixtures/baseline/CONTRACT.md").read_bytes())

    def test_each_reference_contains_only_its_requested_addition(self):
        methods = {"reschedule": "reschedule", "availability": "available_rooms",
                   "batch": "book_many"}
        for name, store_type in STORES.items():
            with self.subTest(name=name):
                self.assertEqual({method for method in methods.values()
                                  if hasattr(store_type, method)},
                                 {methods[name]} if name in methods else set())

    def test_normalization_precision_offsets_and_year_boundaries(self):
        cases = [
            ("2026-10-29T09:00:00-07:00", "2026-10-29T16:00:00.000Z"),
            ("2026-10-29T09:00:00.1+01:30", "2026-10-29T07:30:00.100Z"),
            ("2026-10-29T09:00:00.12Z", "2026-10-29T09:00:00.120Z"),
            ("2026-10-29T09:00:00.123-00:00", "2026-10-29T09:00:00.123Z"),
            ("2026-10-29T00:00:00+23:59", "2026-10-28T00:01:00.000Z"),
            ("0001-01-01T00:00:00Z", "0001-01-01T00:00:00.000Z"),
            ("0999-12-31T23:59:59Z", "0999-12-31T23:59:59.000Z"),
        ]
        for name, store_type in STORES.items():
            for original, expected in cases:
                with self.subTest(name=name, timestamp=original):
                    store = store_type()
                    result = store.book(record(start=original, end="9999-12-31T23:59:59.999Z"))
                    self.assertEqual(result["start"], expected)
                    self.assertEqual(result["end"], "9999-12-31T23:59:59.999Z")

    def test_invalid_timestamps_are_rejected_without_state_changes(self):
        invalid = [
            None, 123, True, "", "2026-10-29T09:00:00", "2026-10-29t09:00:00Z",
            "2026-10-29T09:00:00z", "2026-10-29 09:00:00Z", "2026-10-29T09:00Z",
            "2026-10-29T09:00:00.1234Z", "2026-10-29T09:00:00.Z",
            "2026-02-29T09:00:00Z", "2026-13-01T09:00:00Z", "2026-01-00T09:00:00Z",
            "2026-10-29T24:00:00Z", "2026-10-29T09:60:00Z", "2026-10-29T09:00:60Z",
            "2026-10-29T09:00:00+24:00", "2026-10-29T09:00:00+01:60",
            "2026-10-29T09:00:00+0100", "2026-10-29T09:00:00+01:00:00",
            "0000-01-01T00:00:00Z", "0001-01-01T00:00:00+00:01",
            "9999-12-31T23:59:59-00:01", "2026-10-29T09:00:00Z\n",
            " 2026-10-29T09:00:00Z", "2026-10-29T09:00:00Z ",
            "２０２６-10-29T09:00:00Z",
        ]
        for name, store_type in STORES.items():
            store = store_type()
            store.book(record())
            before = store.list_bookings()
            for timestamp in invalid:
                for field in ("start", "end"):
                    with self.subTest(name=name, timestamp=timestamp, field=field):
                        candidate = record("b", room="maple")
                        candidate[field] = timestamp
                        with self.assertRaisesRegex(ValueError, "^INVALID_INPUT$"):
                            store.book(candidate)
                        self.assertEqual(store.list_bookings(), before)

    def test_invalid_record_shapes_types_and_intervals(self):
        bad_records = [None, [], (), "record", {}, {**record(), "extra": 1},
                       {key: value for key, value in record().items() if key != "id"},
                       record(identifier=""), record(identifier=1), record(room=None),
                       record(end="2026-10-29T09:00:00Z"),
                       record(end="2026-10-29T08:00:00Z"),
                       record(start="2026-10-29T10:00:00+01:00",
                              end="2026-10-29T09:00:00Z")]
        for name, store_type in STORES.items():
            for candidate in bad_records:
                with self.subTest(name=name, candidate=candidate):
                    store = store_type()
                    with self.assertRaisesRegex(ValueError, "^INVALID_INPUT$"):
                        store.book(candidate)
                    self.assertEqual(store.list_bookings(), [])

    def test_conflicts_duplicate_ids_unknown_rooms_and_adjacency(self):
        for name, store_type in STORES.items():
            with self.subTest(name=name):
                store = store_type()
                store.book(record())
                before = store.list_bookings()
                for candidate, code in [
                    (record("b", start="2026-10-29T08:59:59Z"), "CONFLICT"),
                    (record("b", start="2026-10-29T10:30:00+01:00",
                            end="2026-10-29T11:30:00+01:00"), "CONFLICT"),
                    (record("a", room="maple"), "DUPLICATE_ID"),
                    (record("b", room="oak"), "UNKNOWN_ROOM"),
                ]:
                    with self.assertRaisesRegex(ValueError, f"^{code}$"):
                        store.book(candidate)
                    self.assertEqual(store.list_bookings(), before)
                store.book(record("c", start="2026-10-29T10:00:00Z", end="2026-10-29T11:00:00Z"))
                store.book(record("b", room="maple"))
                self.assertEqual([item["id"] for item in store.list_bookings()], ["a", "b", "c"])

    def test_input_and_output_mutation_cannot_change_store(self):
        for name, store_type in STORES.items():
            with self.subTest(name=name):
                store = store_type()
                candidate = record()
                result = store.book(candidate)
                expected = store.list_bookings()
                candidate["room"] = "maple"
                result["id"] = "changed"
                listed = store.list_bookings()
                listed[0]["start"] = "changed"
                listed.clear()
                self.assertEqual(store.list_bookings(), expected)

    def test_nonempty_ids_are_not_trimmed_and_valid_leap_dates_are_accepted(self):
        for name, store_type in STORES.items():
            with self.subTest(name=name):
                store = store_type()
                result = store.book(record(" ", start="2024-02-29T09:00:00Z",
                                           end="2024-02-29T10:00:00Z"))
                self.assertEqual(result["id"], " ")
                self.assertEqual(result["start"], "2024-02-29T09:00:00.000Z")


class ReferenceAdditions(unittest.TestCase):
    def test_reschedule_excludes_self_and_preserves_identity(self):
        store = STORES["reschedule"]()
        original = store.book(record())
        self.assertEqual(store.reschedule("a", original["start"], original["end"]), original)
        result = store.reschedule("a", "2026-10-29T10:30:00+01:00", "2026-10-29T11:30:00+01:00")
        self.assertEqual(result, record(start="2026-10-29T09:30:00.000Z", end="2026-10-29T10:30:00.000Z"))
        result["room"] = "maple"
        self.assertEqual(store.list_bookings()[0]["room"], "cedar")

    def test_reschedule_errors_are_atomic(self):
        store = STORES["reschedule"]()
        store.book(record())
        store.book(record("b", start="2026-10-29T10:00:00Z", end="2026-10-29T11:00:00Z"))
        before = store.list_bookings()
        cases = [
            (("a", "2026-10-29T10:30:00Z", "2026-10-29T11:30:00Z"), "CONFLICT"),
            (("a", "2026-10-29T09:00:00", "2026-10-29T11:30:00Z"), "INVALID_INPUT"),
            (("a", "2026-10-29T12:00:00Z", "2026-10-29T11:30:00Z"), "INVALID_INPUT"),
            (("missing", "2026-10-29T12:00:00Z", "2026-10-29T13:00:00Z"), "BOOKING_NOT_FOUND"),
        ]
        cases += [((identifier, "2026-10-29T12:00:00Z", "2026-10-29T13:00:00Z"), "INVALID_INPUT")
                  for identifier in (None, "", [], 2)]
        for args, code in cases:
            with self.subTest(args=args):
                with self.assertRaisesRegex(ValueError, f"^{code}$"):
                    store.reschedule(*args)
                self.assertEqual(store.list_bookings(), before)

    def test_availability_uses_same_interval_rules_without_mutation(self):
        store = STORES["availability"]()
        self.assertEqual(store.available_rooms("2026-10-29T09:00:00Z", "2026-10-29T10:00:00Z"),
                         ["cedar", "maple"])
        store.book(record())
        before = store.list_bookings()
        self.assertEqual(store.available_rooms("2026-10-29T10:30:00+01:00", "2026-10-29T11:30:00+01:00"),
                         ["maple"])
        self.assertEqual(store.available_rooms("2026-10-29T10:00:00Z", "2026-10-29T11:00:00Z"),
                         ["cedar", "maple"])
        for start, end in (("2026-10-29T09:00:00", "2026-10-29T10:00:00Z"),
                           ("2026-10-29T10:00:00Z", "2026-10-29T09:00:00Z")):
            with self.assertRaisesRegex(ValueError, "^INVALID_INPUT$"):
                store.available_rooms(start, end)
        self.assertEqual(store.list_bookings(), before)
        store.book(record("b", room="maple"))
        self.assertEqual(store.available_rooms("2026-10-29T09:00:00Z", "2026-10-29T10:00:00Z"), [])

    def test_batch_order_normalization_and_detachment(self):
        store = STORES["batch"]()
        self.assertEqual(store.book_many([]), [])
        candidates = [record("z"), record("a", room="maple")]
        result = store.book_many(candidates)
        self.assertEqual([item["id"] for item in result], ["z", "a"])
        self.assertEqual(result[0]["start"], "2026-10-29T09:00:00.000Z")
        expected = store.list_bookings()
        result[0]["room"] = "maple"
        candidates[1]["id"] = "changed"
        candidates.clear()
        self.assertEqual(store.list_bookings(), expected)

    def test_batch_rolls_back_for_later_invalid_conflicting_or_duplicate_records(self):
        good = record("new", room="maple")
        cases = [
            ([good, record("other", room="maple")], "CONFLICT"),
            ([good, record("new")], "DUPLICATE_ID"),
            ([good, record("existing", room="maple")], "DUPLICATE_ID"),
            ([good, record("other")], "CONFLICT"),
            ([good, None], "INVALID_INPUT"),
            ([good, record("other", room="oak")], "UNKNOWN_ROOM"),
            ([good, record("other", start="invalid")], "INVALID_INPUT"),
            (None, "INVALID_INPUT"), ((good,), "INVALID_INPUT"), ({}, "INVALID_INPUT"),
            ((item for item in [good]), "INVALID_INPUT"),
        ]
        for candidates, code in cases:
            with self.subTest(candidates=candidates):
                store = STORES["batch"]()
                store.book(record("existing"))
                before = store.list_bookings()
                with self.assertRaisesRegex(ValueError, f"^{code}$"):
                    store.book_many(candidates)
                self.assertEqual(store.list_bookings(), before)


if __name__ == "__main__":
    unittest.main()
