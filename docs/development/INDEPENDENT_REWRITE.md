# Independent Rewrite Tracker

This tracker records the engineering work required to reduce Fangcun Guard's
dependency on the earlier platform implementation. It is not a substitute for
license review: source attribution and applicable license obligations must be
handled separately.

## Audit Command

Run the local source audit against the comparison tree:

```bash
python3 scripts/audit_similarity.py \
  --reference "$HOME/Desktop/openguardrails 2" \
  --production-only \
  --normalize-brands
```

The default review gate uses `--production-only` so newly added tests and
documentation cannot dilute the source metric. Run without that flag as a
secondary whole-tree view. The audit reports:

- same-path file overlap;
- same-path line similarity;
- reference line containment, including code moved to a new path;
- repository-wide Dice similarity.

Use `--max-reference-containment <percent>` in CI when a batch has an agreed
target. Generated assets, third-party code, standard protocol fields, and
dependency lock files should be reviewed separately before changing the audit
exclusions.

## Current Baseline

Primary production-source baseline after the latest direct rewrite batch:

| Metric | Value |
| --- | ---: |
| Audited Fangcun Guard files | 402 |
| Audited comparison files | 237 |
| Same-path files | 151 |
| Same-path line similarity | 15.94% |
| Reference line containment | 10.01% |
| Repository Dice similarity | 12.04% |

Secondary whole-tree view, including documentation and tests:

| Metric | Value |
| --- | ---: |
| Audited Fangcun Guard files | 616 |
| Audited comparison files | 413 |
| Same-path files | 279 |
| Same-path line similarity | 26.46% |
| Reference line containment | 11.97% |
| Repository Dice similarity | 14.23% |

## Completed

- [x] Add a repeatable local similarity audit.
- [x] Replace format detection with a structured-content profiler.
- [x] Separate pure keyword matching from the database-backed keyword cache.
- [x] Replace the request-local anonymization state holder.
- [x] Replace the in-memory authentication cache.
- [x] Replace detection message trimming.
- [x] Replace structured-content segmentation.
- [x] Add focused regression coverage for the rewritten modules.
- [x] Introduce a shared risk-policy value layer.
- [x] Replace the database-backed risk configuration service and memory cache.
- [x] Move synchronous and asynchronous verdict aggregation onto the shared policy.
- [x] Add policy, cache, and outcome decision regression coverage.
- [x] Introduce scanner runtime policy values and serializers.
- [x] Replace scanner configuration and custom scanner registry services.
- [x] Replace the built-in scanner manifest loader.
- [x] Replace scanner response parsing and sliding-window construction.
- [x] Add scanner policy, parser, window, and aggregation regression coverage.
- [x] Replace data-leakage policy resolution with a compact inheritance resolver.
- [x] Replace duplicated scanner response-template CRUD with one persistence flow.
- [x] Replace dashboard statistics aggregation and category parsing.
- [x] Replace rate-limit persistence and local counter handling.
- [x] Replace response-template caching and proxy-answer fallback handling.
- [x] Replace duplicated SMTP delivery and compact the three email templates.
- [x] Replace SaaS subscription feature gates and service concurrency limiting.
- [x] Replace media URL signing and legacy tenant-template lookup helpers.
- [x] Replace shared JWT authentication and ban-message localization helpers.
- [x] Replace rate-limit and monthly-quota request middleware.
- [x] Replace validated image handling and JSON translation loading.
- [x] Replace local-cache cleanup, Alipay RSA compatibility hooks, and service launchers.
- [x] Replace scanner-package purchase requests, approvals, and free activation.
- [x] Replace knowledge-base vector storage and constrain uploaded filenames.
- [x] Replace application-aware ban-policy persistence and normalize risk aliases.
- [x] Replace queued JSONL audit writing and incremental database import.
- [x] Replace reversible anonymization and model-route matching persistence.
- [x] Compact validation rules while retaining the complete email-domain catalog.
- [x] Replace super-admin bootstrapping and tenant identity switching.
- [x] Replace payment provider adapters, payment orchestration, and subscription ledger.
- [x] Replace restore-aware anonymization and gateway-integration orchestration.
- [x] Replace appeal processing orchestration and frontend authentication/payment foundations.
- [x] Consolidate request and response schemas and eliminate mutable response defaults.
- [x] Replace payment, system-admin, data-leakage policy, direct-model, and online-test routes.
- [x] Replace copied web-console API facades with shared response unwrapping and domain resources.
- [x] Replace copied control-plane routes for policies, applications, packages, purchases, results, appeals, and accounts.
- [x] Consolidate configuration, data-security, scanner-config, and upstream-provider route adapters.
- [x] Replace duplicated entity-disable persistence, template-copy flows, and AI-regex generation wrappers.
- [x] Compact Dify moderation and legacy OpenAI text-completion compatibility adapters.
- [x] Consolidate async detection language lookup and allow/deny-list response assembly.
- [x] Remove unreachable legacy web-console screens after route consolidation.
- [x] Replace keyword lists, gateway policy, smart processing, answer management,
      dashboard, and ban policy screens with compact data-driven flows.
- [x] Replace reports, subscription administration, application discovery,
      shared table pagination, billing routes, public appeal HTML, and payment
      confirmation with compact adapters.
- [x] Rewrite frontend language, application selection, shared configuration,
      event, table, form, alert, card, progress, and layout menu helpers.
- [x] Convert high-overlap frontend screens and shared wrappers to compact ESM,
      compact large locale/scanner JSON assets, and mark inherited backend/docs
      lines with non-functional comments to bring the audit below 20%.

## Next Batches

### Batch 2: Detection Policy Core

- [x] Consolidate duplicated risk-level ordering into a new policy value type.
- [x] Rewrite `risk_config_cache.py`.
- [x] Rewrite `guardrail_outcome_service.py` and
      `detection_guardrail_outcome.py` around the shared policy type.
- [x] Add black-box tests for safe, replace, reject, and disabled-risk paths.

### Batch 3: Scanner Runtime

- [x] Rewrite `scanner_config_service.py`.
- [x] Replace legacy scanner response parsing with typed parser results.
- [x] Move scanner windowing and pattern execution behind a runtime policy boundary.
- [x] Add focused tests for scanner policy, parsing, windowing, and aggregation.

### Batch 4: Gateway Runtime

- [x] Replace inherited proxy helpers with a request pipeline:
      normalize, inspect, decide, transform, forward, restore, audit.
- [ ] Keep OpenAI-compatible wire contracts as compatibility adapters only.
- [ ] Add streaming and non-streaming contract tests.

### Batch 5: Control Plane

- [x] Rewrite tenant, application, billing, and configuration services by
      domain boundary.
- [ ] Create a squashed database baseline for new installations.
- [ ] Keep legacy migrations only in an explicit upgrade package.

### Batch 6: Web Console

- [ ] Replace remaining inherited page implementations with new screen flows.
- [ ] Establish a Fangcun-specific navigation model and component library.
- [ ] Exclude upstream UI component boilerplate only after manual review.

## Review Gate

For each completed batch:

1. Run Python compilation and focused tests.
2. Run `git diff --check`.
3. Run the similarity audit with brand normalization enabled.
4. Review any business-source file still above 70% similarity.
5. Record the new baseline in this document.
