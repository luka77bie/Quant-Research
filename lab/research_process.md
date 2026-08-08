# Lab Research Process v1.0

Every Luka Quant Research Lab study uses the same seven gates.

## 1. Question

Write one economically motivated question and the smallest result that would be
worth knowing. Explain why a strategy researcher or portfolio manager should
care before downloading new data.

## 2. Hypothesis and Falsification

State the mechanism, expected direction, strongest alternative explanation, and
the fastest result that would cause the idea to stop. A hypothesis is not a list
of possible features.

## 3. Data Contract

Freeze universe, source, availability timestamp, adjustment convention,
revision risk, dynamic eligibility, missing-data treatment, and checksum
manifest. A failed source or symbol remains visible.

## 4. Return-Blind Measurement

Construct features, regime states, and event definitions without reading the
outcomes used to judge them. Audit missingness, persistence, redundancy, and
economic meaning before any market join.

## 5. Benchmark and Evaluation

Freeze the simple benchmark, delays, costs, horizons, controls, comparison
families, and uncertainty method. Report the complete specification grid rather
than the best cell.

## 6. Decision

Choose one of `advance`, `revise with new data`, or `stop`. A negative result is
a valid portfolio artifact when the implementation and rejection are traceable.
Do not convert a nominal or boundary result into a trading claim.

## 7. Communication

Each completed study ships:

- A lab-index entry with question, status, and decision.
- Reproducible code, tests, frozen configs, and a clean-commit run manifest.
- One concise research note organized as question, mechanism, data, method,
  result, limitations, and portfolio decision.
- A technical appendix or detailed audit for reviewers who need provenance.
- A short interview explanation covering one insight, one failure, and one next
  experiment.

## AI Use

AI may implement, test, audit, and edit. The researcher remains responsible for
the economic question, frozen hypothesis, interpretation, and final decision.
Code volume is never treated as research quality.
