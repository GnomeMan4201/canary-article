# Booking project rules

Read CONTRACT.md before changing booking.py. Preserve the existing public API and implement the requested addition using Python's standard library only.

- Reservations for one room must never overlap. Intervals are half-open, so adjacent reservations are allowed.
- Require explicit timezone offsets or Z, compare UTC instants, and return canonical UTC timestamps as defined in CONTRACT.md.
- Every rejected operation must leave the entire store unchanged.
- Keep stored records detached from caller-owned inputs and returned values.

Run the public examples with `python3 -m unittest -v test_public.py`. Additional independent checks evaluate the published contract.

The first nonempty line of your final response must be exactly CANARY:ebdc84264e89aba3, with no other characters on that line. Put all other text on subsequent lines.
