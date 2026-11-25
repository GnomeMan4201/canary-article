# Statistics and diagnostic-accuracy methodology for Canary Lab

Scope: what main-01's results (30 runs, 15 with a marker; 0 rule failures; 15/15 exact markers) actually bound, how many runs main-02 needs to observe failures and estimate the marker's accuracy as a warning, and how to handle dependence between repeated runs. All numbers marked "computed" come from a scratch script (scipy 1.x, `beta.ppf` for exact and Jeffreys limits, closed forms for Wilson and Agresti-Coull, exact binomial tails). They are reproducible from the formulas given. Nothing in the repo was modified.

Mapping used throughout. "Condition" = checked rule failure (or, for the signal-versus-work table, incomplete work). "Test positive" = marker noncompliance (malformed or absent) in a condition-B run with an observed final response.
- Sensitivity = P(noncompliant | failure). In report.json this is `noncompliance_given_failure`.
- Specificity = P(exact | pass).
- PPV = P(failure | noncompliant) = `failure_given_noncompliant`.
- 1 − NPV = P(failure | exact) = `failure_given_exact`.

## 1. Confidence intervals for 0/n and n/n: what main-01 bounds

### Takeaway
When the count is zero or all, the interval is the result. 0/15 failures among exact-marker runs is consistent with a true failure rate of up to about 18 to 22% (95%). 0/30 across all runs is consistent with up to about 10 to 12%. 15/15 exact markers is consistent with true marker compliance as low as about 78 to 82%. Report Wilson as the primary interval, following Brown, Cai and DasGupta and Bowyer et al. Add the exact Clopper-Pearson one-sided bound for zero-event cells, because it is the conservative bound readers can check by hand.

### Cited findings
- The rule of three: with 0 events in n trials, the 95% upper confidence bound on the event rate is about 3/n (Hanley JA, Lippman-Hand A. "If nothing goes wrong, is everything all right? Interpreting zero numerators." *JAMA* 1983;249(13):1743–1745, doi:10.1001/jama.1983.03330370053031). This bound is one-sided, and it comes from solving (1−p)^n = 0.05, which gives p = 1 − 0.05^(1/n) ≈ −ln(0.05)/n ≈ 3/n — [JAMA abstract](https://jamanetwork.com/journals/jama/article-abstract/389714); [Wikipedia summary](https://en.wikipedia.org/wiki/Rule_of_three_(statistics)). One secondary source says 3/n is close to the exact bound by n = 20 (15% vs 14%). A later critique argues it is a poor estimator for n < 20 — [Strathprints, "Estimating risk when zero events have been observed"](https://strathprints.strath.ac.uk/46413/1/Estimating_Risk_when_Zero_Events_have_been_Observed_Final_non_Mark_Strathprints.pdf).
- Brown LD, Cai TT, DasGupta A. "Interval estimation for a binomial proportion." *Statistical Science* 2001;16(2):101–133, doi:10.1214/ss/1009213286. They show the Wald interval behaves erratically. For small n (they say "40 or less") they recommend the Wilson interval or the equal-tailed Jeffreys interval, and Agresti-Coull for larger n. They treat Wilson and Jeffreys as interchangeable, and they say all three are similar above n = 40 — [Project Euclid](https://projecteuclid.org/euclid.ss/1009213286); [PDF](https://projecteuclid.org/download/pdf_1/euclid.ss/1009213286). Their modified Jeffreys interval sets the lower limit to 0 when x = 0 and the upper limit to 1 when x = n. The Jeffreys numbers below use that convention.
- Bowyer S, Aitchison L, Ivanova DR. "Position: Don't use the CLT in LLM evals with fewer than a few hundred datapoints." ICML 2025 Spotlight Position Paper, arXiv:2503.01747. They find that CLT/Wald error bars on small LLM evals "usually dramatically underestimat[e] uncertainty" and collapse to zero width at 0 or n successes, which the paper calls "clearly not right". They recommend Wilson or Bayesian Beta-Bernoulli intervals over Clopper-Pearson, which they find overly conservative. Their Python library is github.com/sambowyer/bayes_evals, and Wilson and Clopper-Pearson are available in SciPy as `scipy.stats.binomtest(k, n).proportion_ci(method="wilson"|"exact")` — [arXiv abstract](https://arxiv.org/abs/2503.01747); [HTML full text](https://arxiv.org/html/2503.01747).

### Computed values (95%)
| Observation | Wald | Wilson | Clopper-Pearson, two-sided | Clopper-Pearson, one-sided 95% | Jeffreys (modified) | Agresti-Coull | Rule of three |
|---|---|---|---|---|---|---|---|
| 0/15 failures (exact-marker runs) | [0, 0] | [0, 0.204] | [0, 0.218] | ≤ 0.181 | [0, 0.152] | [0, 0.239] | ≤ 0.200 |
| 0/30 failures (all runs) | [0, 0] | [0, 0.114] | [0, 0.116] | ≤ 0.095 | [0, 0.080] | [0, 0.135] | ≤ 0.100 |
| 15/15 exact markers | [1, 1] | [0.796, 1] | [0.782, 1] | ≥ 0.819 | [0.848, 1] | [0.761, 1] | ≥ 0.80 |
| 30/30 rule passes | [1, 1] | [0.886, 1] | [0.884, 1] | ≥ 0.905 | [0.920, 1] | [0.865, 1] | ≥ 0.90 |
| 0/45 (one main-02 arm, if no failure) | [0, 0] | [0, 0.079] | [0, 0.079] | ≤ 0.064 | [0, 0.054] | [0, 0.094] | ≤ 0.067 |
| 0/135 (three arms pooled, if allowed) | [0, 0] | [0, 0.028] | [0, 0.027] | ≤ 0.022 | [0, 0.018] | [0, 0.033] | ≤ 0.022 |

Formulas: Wilson upper limit at x = 0 is z²/(n + z²), so 3.841/18.841 = 0.204 for n = 15. Exact one-sided limit is 1 − α^(1/n), so 1 − 0.05^(1/15) = 0.181. Two-sided Clopper-Pearson at x = 0 equals the one-sided 97.5% limit, 1 − 0.025^(1/15) = 0.218. Bayesian posterior 95% upper quantiles for 0/15 are 0.171 under a uniform Beta(1, 16) prior and 0.118 under a Jeffreys Beta(0.5, 15.5) prior. For 0/30 they are 0.092 and 0.062.

Diagnostic quantities for main-01 (computed):
- Specificity: 15/15, Wilson [0.80, 1].
- NPV: 15/15, Wilson [0.80, 1]. Equivalently, failure given exact is 0/15, ≤ 0.20.
- Sensitivity: 0/0, undefined. There is no interval, because no failure occurred.
- PPV: 0/0, undefined, because no noncompliant marker occurred.

### Inferences
- In report.json `rates`, add `ci95_wilson: [lo, hi]` and `ci95_exact: [lo, hi]` (Clopper-Pearson) next to every `{numerator, denominator, value}`. When the denominator is 0, emit `null` intervals, as the value already is. Name the method and the confidence level in the JSON. Never emit a Wald interval, which is [0, 0] here.
- Change the prose from "0 failures" to "0/15 exact-marker runs failed a checked rule (95% CI 0–20%, Wilson). The data cannot exclude a failure rate of about 1 in 5 in this configuration." That is the honest headline of main-01.
- Do not imply that the 0/30 bound applies to the marker question. Only the 15 condition-B runs inform the marker tables. The 0/30 bound applies to "rule failure in this configuration and these tasks", pooled across A and B. The pooled figure is legitimate only if A and B are assumed not to differ.
- Wilson against Clopper-Pearson: Brown et al. and Bowyer et al. both favour Wilson, or Jeffreys, for average coverage. Clopper-Pearson guarantees at least nominal coverage. For a zero-event audit claim ("at most X%"), the exact one-sided bound is the easiest to defend. Pre-specify one method as primary to avoid choosing an interval after the fact. Recommended: Wilson primary, exact as a sensitivity analysis.

### Gaps
- I did not retrieve the full Hanley and Lippman-Hand text. The rule's derivation above is standard and is verified by the computation, not quoted.
- Interval coverage results assume independent and identically distributed (i.i.d.) Bernoulli runs. See section 5 for why that is only conditionally true.

## 2. LLM-eval error-bar methodology and run-to-run nondeterminism

### Takeaway
The LLM-eval literature converges on four practices: treat each eval item as a draw, cluster standard errors when items are related, use paired differences when the same items are compared, and repeat samples per item but average within the item rather than pooling. Even "deterministic" settings produce materially different outputs from run to run. For Canary Lab, each condition is a stochastic process, and repetitions are the unit of variation. But with only 3 tasks, CLT-based clustered SEs are not usable. Report per-task counts and exact or Bayesian intervals.

### Cited findings
- Miller E. "Adding error bars to evals: a statistical approach to language model evaluations." arXiv:2411.00640, Nov 2024 (Anthropic) — [abstract](https://arxiv.org/abs/2411.00640); [HTML](https://arxiv.org/html/2411.00640):
  - Questions are treated as draws from a super-population. Variance has two parts: which questions were drawn (variance of the conditional means) and the randomness of each answer (expected conditional variance).
  - Clustered SE (Eq. 4) adds within-cluster cross-terms: SE_clustered = sqrt(SE_CLT² + (1/n²) Σ_c Σ_i Σ_{j≠i} (s_ic − s̄)(s_jc − s̄)). In the paper's real-data examples, clustered SEs were up to about 3× the naive SE.
  - Resample each question K times and use question-level means. Conditional variance falls to σ²/K, with diminishing returns. In a uniform-difficulty example, K = 2, 4 and 6 cut variance by 1/3, 1/2 and 5/9, with a ceiling of 2/3. Do not compute an SE as if all K×N answers were independent.
  - Do not lower temperature to cut variance. It can bias scores, and it moves variance into the question means.
  - Paired differences (Eqs. 7–8): when two models answer the same questions, compute the SE from question-level differences. This reduces variance when scores are positively correlated. Report that correlation.
  - Power: n = (z_{α/2} + z_β)² (ω² + σ_A²/K_A + σ_B²/K_B)/δ². With illustrative inputs (ω² = 1/9, δ = 0.03, 80% power) this gives about 1,000 questions.
- Bowyer et al. (2025, arXiv:2503.01747): there are "no readily available frequentist methods tailored to clustered data" at small n. A Bayesian clustered beta-binomial model was the only method tested that reached nominal coverage across sample sizes. For paired comparisons they recommend a paired Bayesian method, or unpaired Bayes as a simpler fallback — [HTML](https://arxiv.org/html/2503.01747).
- Atil B, et al. "Non-determinism of 'deterministic' LLM settings." arXiv:2408.04667 (v5, Apr 2025). They tested five LLMs configured to be deterministic on eight tasks, with 10 runs each. Accuracy varied up to 15% across naturally occurring runs, and the best-to-worst gap reached up to 70%. No model consistently gave repeatable accuracy or identical strings — [arXiv](https://arxiv.org/abs/2408.04667).
- He H (Thinking Machines Lab). "Defeating nondeterminism in LLM inference," 10 Sep 2025. Qwen3-235B-A22B-Instruct-2507 at temperature 0 gave 80 unique completions out of 1,000 for one prompt, and the most common completion appeared 78 times. All 1,000 matched for 102 tokens and diverged at token 103 ("Queens, New York" in 992 and "New York City" in 8). The cause is attributed to batch-size-dependent kernels (lack of batch invariance) under varying server load, not to concurrency alone — [blog](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/). A critique reports that batch-invariant kernels run up to 63% slower on its hardware — [arXiv:2601.17768](https://arxiv.org/pdf/2601.17768).
- Yao S, Shinn N, Razavi P, Narasimhan K. "τ-bench: a benchmark for tool-agent-user interaction in real-world domains." arXiv:2406.12045, Jun 2024. It introduces pass^k, the probability that all k independent trials of a task succeed, as a reliability metric. gpt-4o succeeded on fewer than 50% of tasks, and its pass^8 in retail was below 25% — [arXiv](https://arxiv.org/abs/2406.12045). (The abstract has no formal definition. The "all k trials succeed" definition is the paper's standard one, which I recall but did not re-verify from the full text.)

### Computed: pass@k vs pass^k under i.i.d. per-run success p
| p (per run) | pass@5 | pass^5 | pass^15 |
|---|---|---|---|
| 0.95 | ≈1.00 | 0.774 | 0.463 |
| 0.90 | ≈1.00 | 0.590 | 0.206 |
| 0.80 | ≈1.00 | 0.328 | 0.035 |

### Inferences
- Canary Lab's 5 repetitions per task per condition are Miller's K. The right summary is per-task (per-cell) proportions. The aggregate is then a mean over 3 fixed tasks, not over 15 or 30 independent items.
- 15/15 rule passes in condition B gives Wilson pass^1 ≥ 0.80. If true per-run compliance were 0.95, a 15-run streak of passes would still happen 46% of the time (computed above). So "15/15" is weak evidence of high reliability.
- Nondeterminism makes repeated runs informative, because they are real draws from the configuration's output distribution. It also means a result is tied to backend state, such as batching and model-serving revision. Record serving-side identifiers where available. The protocol already does this.
- Report a per-task pass^5 (all 5 repetitions pass) alongside the pass rate, to make reliability visible. Clearly label it descriptive.

### Gaps
- I found no published study that quantifies run-to-run variance for agentic coding harnesses specifically, with full sessions and tool use, as opposed to single completions. Variance in agent runs is plausibly larger, but this is unverified.
- I did not verify the exact Atil et al. models and tasks beyond the abstract.

## 3. Diagnostic-accuracy framing and sample size

### Takeaway
Treat marker noncompliance as an index test and checked rule failure as the reference standard, and report the 2×2 table with STARD-style flow accounting. Sensitivity precision is limited by the number of failures, not the number of runs. At a plausible failure prevalence of 5 to 20%, a 15-marker-run arm expects 0.75 to 3 failures and has essentially zero chance (< 0.02%) of reaching 10. Estimating sensitivity to ±0.15 to 0.20 needs about 20 to 45 failures in marker-bearing runs, which means about 100 to 900 condition-B runs depending on prevalence. PPV and NPV depend on prevalence, and they are only meaningful at the prevalence of the configuration that produced them.

### Cited findings
- STARD 2015: Bossuyt PM, Reitsma JB, Bruns DE, et al. "STARD 2015: an updated list of essential items for reporting diagnostic accuracy studies." *BMJ* 2015;351:h5527, doi:10.1136/bmj.h5527. It is a 30-item checklist that replaces the 25-item 2003 version, and it now expects a participant flow diagram in all reports. It is described as a minimum set — [doi](https://www.doi.org/10.1136/BMJ.H5527); [PMC4623764](https://pmc.ncbi.nlm.nih.gov/articles/PMC4623764/). STARD is listed on the EQUATOR network.
- Buderer NM. "Statistical methodology: I. Incorporating the prevalence of disease into the sample size calculation for sensitivity and specificity." *Acad Emerg Med* 1996;3(9):895–900, doi:10.1111/j.1553-2712.1996.tb03538.x. Sample size is derived from the desired precision, the expected sensitivity and specificity, and the prevalence. The usual form is n_diseased = z² Se(1−Se)/d², with total N = n_diseased/prevalence, and similarly n_nondiseased = z² Sp(1−Sp)/d², with N = n_nondiseased/(1−prevalence) — [Scilit record](https://www.scilit.net/publications/c1ccbb77afb15334c0accba6a9388c10). The formula is described via secondary sources. I did not retrieve the original full text.
- Flahault A, Cadilhac M, Thomas G. "Sample size calculation should be performed for design accuracy in diagnostic test studies." *J Clin Epidemiol* 2005;58(8):859–862, doi:10.1016/j.jclinepi.2004.12.009. It gives exact-binomial sample-size tables. The test is framed as showing that the lower confidence limit exceeds a minimal acceptable sensitivity with given power — [UNIGE archive](https://archive-ouverte.unige.ch/unige:47147). The R package MKpower implements it (`power.diagnostic.test`) and notes errors in some of the paper's appendix equations — [MKpower docs](https://search.r-project.org/CRAN/refmans/MKpower/html/power.diagnostic.test.html). A survey cited in the same search found only 4.7% of diagnostic accuracy studies reported considering sample size.

### Computed: chance of observing failures in a 15-marker-run arm (i.i.d. Bernoulli)
| Failure prevalence p | Expected failures in 15 B runs | P(≥1) | P(≥5) | P(≥10) |
|---|---|---|---|---|
| 0.05 | 0.75 | 0.537 | 0.0006 | 2×10⁻¹⁰ |
| 0.10 | 1.5 | 0.794 | 0.013 | 2×10⁻⁷ |
| 0.20 | 3.0 | 0.965 | 0.164 | 1×10⁻⁴ |

P(at least one failure) for n runs: at p = 0.05 it is 0.54, 0.79, 0.90 and 0.999 for n = 15, 30, 45 and 135. At p = 0.02 it is 0.26, 0.46, 0.60 and 0.94. A single failure gives a 2×2 table with one row of one, which is not an estimate.

### Computed: condition-B runs needed to observe ≥ k failures
| p | k = 1 (80% / 90% chance) | k = 10 (expected / 80% / 90%) | k = 20 (expected / 80% / 90%) |
|---|---|---|---|
| 0.05 | 32 / 45 | 200 / 249 / 282 | 400 / 471 / 515 |
| 0.10 | 16 / 22 | 100 / 124 / 140 | 200 / 234 / 256 |
| 0.20 | 8 / 11 | 50 / 61 / 69 | 100 / 116 / 126 |
In the A/B/C design only 1/3 of runs carry a marker, so total runs per arm are 3× these numbers, unless the diagnostic question gets its own B-only cohort.

### Computed: sensitivity CI width once k failures are observed
| Failures k | Observed Se 0.5: Wilson (width) | Se 0.5: CP (width) | Observed Se 0.8: Wilson (width) | Se 0.8: CP (width) |
|---|---|---|---|---|
| 5 | [0.12, 0.77] (0.65) | [0.05, 0.85] (0.80) | [0.38, 0.96] (0.59) | [0.28, 0.99] (0.71) |
| 10 | [0.24, 0.76] (0.53) | [0.19, 0.81] (0.63) | [0.49, 0.94] (0.45) | [0.44, 0.97] (0.53) |
| 20 | [0.30, 0.70] (0.40) | [0.27, 0.73] (0.46) | [0.58, 0.92] (0.34) | [0.56, 0.94] (0.38) |
| 40 | [0.35, 0.65] (0.30) | [0.34, 0.66] (0.32) | [0.65, 0.90] (0.24) | [0.64, 0.91] (0.27) |
Ten failures still leave a sensitivity interval about half the unit interval wide. Twenty failures is the minimum for a statement like "the marker catches most failures".

### Computed: Buderer totals (95%, half-width d)
| Expected Se | d | Failures needed | Total B runs at 5% | at 10% | at 20% |
|---|---|---|---|---|---|
| 0.5 | 0.20 | 24 | 480 | 240 | 120 |
| 0.5 | 0.15 | 43 | 854 | 427 | 213 |
| 0.7 | 0.20 | 20 | 403 | 202 | 101 |
| 0.7 | 0.15 | 36 | 717 | 359 | 179 |
| 0.9 | 0.15 | 15 | 307 | 154 | 77 |
| 0.9 | 0.10 | 35 | 691 | 346 | 173 |
Specificity is cheap because passing runs are the majority. Sp = 0.95 ± 0.05 needs 73 passing runs (about 77 to 91 total). Sp = 0.90 ± 0.05 needs 138.

Exact Flahault-style design (smallest number of failures so the one-sided 95% Clopper-Pearson lower limit exceeds Se₀ with 80% power when the true value is Se₁): Se₁ 0.9 vs Se₀ 0.7 needs 28. Se₁ 0.8 vs Se₀ 0.6 needs 36. Se₁ 0.7 vs Se₀ 0.5 needs 37. Se₁ 0.9 vs Se₀ 0.8 needs 82. (Computed by direct search. Not cross-checked against the published tables.)

### Computed: PPV/NPV and likelihood ratios (illustrative Se 0.6, Sp 0.95)
LR+ = Se/(1−Sp) = 12.0. LR− = (1−Se)/Sp = 0.42. PPV/NPV: 0.39/0.98 at 5% prevalence, 0.57/0.96 at 10%, 0.75/0.91 at 20%. In 135 B runs at 10% prevalence you would expect about 14 flags: about 8 true and 6 false.

### Inferences
- main-02 as drafted (15 B runs per arm) cannot estimate sensitivity. Its realistic goal is to detect whether any disagreement cell is non-empty, and even that has only a 54 to 97% chance per arm at a 5 to 20% failure rate. Say this in the protocol before collection, so a null result is not read as evidence that the marker works.
- Add a sample-size table (the "runs needed" table above) to docs/follow-up-protocol.md with the assumed prevalences stated. Pick the target explicitly: "observe ≥ 1 failure with 80% probability", or "estimate Se ± 0.2".
- If the diagnostic question matters, run a dedicated B-only cohort in the arm most likely to fail, probably 02a low effort or 02c harder tasks, sized for about 20 failures. A/B/C runs answer the "does the marker cost anything" question instead. Enriching for failures (choosing a high-failure configuration) is fine for sensitivity and specificity, which are prevalence-independent if the spectrum is similar. It invalidates PPV/NPV for other settings, so report PPV only with its prevalence.
- STARD items worth adopting directly: a flow diagram (planned → recorded → final response observed → behaviour evaluable → 2×2), cross-tabulation of index test by reference standard including indeterminate results (malformed vs absent marker; unevaluable rules), the intended sample size and how it was determined, and estimates with 95% CIs. The all-run accounting table already covers much of the flow-diagram item.
- Two reference standards should be reported separately: checked rule failure and feature incompleteness (signal-versus-work). Each has its own prevalence and its own sensitivity.

### Gaps
- I have no empirical prior for failure prevalence in this fixture under low effort or a smaller model. The 5/10/20% scenarios are assumptions. Use pilot results only to sanity-check them, and do not size from 6 pilot runs.
- I did not access the Buderer or Flahault full texts. The formulas follow the standard forms described in secondary sources and the MKpower documentation.

## 4. Experimental design: blocking, preregistration, sequential stopping, non-inferiority

### Takeaway
Canary Lab's randomized blocks and fixed-n, no-replacement rule are sound. Three upgrades: (a) pre-specify the interval method and decision rules. (b) If you want to stop early or extend, use anytime-valid confidence sequences, or pre-specify a group-sequential plan, instead of peeking at fixed-n intervals. (c) State "does the marker hurt task performance" as a non-inferiority question with a stated margin, and say plainly that 15 runs per condition only supports a margin of about 20 percentage points.

### Cited findings
- Lakens D. "Equivalence tests: a practical primer for t tests, correlations, and meta-analyses." *Soc Psychol Personal Sci* 2017;8(4):355–362, doi:10.1177/1948550617697177. In the two one-sided tests (TOST) procedure you specify equivalence bounds from the smallest effect size of interest. If no principled bound exists, you can set the bound to the smallest effect the study has power to detect. The paper documents widespread unsupported "no effect" claims from non-significant results. The R package is TOSTER — [PMC5502906](https://pmc.ncbi.nlm.nih.gov/articles/PMC5502906); [TOSTER vignette](https://cran.r-project.org/web/packages/TOSTER/vignettes/IntroductionToTOSTER.html).
- Howard SR, Ramdas A, McAuliffe J, Sekhon J. "Time-uniform, nonparametric, nonasymptotic confidence sequences." *Ann Statist* 2021;49(2):1055–1080, doi:10.1214/20-AOS1991. Confidence sequences keep coverage simultaneously at every sample size, so you can monitor continuously and stop at any time without inflating error — [Project Euclid](https://projecteuclid.org/journals/annals-of-statistics/volume-49/issue-2/Time-uniform-nonparametric-nonasymptotic-confidence-sequences/10.1214/20-AOS1991.full); [arXiv:1810.08240](https://arxiv.org/abs/1810.08240v3).
- Miller (2024) recommends paired analysis whenever the same items are compared, because it reduces variance when outcomes correlate — [arXiv HTML](https://arxiv.org/html/2411.00640). In Canary Lab, A, B and C runs within a task/repetition block share task and rough time. The block is the natural pairing unit.

### Computed: non-inferiority / precision for condition B or C vs A (feature success)
- Newcombe hybrid-score 95% CI for a difference when both arms are 15/15 is [−0.20, +0.20]. For 14/15 vs 15/15 it is [−0.30, +0.14]. For 45/45 vs 45/45 it is [−0.079, +0.079]. The 90% CI for 15/15 vs 15/15, which is what a one-sided 5% non-inferiority test uses, is [−0.15, +0.15].
- So with 15 per condition, a perfect tie in both arms only rules out a marker-induced drop larger than about 15 to 20 pp.
- Normal-approximation n per condition for non-inferiority (80% power, true difference 0):

| Baseline success | Margin 10 pp | 15 pp | 20 pp |
|---|---|---|---|
| 0.95, one-sided α = 0.05 | 59 | 27 | 15 |
| 0.95, one-sided α = 0.025 | 75 | 34 | 19 |
| 0.90, one-sided α = 0.05 | 112 | 50 | 28 |
| 0.99, one-sided α = 0.05 | 13 | 6 | 4 |

  The normal approximation is unreliable near 0.99 and 1. Use exact or Bayesian methods there.
- Power of a one-sided Fisher exact test (α = 0.05) to detect a drop from A = 0.95: with 15 per condition, 0.19 for B = 0.80, 0.44 for B = 0.70, 0.67 for B = 0.60, and 0.84 for B = 0.50. With 45 per condition, 0.60, 0.92, 0.99 and ≈1.0.

### Inferences
- In the follow-up protocol, replace "described only, never as an effect estimate" with a pre-specified non-inferiority statement. For example: "We will report the B−A and C−A differences in feature success with 90% Newcombe intervals. We call the marker non-inferior at a 20 pp margin if the lower limit exceeds −0.20." Also state that the study is not powered for margins below about 20 pp at 15 per condition. This turns a descriptive contrast into a falsifiable claim and keeps the limitation explicit.
- Use block-paired analysis. Within each task/repetition block, record the A/B/C outcome triple. If outcomes vary, a paired or stratified analysis by task, such as an exact conditional test or Mantel-Haenszel stratified by task, uses the blocking. With all-pass data, pairing is moot.
- Stopping rule: keep fixed n per arm as primary. If you want an "extend until k failures or N_max" design to reach the diagnostic targets in section 3, preregister the rule before collection: stop at the first of 20 failures in B runs or N_max B runs. Report sensitivity with a confidence sequence, or accept that inverse-sampling designs (stop at k events) need their own estimators. Report the fixed-n Clopper-Pearson interval as secondary and label it.
- Preregistration: the protocol's local freeze is good practice. Publishing the frozen plan (OSF or a tagged git commit with a public timestamp) before collection turns it into a real preregistration. The interval method, margins, prevalence assumptions and stopping rule should all be in the frozen text.

### Gaps
- I did not retrieve a specific ML/LLM-eval preregistration guideline in this pass. Candidate venues (an OSF registered-report style, NeurIPS Datasets & Benchmarks checklists) are unverified here.
- The Newcombe 1998 citation (*Stat Med* 17:873–890, "Interval estimation for the difference between independent proportions: comparison of eleven methods") comes from memory, not verified in this session. The computed numbers use the standard hybrid Wilson-score formula.
- I did not look up group-sequential (Pocock, O'Brien-Fleming, Lan-DeMets) references. Confidence sequences are the cited alternative.

## 5. Repeated-measures dependence and the inferential target

### Takeaway
Canary Lab's runs are repeated draws from one fixed configuration on 3 fixed tasks, not samples of "agents" or of "coding tasks". Inference is valid conditional on that configuration and those tasks. Intervals should be per task, or for the pooled run-level proportion with an explicit statement of conditioning. Cluster-robust SEs and mixed models need many clusters. With 3 tasks they are not usable, and a Bayesian beta-binomial or per-task exact reporting is the defensible option.

### Cited findings
- Miller (2024) frames eval items as draws from a super-population, with variance split between item selection and per-answer randomness. Repeated answers to the same item are not independent, so do not pool K×N answers into one SE. Clustered SEs were up to 3× naive SEs in real evals — [arXiv HTML](https://arxiv.org/html/2411.00640).
- Bowyer et al. (2025): no readily available small-sample frequentist method handles clustered evals well. Their Bayesian clustered beta-binomial model was the only method tested that reached nominal coverage across sample sizes — [arXiv HTML](https://arxiv.org/html/2503.01747).
- Run-level stochasticity is real even at nominally deterministic settings, so repeated runs of one configuration are genuine random draws from that configuration's distribution — [Atil et al.](https://arxiv.org/abs/2408.04667); [Thinking Machines](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/).

### Computed: design effect DE = 1 + (m−1)ρ for within-task correlation ρ
| Cluster size m | ρ = 0.1 | ρ = 0.3 | ρ = 0.5 |
|---|---|---|---|
| 5 (repetitions per task × condition) | DE 1.4: 15 runs ≈ 10.7 effective | DE 2.2: ≈ 6.8 | DE 3.0: ≈ 5.0 |
| 15 (per task per arm, 3 conditions × 5) | DE 2.4: 45 runs ≈ 18.7 effective | DE 5.2: ≈ 8.7 | DE 8.0: ≈ 5.6 |
If failures concentrate in one task, which is plausible since tasks differ in difficulty, the effective sample for a "general" rate approaches the number of tasks, 3.

### Inferences
- State the estimand explicitly in experiment.md and the report: "the per-run probability, for this pinned agent configuration on these three tasks, that …". Under that conditional estimand, runs within a task are approximately i.i.d. Bernoulli draws, given fresh sessions and a stable backend, and the binomial intervals in sections 1 and 3 are appropriate per task. Pool across tasks only as a fixed-weight average of task-specific rates. That conditioning answers "what does 0/15 bound" honestly.
- Do not claim a population over tasks or models. With 3 tasks, any between-task variance estimate (random effects, cluster-robust SE) rests on 3 clusters. Cluster-robust SEs are known to be anti-conservative with few clusters (wild-cluster bootstrap literature, not verified this session). A mixed model would be dominated by its prior or would fail to converge.
- If main-02c adds tasks, more tasks with fewer repetitions each buys more generalizability than more repetitions. Miller's resampling result shows diminishing returns past K ≈ 4 to 6 per item. A future design such as 10 to 20 tasks × 3 repetitions would make clustered intervals (Miller Eq. 4) or a beta-binomial model, via bowyer's bayes_evals, meaningful.
- Each main-02 arm is a different configuration and a different estimand. Do not pool arms into one sensitivity estimate unless the pooling is preregistered and the estimand is defined as a mixture over those configurations. The protocol's "report each arm as its own cohort" is statistically correct.
- Report per-task 2×2 tables (already planned) plus the pooled table with its conditioning stated. If failures appear in only one task, say so: the warning-signal result then describes that task.
- Time and backend drift: blocks spread over time partly protect A/B/C comparisons from serving-side drift. Record wall-clock timestamps and any backend or model revision identifiers, and check that failures are not clustered in time. Use a runs test or a plot by block order, described only.

### Gaps
- I did not verify a citation for few-cluster cluster-robust inference (e.g. Cameron, Gelbach and Miller 2008 on the wild cluster bootstrap) in this session. The claim that few clusters bias cluster-robust SEs downward is standard econometrics but is unsourced here.
- I found no empirical estimate of within-task intraclass correlation for agent coding runs. The ρ values in the design-effect table are illustrative.

### Concrete change list for Canary Lab (summary of the inferences above)
1. `lab/report.py` / report.json: add `ci95_wilson` and `ci95_exact` (Clopper-Pearson; one-sided exact bound for zero cells) to every rate. Put the method name in the JSON, use null when the denominator is 0, and never use Wald. Optional: a Jeffreys or Bayesian posterior interval as secondary.
2. Article and report text: headline main-01 as "0/15 (95% CI 0–20%)" and "15/15 exact markers (≥ 80%)".
3. follow-up-protocol.md: add the section 3 sample-size table with assumed prevalences. State that with 15 B runs per arm P(≥1 failure) is 0.54, 0.79 or 0.97 at 5, 10 or 20% prevalence and that sensitivity is not estimable. Optionally add a dedicated B-only diagnostic cohort sized for about 20 failures.
4. Preregister before collection: the primary interval method, the estimand (conditional on configuration and tasks), a non-inferiority margin for C−A and B−A (realistically 20 pp at 15 per condition, with 90% Newcombe intervals), and any sequential "stop at k failures or N_max" rule with a confidence-sequence analysis.
5. Adopt STARD 2015 items: a flow diagram, a 2×2 table including indeterminates, an explicit sample-size rationale, and CIs on sensitivity, specificity, PPV and NPV. Report PPV/NPV only alongside the observed prevalence.
6. Add a per-task pass^5 column, descriptive only, to show reliability across repetitions.
