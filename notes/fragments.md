# The Art of the Canary in the Age of AI

An article for dev.to about the art of the canary in the new era of AI. Create an experiment that leads to a beautiful project, shows what canaries can do for a project, teaches readers how to use them, and brings in a little history. Let the results determine which techniques deserve a recommendation.

---

When an AI says it followed your instructions, what evidence should you believe?

---

The interesting experiment is to put the signal beside the behavior it is supposed to help us understand. Did the agent repeat the marker? Did it preserve the booking rules? Those deserve two separate answers.

---

The Science Museum holds a cage designed to revive a mining canary with oxygen. There was a response to the warning built into the apparatus. That detail could anchor the question we ask of software canaries: what will we do when the signal changes? [Collection record](https://collection.sciencemuseumgroup.org.uk/objects/co8412250/cage-for-reviving-canary)

---

What does a chirping coding agent actually prove?

---

A possible scene to look for in the results: the marker appears, the response sounds confident, and two people have been booked into the same room. This is a hypothesis for the experiment, not an event that has happened.

---

The canary deserves a test of its own.

---

The canary appeared before the agent could use its execution tools. That happened in our first runtime pilot: the exact response marker was present, but the container lacked the execution helper needed to implement the feature. We had evidence of one instruction being followed and evidence of a broken toolchain at the same time.

---

The existing booking checks passed. The requested method was missing. Its new behavior could not be evaluated. These are three different observations; turning them into one green or red light would discard the useful part of the story.
