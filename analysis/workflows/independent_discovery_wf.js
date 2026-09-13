export const meta = {
  name: 'independent-discovery-250',
  description: 'Independent second-pass discovery of Banyan-aligned software companies via codex, by acquirer-adjacency and bootstrapped/regional angles, for cross-match against pass 1',
  phases: [
    { title: 'Discovery', detail: 'codex deep web research per angle (foreground, sandbox off) -> structured candidate lists' },
  ],
}

const WS = '/Users/pahmed/.claude/plugins/cache/paypal-ai-hub/ai-hub-web-search/1.3.2/paypal-ai-hub/skills/codex-websearch/scripts/websearch.sh'

// Deliberately DIFFERENT sourcing angles than pass-1 (which was vertical keyword batches),
// so overlap = independent validation, not a re-run.
const ANGLES = [
  {key:'constellation-adjacency', q:`software companies in the SAME narrow niches that Constellation Software's operating groups (Volaris, Harris, Jonas, Vela, Topicus, Perseus, Trapeze) have acquired - list both their recent tuck-in acquisitions AND similar STILL-INDEPENDENT niche vertical-software leaders that fit a buy-and-hold acquirer`},
  {key:'valsoft-everfield-banyan', q:`vertical B2B software companies similar to what Valsoft, Everfield, Main Capital Partners, and Banyan Software have acquired - and comparable STILL-INDEPENDENT founder/family-owned niche leaders in those same categories that have NOT yet been acquired`},
  {key:'education', q:`bootstrapped or founder/family-owned vertical software companies in K-12 student information systems, school administration/ERP, higher-ed SIS/LMS for small colleges, school communications, and edtech operations - profitable private niche leaders, US and international, NOT VC-backed unicorns`},
  {key:'manufacturing-industrial', q:`profitable founder-owned software companies for SMB manufacturers: ERP, MRP, MES, QMS, CMMS, shop-floor/production management, EQMS - private niche leaders (US, Canada, UK, Europe), exclude VC-backed and public companies`},
  {key:'construction-fieldservice', q:`bootstrapped founder-owned software for construction and field service: trades job management/FSM, estimating/takeoff, construction accounting/ERP, project management, service contractors - niche leaders in US, Australia, New Zealand, UK, Canada, exclude VC-backed unicorns`},
  {key:'healthcare-practice-mgmt', q:`profitable founder-owned practice-management and clinical-admin software: allied-health, behavioral health/EHR, dental, veterinary, physiotherapy, medspa/aesthetics, chiropractic - private vertical niche leaders (US, Canada, ANZ, UK), exclude VC-backed AI scribe/agent companies`},
  {key:'realestate-hospitality', q:`bootstrapped vertical software for real estate and hospitality: property management, HOA/community management, short-term-rental PMS, hotel PMS, salon/spa, restaurant back-office/scheduling, catering/events - founder-owned profitable niche leaders, exclude VC-backed`},
  {key:'fintech-backoffice', q:`profitable founder-owned software in financial-services back office: credit-union core banking, loan servicing/origination, wealth/RIA/advisor platforms, insurance agency management, community-bank lending - private niche leaders, exclude VC-backed fintech infrastructure unicorns`},
  {key:'legal-compliance-gov', q:`established profitable NON-AI vertical software: legal practice management, contract lifecycle management (CLM), GRC/compliance, EQMS quality management, e-discovery, government/public-sector permitting/licensing/ERP - founder-owned or bootstrapped private niche leaders, exclude VC-backed legal-AI startups`},
  {key:'regional-bootstrapped', q:`bootstrapped, profitable, founder-owned vertical B2B software companies (NOT VC-backed) headquartered in Australia, New Zealand, UK, Canada, the Nordics, the Baltics, or Germany/DACH - niche leaders across any industry vertical, roughly $2M-$100M revenue, that would suit a buy-and-hold permanent acquirer`},
]

const CAND_SCHEMA = { type:'object', properties:{
  companies:{ type:'array', items:{ type:'object', properties:{
    name:{type:'string'}, domain:{type:'string'}, vertical:{type:'string'}, region:{type:'string'},
    ownership:{type:'string'}, size_signal:{type:'string'}, banyan_fit_note:{type:'string'}
  }, required:['name','vertical'] } }
}, required:['companies'] }

const CRITERIA = `BANYAN FIT (include only companies that plausibly match): vertical/enterprise B2B software niche leader; founder/family-owned OR bootstrapped OR PE-light (NOT venture-scale, NOT a >$100M or unprofitable growth company, NOT already public); high-recurring-revenue; roughly $2M-$100M revenue. EXCLUDE: VC-backed unicorns, hyperscale AI-native startups, and any company already acquired by Banyan itself. Prefer the "boring", profitable, under-the-radar niche leaders.`

const results = await parallel(ANGLES.map(a => () => agent(
`You are a sourcing analyst for Banyan Software (buy-and-hold-forever vertical-software acquirer). Discover qualifying companies for the angle "${a.key}".

STEP 1 - RESEARCH. Run Codex deep web research in the FOREGROUND (do NOT run_in_background); it needs the sandbox OFF, so call the Bash tool with dangerouslyDisableSandbox: true. Wait for it to finish. Run this, and optionally one refining follow-up search if the first is thin:

bash ${WS} --mode deep --format md "${a.q}. For each company give: name, website domain, the specific vertical/niche, HQ country/region, ownership (bootstrapped / founder-family / PE / VC / public), and any size signal (employees, revenue/ARR estimate). Aim for 30+ companies. Cite sources."

STEP 2 - COMPILE. From the research, return as many QUALIFYING companies as it surfaced (target 25-40). ${CRITERIA}
For each: name, domain (if known), vertical (specific niche), region, ownership, size_signal, and a one-line banyan_fit_note. Base every entry on the research; do not invent companies. If a company is clearly VC-backed/oversized, drop it rather than list it.`,
  { label:`discover:${a.key}`, phase:'Discovery', schema: CAND_SCHEMA, agentType:'general-purpose' })
))

const angles = ANGLES.map((a,i) => ({ angle:a.key, companies:(results[i]&&results[i].companies)||[] }))
const total = angles.reduce((n,x)=>n+x.companies.length,0)
log(`Discovery complete: ${total} raw candidates across ${angles.length} angles`)
return { angles, total }
