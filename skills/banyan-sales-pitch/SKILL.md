---
name: banyan-sales-pitch
description: Generate high-hit-rate M&A / sales outreach emails to software-company leads for the Banyan screening platform. Use when drafting a first-touch or follow-up email to a screened lead, when someone asks for "a pitch", "outreach email", "cold email", or "contact this lead". Branches the angle by thesis (Banyan permanent-home acquisition vs growth-stage) and is IAM-gated to Sales/BD roles. Triggers include a lead name/domain plus intent to contact.
---

# Banyan Sales / M&A Outreach Pitch

Generate a tailored, high-conversion outreach email for a screened software-company lead. Every pitch is grounded in the lead's dossier and the correct **thesis angle**, follows evidence-based cold-email rules, and respects Banyan's brand posture.

## STEP 0 — Access gate (mandatory)

This skill emits lead identity + outreach content, which is **Sales/BD** data. Before producing anything, confirm the requester's role is a Sales/BD role (`sales_rep`, `sales_manager`, or BD). If invoked in a pipeline, the output MUST pass through `banyan_screen.policy.guard(role, ...)`. **Never** emit a lead pitch to `ds_*`, `finance_*`, or governance roles — Data Science and Finance do not receive lead PII/pitch content. If role is unknown, refuse.

## STEP 1 — Pick the thesis angle

Read the lead's `best_thesis` / fit assessment:

- **banyan-fit** (profitable, founder/family-owned, high recurring revenue, vertical niche leader, roughly $2M–$100M revenue): use the **Permanent-Home Acquisition** angle. This is Banyan's real motion.
- **growth-thesis** (VC/PE-backed, scaling, often >$100M or unprofitable): a buy-and-hold acquisition pitch is inappropriate and will damage credibility. Either (a) mark `NOT A BUY-AND-HOLD TARGET — route to growth mandate` and produce a partnership/relationship-building note instead, or (b) if no growth mandate exists, do not draft an acquisition email at all. Never send a "permanent home" acquisition pitch to a VC-backed unicorn.

## STEP 2 — Apply the high-hit-rate rules

Evidence-based cold-outreach principles (these drive reply rates; follow all):

1. **One idea, one CTA.** The only ask in a first touch is a short exploratory conversation — never "sell", never multiple asks.
2. **Short.** 50–125 words for the body. Every extra sentence lowers reply rate.
3. **Specific personalization in the first line** — a real, verifiable detail about *their* business (a product, a milestone, a niche they lead), not "I came across your company." Generic = ignored.
4. **Lead with them, not us.** The first two sentences are about the founder/company; Banyan is introduced only as the answer to a problem they have (succession, permanence).
5. **Credibility, not hype** — one concrete proof point (e.g. "120+ software companies, held permanently, zero sold"), no superlatives.
6. **Respect the legacy.** For founder-owned targets, the emotional core is *preserving what they built* (brand, team, mission), not a payday. Banyan's differentiator is *permanence* vs. PE flip.
7. **Frictionless CTA.** "Open to a 20-minute call in the next couple of weeks?" — low-commitment, time-boxed, easy yes.
8. **No pressure / no false urgency.** M&A outreach is relationship-first; manufactured urgency backfires with founders.
9. **Subject line:** 3–5 words, specific, curiosity or relevance — not "Partnership Opportunity". Prefer the company's niche or a genuine observation.
10. **Plain text, real signature, single sender.** No images, no tracking-pixel feel.

## STEP 3 — Ground every claim in the dossier

Pull the personalization detail, the fit rationale, and any risk to avoid mentioning from the lead's dossier. Do **not** state a revenue/financial figure to the recipient — those are internal estimates (and often Confidential). Never imply you have non-public information about them (MNPI hygiene).

## STEP 4 — Produce the output

For each lead, return:
- `subject` (3–5 words)
- `body` (50–125 words, plain text, one CTA)
- `personalization_note` (which specific detail you used and its source)
- `thesis` (banyan-fit | growth-thesis)
- `send_recommendation` (send | route-to-growth-mandate | do-not-contact) + one-line reason

See `templates.md` for the frameworks (Permanent-Home, PAS, Founder-Succession, Follow-up) and worked examples. See `banyan_playbook.md` for the thesis criteria, brand voice, and compliance do/don'ts.

## Activation

This skill lives in the project at `skills/banyan-sales-pitch/`. To make it invocable in Claude Code, copy it to `~/.claude/skills/` (or the project `.claude/skills/`):
`cp -r skills/banyan-sales-pitch ~/.claude/skills/`
