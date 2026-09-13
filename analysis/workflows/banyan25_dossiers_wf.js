export const meta = {
  name: 'banyan25-dossiers-pitches',
  description: 'Deep-research the top-25 BANYAN-RUBRIC acquisition targets via codex and draft permanent-home outreach pitches',
  phases: [
    { title: 'Research', detail: 'codex deep web research per lead (foreground, sandbox off)' },
    { title: 'Dossier & Pitch', detail: 'synthesize dossier + thesis-branched outreach email' },
  ],
}

// Top-25 by the BANYAN buy-and-hold rubric (from out/results.json, rejected/insufficient dropped).
const LEADS = [
 {"name":"HawkSoft","domain":"hawksoft.com","vertical":"Insurance agency management","region":"US","best":"banyan","banyan_adj":0.631,"growth_adj":0.44},
 {"name":"Rentec Direct","domain":"rentecdirect.com","vertical":"Property management software","region":"US","best":"banyan","banyan_adj":0.613,"growth_adj":0.406},
 {"name":"Infinite Campus","domain":"infinitecampus.com","vertical":"K-12 student information system / district administration","region":"US","best":"banyan","banyan_adj":0.607,"growth_adj":0.457},
 {"name":"Jane App","domain":"jane.app","vertical":"Health/wellness practice management","region":"Canada","best":"banyan","banyan_adj":0.6,"growth_adj":0.555},
 {"name":"Skyward","domain":"skyward.com","vertical":"K-12 SIS / school ERP","region":"US","best":"banyan","banyan_adj":0.6,"growth_adj":0.441},
 {"name":"ClassLink","domain":"classlink.com","vertical":"K-12 identity / single sign-on / rostering","region":"US","best":"banyan","banyan_adj":0.597,"growth_adj":0.468},
 {"name":"Schedulefly","domain":"schedulefly.com","vertical":"Restaurant scheduling","region":"US","best":"banyan","banyan_adj":0.595,"growth_adj":0.354},
 {"name":"Edupoint","domain":"edupoint.com","vertical":"K-12 SIS / LMS / administration (Synergy)","region":"US","best":"banyan","banyan_adj":0.593,"growth_adj":0.449},
 {"name":"Corelation","domain":"corelationinc.com","vertical":"Credit-union core banking","region":"US","best":"banyan","banyan_adj":0.589,"growth_adj":0.465},
 {"name":"OwnerRez","domain":"ownerrez.com","vertical":"Short-term rental PMS","region":"US","best":"banyan","banyan_adj":0.586,"growth_adj":0.386},
 {"name":"QT9 Software","domain":"qt9software.com","vertical":"QMS + ERP for regulated manufacturers","region":"US","best":"banyan","banyan_adj":0.581,"growth_adj":0.433},
 {"name":"Rent Manager / LCS","domain":"rentmanager.com","vertical":"Property management software","region":"US","best":"banyan","banyan_adj":0.581,"growth_adj":0.431},
 {"name":"Aeries Software","domain":"aeries.com","vertical":"K-12 student information system","region":"US","best":"banyan","banyan_adj":0.572,"growth_adj":0.423},
 {"name":"Advyzon","domain":"advyzon.com","vertical":"Wealth/advisor all-in-one platform","region":"US","best":"banyan","banyan_adj":0.572,"growth_adj":0.438},
 {"name":"Rediker Software","domain":"rediker.com","vertical":"School administration / SIS","region":"US","best":"banyan","banyan_adj":0.569,"growth_adj":0.397},
 {"name":"Cetec ERP","domain":"cetecerp.com","vertical":"Manufacturing ERP/MRP/QMS","region":"US","best":"banyan","banyan_adj":0.566,"growth_adj":0.427},
 {"name":"Vagaro","domain":"vagaro.com","vertical":"Beauty/wellness SaaS","region":"US","best":"banyan","banyan_adj":0.56,"growth_adj":0.531},
 {"name":"Cliniko","domain":"cliniko.com","vertical":"Allied-health practice management","region":"Australia","best":"banyan","banyan_adj":0.558,"growth_adj":0.375},
 {"name":"Global Shop Solutions","domain":"globalshopsolutions.com","vertical":"Manufacturing ERP","region":"US","best":"banyan","banyan_adj":0.558,"growth_adj":0.409},
 {"name":"PayHOA","domain":"payhoa.com","vertical":"HOA/community management software","region":"US","best":"banyan","banyan_adj":0.556,"growth_adj":0.53},
 {"name":"Populi","domain":"populi.co","vertical":"Higher-ed SIS / LMS (small colleges)","region":"US","best":"banyan","banyan_adj":0.554,"growth_adj":0.394},
 {"name":"TherapyNotes","domain":"therapynotes.com","vertical":"Behavioral-health EHR","region":"United States","best":"banyan","banyan_adj":0.554,"growth_adj":0.505},
 {"name":"Gradelink","domain":"gradelink.com","vertical":"K-12 SIS / school administration","region":"US","best":"banyan","banyan_adj":0.551,"growth_adj":0.4},
 {"name":"Phorest","domain":"phorest.com","vertical":"Salon/spa management","region":"Ireland","best":"banyan","banyan_adj":0.55,"growth_adj":0.531},
 {"name":"Hebbia","domain":"hebbia.com","vertical":"Finance / legal document AI","region":"US","best":"growth","banyan_adj":0.549,"growth_adj":0.582}
]

const WS = '/Users/pahmed/.claude/plugins/cache/paypal-ai-hub/ai-hub-web-search/1.3.2/paypal-ai-hub/skills/codex-websearch/scripts/websearch.sh'

const OUT_SCHEMA = { type:'object', properties:{
  company:{type:'string'},
  thesis:{type:'string'},
  fit_assessment:{type:'string'},
  dossier:{type:'object', properties:{
    business_model:{type:'string'}, niche_position:{type:'string'},
    revenue_profitability:{type:'string'}, ownership_funding:{type:'string'},
    competitors:{type:'string'}, moat:{type:'string'}, risks:{type:'string'},
    personalization_hook:{type:'string'}, sources:{type:'array',items:{type:'string'}}
  }, required:['business_model','niche_position','ownership_funding','personalization_hook'] },
  pitch:{type:'object', properties:{
    subject:{type:'string'}, body:{type:'string'},
    personalization_note:{type:'string'}, send_recommendation:{type:'string'}
  }, required:['subject','body','send_recommendation'] }
}, required:['company','thesis','fit_assessment','dossier','pitch'] }

const results = await pipeline(LEADS,
  (lead) => agent(
`Run Codex deep web research and return its findings VERBATIM (keep the cited sources).
CRITICAL: run the command in the FOREGROUND (do NOT use run_in_background); it needs the sandbox OFF, so call the Bash tool with dangerouslyDisableSandbox: true. Wait for it to finish, then return its stdout.

bash ${WS} --mode deep --format md "Deep profile of ${lead.name} (${lead.domain}) for an M&A acquisition assessment: business model & product; the vertical niche and market position; estimated revenue/ARR and profitability signals; employee count and growth trend; ownership (founder/family/bootstrapped/VC/PE) and full funding history with investors; key competitors; moat/defensibility; notable risks; recent news (last 12-18 months); founder/leadership names; and any PUBLIC detail useful as a personalization hook for founder outreach. Cite sources."

If the output is empty, run this fallback (also foreground, sandbox OFF):
printf 'Deep M&A profile of ${lead.name} (${lead.domain}): business model, niche & market position, revenue/ARR & profitability, employees & growth, ownership & funding history, competitors, moat, risks, recent news, founders, and a public personalization hook. Cite sources.\\n' | codex --search -a never -m gpt-5.6-sol exec --ephemeral --sandbox read-only --skip-git-repo-check -o "$TMPDIR/o.txt" - ; cat "$TMPDIR/o.txt"

Return the findings text (with sources). If both attempts yield nothing, return exactly: RESEARCH_FAILED`,
    { label:`research:${lead.name}`, phase:'Research', agentType:'general-purpose' }),

  (research, lead) => agent(
`You are an M&A analyst + outreach writer for Banyan Software. Build a dossier and a THESIS-APPROPRIATE outreach pitch for the lead, grounded ONLY in the research provided.

BANYAN THESIS: a buy-and-hold-FOREVER acquirer of PROFITABLE, founder/family-owned, high-recurring-revenue vertical B2B software niche leaders (~$2M-$100M revenue). A VC/PE-backed, unprofitable, or >$100M company is NOT a buy-and-hold target.

PITCH RULES (high hit-rate, follow all):
- Thesis-branch: if the lead is banyan-fit -> a Permanent-Home acquisition pitch (differentiator = permanence vs PE flip; preserve brand/team/legacy; proof point "120+ acquired, held permanently, zero sold"). If growth-thesis (VC-backed/unprofitable/too big) -> set send_recommendation to "route-to-growth-mandate" or "do-not-contact" and write at most a light relationship note; NEVER a permanent-home acquisition pitch to a VC-backed/oversized company.
- Body 50-125 words, ONE low-commitment CTA (a 20-minute call), specific first-line personalization from a PUBLIC detail in the research, lead with THEM not Banyan, no revenue/financial figures quoted to the recipient, no implication of non-public info (MNPI hygiene), no false urgency. Subject 3-5 words.

LEAD: ${lead.name} (${lead.domain}) — ${lead.vertical}, ${lead.region}. Screen best-thesis: ${lead.best} (banyan_adj ${lead.banyan_adj}, growth_adj ${lead.growth_adj}). If research is RESEARCH_FAILED, still classify by the screen data and set send_recommendation to "needs-manual-research".

RESEARCH:
${research}`,
    { label:`pitch:${lead.name}`, phase:'Dossier & Pitch', schema: OUT_SCHEMA, effort:'high' })
)

return results.filter(Boolean)
