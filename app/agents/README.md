# agents layer technical documentation

## full pipeline used by parse-query

`AgentPipeline.parse_query` in `app/orchestrator/pipeline.py` is the authoritative sequence.

ordered stages:
1. `LanguageProcessingAgent.run(query) -> CleanQuery`
2. `IntentDetectionAgent.run(clean_query) -> IntentResult`
3. `EntityExtractionAgent.run(clean_query, intent_result) -> RawEntities`
4. `NormalizationAgent.run_entities(raw_entities) -> NormalizedEntities`
5. `ConstraintExtractionAgent.run(clean_query) -> Constraints`
6. `DomainGuardAgent.run(clean_query, intent_result) -> DomainGuardResult`
7. `AmbiguityReasoningAgent.run(intent_result, raw_entities, normalized_entities) -> AmbiguityDecision`
8. `FallbackAgent.run(normalized_entities, intent) -> FallbackDecision`
9. `UserContextAgent.run(clean_query) -> UserContext`
10. `ExecutionPlannerAgent.run(...) -> (ExecutionPlan, ExecutionGraph, CandidateExecutionPath[])`
11. `ConstraintOptimizerAgent.derive_weights(...) -> ranking weights`
12. `OutputFormatterAgent.run(...) -> FinalStructuredQuery`

the pipeline also logs each stage through `QueryLoggingAgent.run(stage, payload)` and updates learning signals with `LearningLoop`.

## finalstructuredquery contract

`FinalStructuredQuery` is defined in `app/data/models.py` and is the required execution contract for `/search` and `/execute`.

top-level fields:
- parsing and intent: `clean_query`, `intent_result`
- extraction and normalization: `raw_entities`, `normalized_entities`
- control and policy: `constraints`, `domain_guard`, `ambiguity`, `fallback`
- planning: `execution_plan`, `execution_graph`, `candidate_paths`
- personalization and learning: `user_context`, `learning_signals`, `evaluation_history`, `failure_policies`
- runtime metadata: `platform_signals`, `coordination_trace`
- execution payload: `structured_query`

execution depends on this object because `run_search` reads all control decisions from it (domain guard, plan nodes, constraints, candidate paths) and does not reconstruct intent from raw text.

## each agent responsibility

### language processing agent

file: `app/agents/language_processing.py`

input:
- raw query string

output:
- `CleanQuery` with:
  - original stripped text
  - language (`en`)
  - cleaned tokens
  - normalized text

transformations:
- unicode normalization (nfkc)
- lowercase
- punctuation cleanup by regex
- stop/noise token removal

### intent detection agent

file: `app/agents/intent_detection.py`

input:
- `CleanQuery`

output:
- `IntentResult(intent, confidence, notes, secondary_intents)`

logic:
- keyword heuristics for recipe/cart/exploratory/unsupported/default search
- multi-intent branch for recipe + cart optimization

### entity extraction agent

file: `app/agents/entity_extraction.py`

input:
- `CleanQuery`, `IntentResult`

output:
- `RawEntities`

logic:
- picks known grocery term from normalized text
- exploratory intent defaults to `snacks`
- supports candidate extraction when query contains `and`
- emits ambiguity flags like `low_confidence_entity`/`missing_entity`

### normalization agent

file: `app/agents/normalization.py`

input:
- single term (`run`) or `RawEntities` (`run_entities`)

output:
- `NormalizedItem` or `NormalizedEntities`

logic:
- llm-first normalization with schema-constrained output
- deterministic fallback maps on llm failure
- synonym memory lookup/remember cycle (`SynonymMemoryAgent`)
- canonical mapping includes explicit mayo -> mayonnaise handling
- unresolved entities identified by confidence threshold

### constraint extraction agent

file: `app/agents/constraint_extraction.py`

input:
- `CleanQuery`

output:
- `Constraints`

logic:
- regex extraction for budget and servings
- preference keyword extraction (cheap, organic, healthy, premium, fresh)
- ranking weight bootstrap
- conflicting preference notes
- inferred quantity multiplier from servings

### domain guard agent

file: `app/agents/domain_guard.py`

input:
- `CleanQuery`, `IntentResult`

output:
- `DomainGuardResult`

logic:
- blocks unsupported intent and empty normalized queries
- otherwise allows execution

### ambiguity reasoning agent

file: `app/agents/ambiguity_reasoning.py`

input:
- `IntentResult`, `RawEntities`, `NormalizedEntities`

output:
- `AmbiguityDecision`

logic:
- computes `single_clear_entity` with confidence and flag checks
- skips ambiguity for single high-confidence entity path
- enables delayed resolution/candidate enumeration/backoff strategies when needed

### fallback agent

file: `app/agents/fallback.py`

input:
- `NormalizedEntities`, `QueryIntent`

output:
- `FallbackDecision`

logic:
- exploratory intent -> exploratory fallback alternatives
- unresolved entities -> ambiguity fallback alternatives
- otherwise no fallback

### user context agent

file: `app/agents/user_context.py`

input:
- `CleanQuery`

output:
- `UserContext`

logic:
- reads/writes profile from shared memory
- derives preferences, dietary patterns, budget habits
- updates long-term preference and consumption counters
- computes predicted needs when absent

### execution planner agent

file: `app/agents/execution_planner.py`

input:
- `IntentResult`, `Constraints`, `UserContext`, `candidate_entities`

output:
- `ExecutionPlan`, `ExecutionGraph`, candidate path list

logic:
- initializes baseline operations: matching -> ranking -> deals
- adaptive flags can remove deals/ranking nodes
- appends recipe/cart nodes by primary intent/secondary intents
- generates up to three candidate execution paths with descending confidence

### constraint optimizer agent

file: `app/agents/constraint_optimizer.py`

input:
- base weights, query preferences, user preferences

output:
- normalized ranking weights

logic:
- boosts price for cheap/budget
- boosts rating for premium
- boosts delivery for fresh
- normalizes sum to 1.0
- provides candidate scoring for budget optimization decisions

### product matching agent

file: `app/agents/product_matching.py`

input:
- `StructuredQuery`, optional `NormalizedItem`

output:
- `UnifiedProduct`

logic:
- calls data layer `match_products_for_entity`
- applies max/min price and brand filters
- if filters remove all but raw match exists, relaxes to top-k cheapest fallback

### ranking agent

file: `app/agents/ranking.py`

input:
- `UnifiedProduct`, optional ranking preferences

output:
- `RankingResult`

logic:
- computes weighted composite score from price/delivery/rating/discount
- supports price-first sorting when price preference threshold is met

### deal detection agent

file: `app/agents/deal_detection.py`

input:
- `UnifiedProduct`

output:
- `DealResult`

logic:
- marks discount deals at >= 5%
- marks trending deals at >= 10%

### evaluation agent

file: `app/agents/evaluation.py`

input:
- `FinalStructuredQuery`, `FinalResponse`

output:
- `EvaluationResult`

logic:
- emits failure signals for ambiguity/quality/constraint issues
- computes quality score with penalties/bonuses
- sets retry flag based on failure signal presence
- special case: single clear entity with empty results adds correction note without forced ambiguity retry

### output formatter agent

file: `app/agents/output_formatter.py`

input:
- all stage outputs

output:
- `FinalStructuredQuery`

logic:
- deterministic assembly only; no additional inference

## execution planner and branching in run_search

`AgentPipeline.run_search` uses planner artifacts as follows:
- candidate entities are built from `candidate_paths` and normalized primary entity
- each candidate path runs normalization -> product matching -> ranking -> deals -> response -> evaluation
- best path selected by maximum evaluation quality score
- retries are bounded by `_MAX_REASONING_RETRY_ATTEMPTS` (`3`)
- failure signals can expand candidate list or reweight constraints for subsequent retries
- selected path is recorded in `candidate_paths` and learning notes

## evaluation and retry conditions

retry loop triggers only when `EvaluationResult.should_retry` is true.

examples of retry signals in code:
- `ambiguity_failure`
- `poor_match_quality`
- `constraint_violation`
- `constraint_conflict`

policy application:
- on final non-success, matching `FailurePolicy` entries are marked `applied=True`

## ambiguity handling behavior

ambiguity is triggered when not single-clear and any of:
- exploratory intent
- multiple candidates
- ambiguity flags from extraction
- normalized confidence below threshold

ambiguity is skipped when single clear entity conditions are met:
- <= 1 candidate
- exactly one normalized entity
- confidence >= 0.85
- no ambiguity flags
- intent not exploratory

## normalization system details

normalization is llm-first but deterministic-safe:
- prompt+schema guides canonical output
- failures use explicit fallback maps
- synonym memory persists mappings and alias expansion
- `run_entities` returns canonical entities, variants, and unresolved list

this output directly controls data-layer lookup terms and candidate path generation.

## recipe and cart usage of normalization

normalization agent is reused outside parse-query:
- recipe ingredient mapping normalizes each ingredient before lookup
- cart optimization normalizes each item before platform comparison

## test command

```bash
python -m pytest -q tests/test_agents.py tests/test_pipeline.py
```
