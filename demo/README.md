# Demo artifact — CSV monthly-summary (Iteration 1, stopped at Gate 2)

These modules were produced by a real run of the EDD relay (`mode:"iteration"`,
iteration 1) against the problem *"a CLI that reads a CSV of transactions and
prints a per-month income/expense/net summary."* The full conversation that
produced them is in [`../ledger/ledger.jsonl`](../ledger/ledger.jsonl) (seq 3–134;
roadmap and gates are seq 0–2 and 135–136).

## Status: intentionally incomplete

All six behaviours passed their per-behaviour expectations, but the iteration
**did not** deliver a shippable increment, and the Owner chose **stop** at Gate 2.
The six modules (`csv_parser`, `calendar_month`, `ledger_entry`, `month_totals`,
`month_net`, `month_summary`) were each verified in isolation but were never wired
into a runnable command, and they disagree on the data model (the parser emits a
signed amount; the summary engine expects a kind + magnitude).

## The lesson this run surfaced

Per-behaviour Expectation-Driven verification can *all pass* while the iteration's
real goal fails, because no agent held an expectation for the **integrated,
shippable increment** — only for each behaviour alone. The relay's saving grace was
the Interpreter's delivery step: facing the Owner, it reported the gap honestly
instead of declaring success.

**Model improvement (recorded as Owner feedback, ledger seq 135):** the Examiner
should author an iteration-level *integration expectation* ("the increment runs
end-to-end") alongside the per-behaviour ones.

These files are kept only as evidence of the run; they are not part of the working
model itself.
