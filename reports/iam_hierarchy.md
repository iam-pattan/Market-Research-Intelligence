IAM Hierarchy — M&A Platform

# IAM Role Hierarchy — M&A / Sales-Intelligence Platform

Conceptual, substrate-agnostic access-control model · RBAC ceiling + ABAC scope + dual-axis data classification · hardened by a 3-lens adversarial red-team. v1 · 2026-09-12

[Summary](#exec)[Classification](#class)[Attributes](#attrs)[Roles](#roles)[Access matrix](#matrix)[Principles](#principles)[Governance](#gov)[Policies](#policies)[Red-team](#redteam)

**5**classification tiers

**15**roles (11 human + governance + 1 service)

**8**data domains (D1–D8)

**3**Critical findings fixed

**24**revisions applied

## Executive summary

A **deny-by-default**, two-axis model: **RBAC sets the capability ceiling** (what kind of data a job function may ever touch) and **ABAC predicates narrow to permitted rows/fields** (which vertical/region/account/deal). Sensitivity is a **dual axis** — confidentiality × regulatory category (none / Financial-SOX / PII-GDPR / MNPI-securities). Governance functions are mutually separated from each other and from data consumption.

The red-team closed the model's most dangerous escalation paths. Two structural fixes dominate:

1. **MNPI is a property of the signal, not one domain.** Deal-intent-bearing fit-scores (D2) and active-deal dossiers (D3) are tagged `Restricted-MNPI` at write-time and inherit the full information-barrier — closing the sibling-domain side-channel that let un-cleared Finance/Sales infer non-public deal intent outside the wall.
2. **Single-party powers are broken up.** Classification downgrades, de-identification certs, and MNPI wall-crossings all require maker-checker with a second approver from the relevant control function (Compliance/MNPI, Finance/SOX, DPO/PII); no human self-approves or approves a same-family peer-admin grant. Person-level toxic-role aggregation is blocked by **mutually-exclusive role families** evaluated on *effective* permissions across a subject's whole role+attribute set.

## Data classification tiers

Public (post-scrub)
Internal
Confidential-Financial
Restricted-PII
Restricted-MNPI

| Tier | Regulatory | Domains | Core controls |
| --- | --- | --- | --- |
| Public | none | D7 pitches (after certified scrub) | Broadly readable only after maker-checker-certified scrub strips names/deal-context/financials; un-scrubbed = Internal. |
| Internal | none | D1 company records; D2 *non-deal-intent* signals; D8 de-identified aggregates | Readable per role; competitively scoped. D2 deal-intent fields escalate to MNPI at write-time. |
| Confidential-Financial | SOX | D3 dossiers (no active deal); D6 financials (revenue/TPV/margins) | Category grants, financial-column masking for non-Finance, free-text redaction, export step-up, SOX ITGC audit. |
| Restricted-PII | GDPR/CCPA | D4 contacts & relationships | Masked/pseudonymized by default; unmask = step-up; hard residency predicate; DPO-owned DSAR/erasure; crypto-shreddable per-subject tokens. |
| Restricted-MNPI | securities | D5 deal/pipeline; D2 deal-intent fields; D3 active-deal dossiers | Ethical-wall overlay on top of ABAC: named deal-team need-to-know, Compliance-co-approved time-boxed wall-crossing, watch-list hard predicate, blackout gate, immutable per-access audit. |

## ABAC attributes

### Subject

* identity (IdP-authenticated)
* team / job function
* **role\_family** (mutually-exclusive — one consumer family per human)
* seniority / scope\_width (drives ABAC width, not a role name)
* assigned\_verticals (enumerated; wildcard forbidden for D3/D4/D5 ceilings)
* assigned\_regions / assigned\_accounts
* deal\_team\_memberships (enumerated deal ids)
* mnpi\_clearance
* auth\_strength (MFA / step-up)
* incentive\_chain\_for\_deal (approver independence)

### Resource

* data\_domain (D1–D8)
* sensitivity\_tier · regulatory\_category
* **mnpi\_tag** (write-time; drives the wall for D2/D3)
* vertical / region / account (+ residency)
* owner (record / deal owner)
* granularity (raw-row / aggregate / field)
* derived\_from (lineage → inherits MAX input tier)
* min\_cell\_count / bucket\_membership\_hash
* active\_deal\_flag · residency\_zone

### Environment

* access\_time
* **mnpi\_blackout\_window** (break-glass cannot override)
* device\_posture / network
* operation\_type (read / edit / **export** / **unmask-PII** — distinct step-ups)
* purpose\_of\_use (must resolve to a verifiable artifact)
* break\_glass\_flag (excludes MNPI)
* cell\_size\_satisfied (SDC service)
* **effective\_permission\_set** (computed across all roles+attrs)

## Role hierarchy

authenticated\_user (base — D1 identity + scrubbed D7 only; deny-by-default)
│
├─ Sales ───────── sales\_rep ──▶ sales\_manager (ABAC: own vertical/region/account; mnpi\_tag=false)
├─ Finance ─────── finance\_analyst ──▶ finance\_editor (SOX: preparer ≠ reviewer)
│ └─▶ finance\_approver
├─ Data Science ── ds\_analyst ──▶ ds\_lead (aggregate-only via SDC service)
└─ Leadership ──── c\_suite\_leadership (enumerated active deals; D6 summaries only)
GOVERNANCE — mutually separated, no business-data consumption (SoD):
compliance\_officer · owns MNPI wall + watch-list; co-approves wall-crossings
dpo\_data\_protection · owns DSAR / erasure (dual-control); PII downgrade co-approver
data\_steward · PROPOSES classification (downgrades need 2nd approver)
access\_admin · grant/revoke (requester ≠ approver across all admins)
access\_reviewer · read-only audit + effective-permission recert
platform\_admin · substrate only; D1–D8 content DENIED (keys/WORM outside admin)
NON-HUMAN:
etl\_service\_identity · least-privilege; reads D1 + non-MNPI D2 → writes D8 mart

Role definitions (expand)

### sales\_rep → sales\_manager

Rep reads D1, non-MNPI D2, non-active-deal D3, masked D4, and stage/owner of D5 **for own assigned accounts only** — no financials, no MNPI, no peers' pipelines. Manager adds a real capability: SoD-preserving deal-stage second-approval (approver ≠ owner, not in incentive chain). Seniority widens the row predicate, not the domain set.

### finance\_analyst / editor / approver

Analyst: read-only operational financials (D6) cross-territory + context. Editor: edits D6 rows but **cannot approve the rollup built from them**. Approver: certifies rollups after independent reconciliation, cannot edit the rows it certifies. Bulk export of raw D6 is a separate step-up.

### ds\_analyst → ds\_lead

Reads **only** the SDC-governed de-identified aggregate layer (D8); zero grants on raw D4/D6; no row-level export. DS-aggregate family is mutually exclusive with Sales/Finance consumers to defeat aggregate-differencing. Lead may propose new views; dashboards publish only if no input carries an mnpi\_tag.

### c\_suite\_leadership

Reads D4 (masked; unmask = step-up) and MNPI-tagged D5/D2 on a **named, enumerated-deal need-to-know** (not row\_scope=full), plus financial **summaries** (not raw D6). Purpose-bound, blackout-gated, heightened audit. Explicitly not a super-role.

### compliance\_officer & dpo

Compliance owns the MNPI wall, watch-list (hard predicate), and co-approves every wall-crossing (the securities leg, distinct from IT). DPO owns DSAR/erasure under dual control, residency/lawful-basis, and token crypto-shred so erasure propagates downstream.

### platform\_admin & etl\_service\_identity

Platform-admin SoD deny is **technically enforced** (keys in HSM outside admin control, audit on external WORM, masked diagnostic view; RLS-bypass paths alarmed). ETL identity is enumerated, least-privilege, rotated, fully audited, reads non-MNPI fields only.

## Role × data-domain access matrix

row\_scope:
none
aggregate
own-scope
full
metadata

| Role | Data domain | Row scope | Field access |
| --- | --- | --- | --- |
| authenticated\_user | D1 company records | full | identity/vertical/region only |
| authenticated\_user | D7 pitches (scrubbed) | full | full |
| authenticated\_user | D2–D6, D8 | none | denied by default |
| sales\_rep | D1 company records | own-scope | full (no wildcard) |
| sales\_rep | D2 signals (non-MNPI) | own-scope | read non-MNPI fields; MNPI denied; fit-score edit denied (SoD) |
| sales\_rep | D3 dossiers (non-active) | own-scope | read; financial redaction; quarantine on MNPI uncertainty |
| sales\_rep | D4 contacts | own-scope | masked by default; unmask = step-up (deal artifact) |
| sales\_rep | D5 stage/owner (lower) | own-scope | full on stage/owner; peers' pipelines NOT visible |
| sales\_rep | D5 impact/growth + MNPI D2 | none | denied unless enumerated deal-team (wall) |
| sales\_rep | D6 financials | none | denied |
| sales\_manager | D1/D2/D3/D4-masked/D5-lower/D7 | team region | as rep; may second-approve deal stage when independent of deal |
| finance\_analyst | D6 financials | full | read (cross-territory) |
| finance\_analyst | D1 / D2 (non-MNPI) | full | read; MNPI-tagged D2 DENIED (closes sibling leak) |
| finance\_analyst | D4 / D5-MNPI | none | denied unless deal-team-added |
| finance\_editor | D6 financials | full | edit; cannot approve rollup (SOX); export = step-up |
| finance\_approver | D6 rollups / summaries | full | approve/certify after independent reconciliation; cannot edit certified rows |
| finance (bulk export) | D6 export | step-up | distinct op: throttled, justified, DLP, threshold approval, pre-alert |
| ds\_analyst | D8 aggregate mart | aggregate | safe columns; SDC: k≥5 + dominance + suppression + effective-k |
| ds\_analyst | D4/D6 raw · D5/MNPI | none | denied; MNPI signals excluded from mart entirely |
| ds\_lead | D8 + view definition | aggregate | publish only if no mnpi\_tag input; new views via SDC cert + steward |
| c\_suite\_leadership | D4 contacts | enumerated deals | masked; per-record unmask = step-up; residency enforced |
| c\_suite\_leadership | D5 impact/growth + MNPI D2 | enumerated deal-team | read within wall; blackout-gated; watch-list-clear |
| c\_suite\_leadership | D6 financials | aggregate | summaries only; raw operational denied |
| c\_suite\_leadership | D8 aggregates | full | full on published dashboards |
| compliance\_officer | MNPI wall + watch-list | metadata | co-approve wall-crossings; curate watch-list; MNPI downgrade 2nd-approver |
| dpo\_data\_protection | D4 PII governance | DSAR-scoped | execute erasure (dual-control); PII downgrade 2nd-approver; token lineage |
| platform\_admin | D1–D8 content | none | DENIED (keys/WORM outside admin); masked diagnostic view |
| data\_steward | classification metadata | metadata | propose tags; downgrades/de-id/retag need 2nd approver |
| access\_admin | entitlements | grants | grant/revoke; requester ≠ approver; deal-team adds need compliance co-approval |
| access\_reviewer\_auditor | audit + entitlements | full (logs) | read-only; NONE on D1–D8 business data |
| etl\_service\_identity | D1 + non-MNPI D2 → D8 | source read (logged) | read non-MNPI; write mart under SDC; no interactive login |

## Principles

1. **Deny-by-default / fail-closed** — any unmatched request, new domain/column, or null scope → no access; new users sit in an alarmed provisioning-pending state.
2. **Least privilege + need-to-know** — even C-suite D4/D5 is predicate-scoped to enumerated active deals, never a de-facto super-role.
3. **Two-axis WHAT vs WHICH ROWS** — RBAC sets the ceiling; ABAC narrows rows. Scope & seniority live in attributes, never role names.
4. **Effective-permission evaluation + mutually-exclusive role families** — authz & recert computed across a subject's full role+attribute set; toxic role-pairs blocked pre-grant and at recert.
5. **MNPI is a property of the signal, not a domain** — deal-intent D2/D3 tagged MNPI at write-time; excluded from the DS mart entirely (signal lives in the score value, not a flag).
6. **Dual-control on classification** — every downgrade / de-id cert / threshold change / retag needs an independent second approver from the relevant control function.
7. **SoD across deal AND financial lifecycle** — block toxic combos (edit-fit-score+advance-deal; edit-financials+approve-rollup; own/comped-on-deal+approve-that-deal); admin, classification, MNPI-wall, PII, platform-ops, and audit each separated.
8. **MNPI information barriers, first-class** — walled to named deal team; Compliance-co-approved time-boxed wall-crossing; watch-list & blackout as hard gates break-glass can't override.
9. **Minimum aggregation via a dedicated SDC layer** — k≥5, dominance/p-percent, complementary suppression, frozen buckets, effective-k inflation — enforced by a statistical-disclosure-control service, not row predicates.
10. **Two named enforcement layers** — (a) RLS/attribute-predicate engine for D1–D6 rows/fields; (b) separate SDC service for aggregate/query-set control; direct-datastore bypass alarmed.
11. **Export & PII-unmask are distinct step-ups** — own grant, throttle, justification, DLP, threshold approval; dashboards re-classified to max input tier before sharing.
12. **Attribute integrity is in the trust boundary** — territory/deal-team assignment is privileged, SoD-controlled, requester ≠ approver; wildcard scope forbidden for D3/D4/D5 ceilings; no self-widening.
13. **Purpose limitation bound to evidence** — purpose\_of\_use must resolve to a verifiable artifact at decision time; self-asserted purpose is never the control.
14. **GDPR by construction** — masked-by-default PII, hard residency predicate, DPO-owned DSAR/erasure under dual control, per-subject crypto-shreddable tokens (Art. 17).
15. **Technically-enforced platform SoD** — keys outside platform\_admin, PIP administration separated, audit on external WORM.
16. **Governed non-human principals** — the ETL/mart identity is enumerated, least-privilege, rotated, audited, in-scope for recert.
17. **Operability preserves the controls** — small-cohort DS appeal path, pre-authorized deal-team templates with SLA, minimum-viable-staffing compensating controls, provisioning-latency metrics.

## Governance

### Provisioning

Group-based via corporate IdP → RBAC roles + ABAC attributes pushed to the authoritative PIP. One consumer family per human (enforced at grant). All grants request→approve→log via access\_admin, requester ≠ approver across all admins, independent business-owner approval for territory, Compliance co-approval for every deal-team/MNPI wall-crossing. Unresolved attributes → alarmed provisioning-pending (deny + SLA). Same-day joiner/mover/leaver.

### Access reviews

Quarterly recertification (MNPI/PII/financials first) on **effective** permissions across each subject's full role+attribute set; managers re-confirm scope + effective reachable company counts; toxic role-pair detection every identity; SOX recert on D6 editor/approver split; DPO GDPR retention/residency; Compliance re-attests deal rosters + watch-list. Exceptions are named, time-boxed, auto-expiring entitlements visible to a "who can see company X" simulator.

### Audit

Immutable, tamper-evident logging on external WORM the platform\_admin cannot alter — every domain, attributable, timestamped, recording purpose\_of\_use **and its backing artifact**. Heightened for MNPI/PII. Every classification change, wall-crossing, watch-list access, bulk export, PII unmask, cross-territory read, RLS-bypass attempt, and ETL source read logged and (where sensitive) real-time alerted. One stream serves SOX ITGC, GDPR Art. 30, insider-trading surveillance.

### Break-glass

Independently-approved-to-engage, alarmed, time-boxed, domain-bounded. **Excludes Restricted-MNPI** (or requires in-line Compliance approver) and **cannot override an active blackout window or wall-crossing**. Distinct env attribute logged to WORM with synchronous alerting; auto-expires; recertified next review. Frequency tracked as a boundary-health signal.

## Example policies (plain language)

* A **finance\_analyst** reading D2 gets only `mnpi_tag=false` fields; any deal-intent fit-score is denied and walled — the sibling-domain path that let un-cleared Finance infer deal intent is closed.
* A **data\_steward** downgrading a D6 row or certifying de-identification has no effect until an independent second approver (finance\_approver / compliance\_officer / DPO) signs off; the change and approval hit the immutable stream and a downgrade alert fires.
* No single human can hold **finance + leadership** or **finance + sales-leader**: role families are mutually exclusive and the PDP evaluates effective permissions, so raw-D6 + named-D4-PII + MNPI can never accumulate via role stacking.
* A user who is both **DS-aggregate and Sales** is refused — structurally preventing the differencing attack (subtract 5 own-territory raw scores from a k=6 aggregate to isolate the 6th).
* A **sales\_rep** declaring `purpose=deal-execution` to unmask D4 PII is denied unless that purpose resolves to an enumerated open deal they're on; unmask is then a per-record, independently-approved, logged step-up.
* **access\_admin** cannot set `assigned_verticals='*'` on a sales-leader: wildcard/parent scope is forbidden for any role whose ceiling includes D3/D4/D5.
* Adding anyone to a deal team requires **compliance\_officer co-approval** plus access\_admin execution, requester ≠ approver, blackout- & watch-list-checked, time-boxed, alerted — IT alone can never grant MNPI access.
* **break-glass** cannot reach Restricted-MNPI or override an active blackout window; an emergency MNPI need requires an in-line Compliance approver.
* **platform\_admin** operating the datastore still cannot read D1–D8: sensitive domains encrypted with keys outside admin control, audit on WORM; routine debugging uses a masked diagnostic view; any RLS-bypass read alarms.

## Adversarial red-team — audit trail

Three independent lenses attacked the synthesized model; every Critical/High was fixed in the final. Severity: Critical · High · Medium · Low

### Critical findings (all fixed)

* Critical — **D2 fit-scores were an unwalled MNPI side-channel.** Finance/Sales could infer non-public deal intent from scores outside the wall, un-audited. → *Fixed: write-time `mnpi_tag`, D2/D3 inherit the MNPI overlay, deal-intent signal excluded from the DS mart.*
* Critical — **data\_steward was an unchecked single-party root of trust** for every ABAC decision (could silently downgrade MNPI/financial tiers). → *Fixed: maker-checker on all downgrades/de-id/retag; propose ≠ approve; real-time downgrade alerts.*
* Critical — **No person-level role mutual-exclusion** — toxic role aggregation defeated SoD (finance\_lead + c\_suite = near-total reach). → *Fixed: mutually-exclusive role families; authz/recert on effective permissions; toxic-pair detection.*

All findings by lens (expand — 3 Critical, 12 High, 8 Medium, 1 Low across the three lenses)

### Lens 1 — Data-leakage & privilege escalation

* D2 MNPI side-channel (C) · data\_steward single-party trust (C) · no role mutual-exclusion (C)
* ds\_analyst+sales\_rep aggregate differencing (H) · self-declared purpose\_of\_use non-enforcing (H) · wildcard scope → enterprise PII reader (H) · access\_admin silent scope escalation of confederates (H) · finance\_lead bulk raw-D6 export uncontrolled (H) · ungoverned ETL super-principal (H)
* Confidential financials in D3 free-text leak to sales-leader (M) · break-glass unbounded vs MNPI/blackout (M) · c\_suite D4 full enterprise PII on self-asserted need (M)

### Lens 2 — Separation-of-duties & regulatory (MNPI/SOX/GDPR)

* MNPI via D2 outside the barrier (C) · deal-team wall-crossing granted by IT with no compliance leg (C) · data\_steward declassification without dual-control (C)
* No SOX maker-checker on financials (H) · platform\_admin SoD only application-layer (H) · purpose\_of\_use unverified (H) · GDPR minimization inverted for leadership (H) · no DSAR/erasure owner + stable tokens block erasure (H) · unspecified ETL identity = SOX ITGC gap (H) · D3 dossiers MNPI-capable but only scanned (H)
* break-glass no MNPI/blackout wall (M) · weak deal-stage approval independence (M) · dashboards surface MNPI-in-signal to Internal (M)

### Lens 3 — Operational feasibility

* Single RLS layer can't deliver aggregate/k-anonymity guarantees (H) · aggregate-only DS suppresses the small-cohort insights that are the mission (H) · steward can't classify what it can't read (H)
* Seniority-as-roles = role explosion vs own principle (M) · prose per-user exceptions erode RBAC (M) · self-declared purpose neither enforceable nor free (M) · fail-closed null-attribute = onboarding friction (M) · deal-team churn vs approval latency on critical path (M) · platform\_admin zero-data forces break-glass for ops (M) · manager second-approval SoD gap (M)
* Four separated governance identities presume headcount (L)

### Residual risks (accepted / monitored)

* Write-time MNPI tagging is only as good as the classifier — a mis-tagged deal-intent signal escapes the wall (detection gap; mitigate with red-team sampling + tag-on-uncertainty).
* Aggregate re-identification is bounded, not eliminated — the small-cohort appeal path deliberately reopens some surface as a per-query-audited accepted risk.
* purpose-bound-to-artifact raises the bar but doesn't prove intent — relies on sampled after-the-fact audit.
* Governance depends on genuinely independent, staffed control functions; thin-headcount compensating controls reduce but don't fully replace four-eyes.
* Collusion across distinct control functions remains possible — controls force a conspiracy; residual detection is immutable audit + approval-pattern surveillance.
* Crypto-shred erasure assumes complete token lineage — off-platform copies remain an Art. 17 residual.
* Technically-enforced platform SoD shifts trust to key/audit custodians and their own SoD.
* Field-level dual-classification of D2/D3 increases complexity — mislabeling is now a more likely failure mode (maker-checker + audit reduce, not remove).

Generated from a 9-agent workflow (4 research → synthesis → 3-lens red-team → finalize). Conceptual model — map to a concrete enforcement substrate (BigQuery RLS + policy tags, cloud IAM + IdP groups, or an OPA/Cedar policy engine) as a follow-on.
