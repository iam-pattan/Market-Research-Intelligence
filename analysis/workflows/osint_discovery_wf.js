export const meta = {
  name: 'osint-discovery-verify',
  description: 'OSINT vector: discover Banyan-aligned software companies via registries/filed-accounts/GitHub/careers, and verify ownership + real financials for known top candidates',
  phases: [
    { title: 'OSINT', detail: 'codex directed at OSINT sources (foreground, sandbox off): discovery + ownership/financial verification' },
  ],
}

const WS = '/Users/pahmed/.claude/plugins/cache/paypal-ai-hub/ai-hub-web-search/1.3.2/paypal-ai-hub/skills/codex-websearch/scripts/websearch.sh'

// OSINT DISCOVERY angles — sourced by registry/source-type & region (differs from
// pass-1 vertical batches and pass-2 acquirer-adjacency). Registries with FILED ACCOUNTS
// are the point: they carry REAL private-company revenue/profit + shareholder/ownership.
const ANGLES = [
  {key:'uk-ireland-filed-accounts', q:`Using UK Companies House filed annual accounts and Irish CRO records as sources, identify PRIVATE founder/family-owned or bootstrapped vertical B2B SOFTWARE companies (SIC 62/58) with filed turnover roughly GBP 2M-80M that are profitable. For each give: company name, website domain, niche/vertical, latest FILED revenue and profit if disclosed, shareholders / ownership structure (founder / family / PE / VC), and employee count.`},
  {key:'eu-registries-filed', q:`Using EU company registries with public filings (Germany Bundesanzeiger/Unternehmensregister, Netherlands KVK, the Nordic registries, France Infogreffe/Pappers) as sources, identify PRIVATE founder-owned or bootstrapped vertical B2B SOFTWARE companies with filed revenue roughly EUR 2M-80M. For each: name, domain, niche, latest filed revenue/profit, ownership, employees, country.`},
  {key:'anz-canada-registries', q:`Using ASIC (Australia), the NZ Companies Office, and Canadian corporate registries plus public filings as sources, identify PRIVATE founder-owned vertical B2B SOFTWARE companies (roughly AUD/CAD 3M-100M revenue) that are profitable niche leaders. For each: name, domain, niche, ownership, any disclosed revenue/employees, country.`},
  {key:'us-registry-sec-osint', q:`Using US SEC EDGAR (Form D private placements, Reg A, S-1/10-K), state Secretary-of-State registries, and press releases as sources, identify PRIVATE US vertical B2B software companies that are founder-owned or bootstrapped niche leaders (NOT venture-scale). Flag any that filed Form D showing venture funding (to EXCLUDE). For each: name, domain, niche, ownership signal from filings, size signal.`},
  {key:'github-tech-footprint', q:`Using GitHub organizations, engineering blogs, and tech-stack footprints as OSINT sources, identify bootstrapped/founder-owned vertical B2B software companies (not VC-backed) that show a healthy, active engineering org (steady commits, sizeable team) in niche industry verticals. For each: name, domain, niche, ownership signal, team-size signal.`},
  {key:'careers-hiring-osint', q:`Using company careers pages and public job-posting counts as OSINT sources, identify vertical B2B software companies that are steadily HIRING (a growth signal) yet have NO announced VC funding rounds (bootstrapped signal), in niches like ERP/field-service/healthcare-admin/education/property. For each: name, domain, niche, open-roles/hiring signal, ownership signal.`},
  {key:'product-directory-leaders', q:`Using software review directories (Capterra, GetApp, TrustRadius, SoftwareAdvice) as OSINT sources, identify high-review-count category leaders in NARROW industry verticals that are PRIVATE and founder-owned/bootstrapped (not VC-backed, not public). For each: name, domain, niche/category, review-count/rating signal, ownership signal.`},
]

const CRITERIA = `INCLUDE only plausible Banyan fits: vertical B2B software niche leader; founder/family-owned OR bootstrapped OR PE-light; roughly $2M-$100M revenue; high recurring revenue; profitable/self-sustaining. EXCLUDE venture-scale, >$100M, unprofitable, public, or already-Banyan-owned companies.`

const CAND_SCHEMA = { type:'object', properties:{
  companies:{ type:'array', items:{ type:'object', properties:{
    name:{type:'string'}, domain:{type:'string'}, vertical:{type:'string'}, region:{type:'string'},
    ownership:{type:'string'}, ownership_evidence:{type:'string'},
    filed_financials:{type:'string'}, size_signal:{type:'string'},
    source_type:{type:'string'}, banyan_fit_note:{type:'string'}
  }, required:['name','vertical'] } }
}, required:['companies'] }

// Known strong candidates to VERIFY (ownership truth + filed financials). Includes some
// synthesis-flagged "looks-founder-owned-but-maybe-not" names to actively refute.
const VERIFY_NAMES = [
  'HawkSoft','Rentec Direct','Infinite Campus','Jane App (jane.app)','Skyward','ClassLink','Schedulefly',
  'Edupoint','Corelation','OwnerRez','QT9 Software','Rent Manager (rentmanager.com)','Aeries Software',
  'Advyzon','Rediker Software','Cetec ERP','Vagaro','Cliniko','Global Shop Solutions','PayHOA','Populi',
  'TherapyNotes','Gradelink','Phorest','Agiloft','Tripleseat','Katana','Limble CMMS','UpKeep','Boulevard',
  '7shifts','MarginEdge','DoorLoop','Hostaway','ClassLink'
]

const VERIFY_SCHEMA = { type:'object', properties:{
  verifications:{ type:'array', items:{ type:'object', properties:{
    company:{type:'string'}, apparent_owner_type:{type:'string'}, verified_owner_type:{type:'string'},
    is_founder_owned:{type:'boolean'}, latest_investor_or_acquirer:{type:'string'},
    filed_or_reported_financials:{type:'string'}, evidence:{type:'string'},
    flag:{type:'string'}
  }, required:['company','verified_owner_type','is_founder_owned'] } }
}, required:['verifications'] }

const discoveryThunks = ANGLES.map(a => () => agent(
`You are an OSINT sourcing analyst for Banyan Software. Angle: "${a.key}".

STEP 1 - RESEARCH via Codex, FOREGROUND (do NOT run_in_background), sandbox OFF (Bash with dangerouslyDisableSandbox: true). Wait for completion; optionally one refining follow-up search:

bash ${WS} --mode deep --format md "${a.q} Aim for 25+ companies. Cite sources."

STEP 2 - COMPILE. ${CRITERIA}
Return qualifying companies (target 20-35) with: name, domain, vertical, region, ownership, ownership_evidence (what OSINT source/fact supports the ownership call), filed_financials (real filed/disclosed numbers if the source gave them, else empty), size_signal, source_type (which OSINT source), banyan_fit_note. Base every entry on the research; never invent. Drop anything clearly VC-backed/oversized.`,
  { label:`osint:${a.key}`, phase:'OSINT', schema: CAND_SCHEMA, agentType:'general-purpose' }))

const verifyThunk = () => agent(
`You are an OSINT verification analyst for Banyan Software. For EACH company below, verify its TRUE ownership and pull any FILED or credibly-reported financials, using OSINT sources (company registries + filed accounts, Crunchbase/PitchBook free pages, press releases, M&A news, LinkedIn). The goal is to CONFIRM genuinely founder/family-owned targets and REFUTE ones that only look independent (e.g. quietly PE/VC-held).

Run Codex in the FOREGROUND, sandbox OFF (Bash dangerouslyDisableSandbox: true), one or more deep searches as needed:
bash ${WS} --mode deep --format md "Ownership, cap table, funding rounds, and any acquisition of these software companies, plus any filed or reported revenue/profit; cite sources: ${VERIFY_NAMES.join('; ')}"

Return one verification per company: company, apparent_owner_type, verified_owner_type, is_founder_owned (boolean), latest_investor_or_acquirer (if any), filed_or_reported_financials, evidence (source + fact), and flag (e.g. "clean founder-owned", "PE-held - exclude", "VC-backed - exclude", "uncertain"). Be skeptical; if a name is actually PE/VC-held, say so plainly.`,
  { label:'osint:verify-known', phase:'OSINT', schema: VERIFY_SCHEMA, agentType:'general-purpose' })

const all = await parallel([...discoveryThunks, verifyThunk])
const discovery = ANGLES.map((a,i) => ({ angle:a.key, companies:(all[i]&&all[i].companies)||[] }))
const verification = (all[ANGLES.length] && all[ANGLES.length].verifications) || []
const total = discovery.reduce((n,x)=>n+x.companies.length,0)
log(`OSINT complete: ${total} discovery candidates + ${verification.length} ownership verifications`)
return { discovery, verification, total }
