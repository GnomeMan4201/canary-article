# Initial project brief

Archived before implementation. See the [current project README](../README.md) for results and runnable commands.

# Canary Lab

An experiment and companion project for a dev.to article about using canaries in AI-assisted development. The first study examines how a visible instruction marker relates to independently checked project behavior in a small set of coding tasks.

Working article title: **The Art of the Canary in the Age of AI**.

Working subtitle: **What does a chirping coding agent actually prove?**

## The editorial choice

Focus on instruction canaries: a small requirement in a project's instructions that produces an observable signal in an agent's response. Explain deployment canaries briefly as a related use of the metaphor; keep security decoys outside this experiment.

Write for developers already using a coding assistant who know what a repository and an automated test are. Explain instruction discovery, canary signals, and measurement through the project rather than assuming familiarity.

The article's contribution will be a reproducible comparison between a canary's signal and independently checked project behavior. Existing tools already display instruction canaries, including [Context Canary](https://github.com/Nachx639/context-canary). Its README acknowledges that a missing signal does not prove context loss. Credit that work; do not claim to have invented the technique or its limitations.

Our editorial promise: build a small instruction canary, compare its responses with independent checks of a coding task, and give readers a reproducible way to examine the signal in their own projects. Keep instruction-loading evidence, marker adherence, behavioral checks, and feature completion distinct. A rule-check failure can reflect an implementation mistake even when the instruction was available.

The first study measures final outcomes. It does not test early warning, recovery actions, or which canary technique is best. Present practical response advice as engineering guidance, and reserve comparative claims for experiments that actually compare those techniques.

## The companion project

Build a small meeting-room booking service as the experimental subject. Its rules are easy to explain and check: no overlapping bookings for the same room, consistent handling of timestamps, and no changes to existing bookings when a new request is rejected.

Build Canary Lab around recorded runs of agents modifying that service. Begin with a run matrix and an expandable evidence view. Selecting a run reveals its instructions, task, response, code diff, and test evidence. Show marker status, rule checks, feature completion, and unavailable evidence separately. A bird can indicate whether the marker appeared; its label must say exactly that. A within-session warning timeline belongs to a later study that collects checkpoints.

Select an opening example after all runs are classified, showing how often that combination occurred. Prefer a representative case; label an unusual case as an outlier if it earns a place in the story. If every marker appears, report that the sample cannot show whether marker omission distinguishes correct from incorrect behavior. A disagreement between marker and checks is one possible result, not the desired result.

## The article's journey

Open with one real run after the experiment and place it in the context of the full results. Introduce the small signal that prompted the investigation. Use one short historical passage to explain the early-warning metaphor while making clear that our first study does not measure warning lead time. Show how to add a canary, how we evaluated it, what happened, and a practical investigation sequence for a missing marker: inspect loading, re-establish the relevant instruction, and run the appropriate independent check.

The historical anchor is the Science Museum's [canary revival cage](https://collection.sciencemuseumgroup.org.uk/objects/co8412250/cage-for-reviving-canary), which included an oxygen cylinder. It provides a concrete object for discussing detection and response. Avoid suggesting an unbroken, documented lineage from that object to AI tooling.

Keep the article practical and curious. Explain distinctions among evidence that instructions were loaded, evidence that a marker was emitted, and evidence that a rule was followed. Anthropic's [memory documentation](https://code.claude.com/docs/en/memory) explicitly distinguishes instructional context from enforced configuration; the experiment explores the practical consequences.

## Project documents

- [Experiment protocol](experiment.md): comparison groups, checks, measurements, and evidence requirements.
- [Article fragments](../notes/fragments.md): possible passages and observations to develop as the work progresses.
- [Expert review and decisions](review.md): engineering, experimental-methods, and editorial findings, with remaining requirements before trials.

Current state: reviewed experiment design, with implementation and validation requirements still open. The booking service, runner, and visual explorer have not been implemented, and no agent trials have been run. Build and validate the evidence pipeline before investing in the visual explorer.
