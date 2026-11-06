# Habari business case

## The problem, in the guide's own numbers
- 88.5% of children in UCC's Kampala survey of 5,700+ students had met online harm, and 70.1% had received unsolicited sexual content.
- **74.2% never told anyone.**
- Only **3% to 11%** of serious online incidents ever reach the authorities or social workers (Disrupting Harm in Uganda, UNICEF, ECPAT and INTERPOL).
- The main reasons: fear of stigma, fear of losing their phone, and no trusted, child-friendly way to report.

Habari closes the gap between a child who wants to tell someone and the services that can help.

## Who uses it, and who pays

Children **never** pay and never need data, an app or a smartphone (SMS and USSD work on any phone).

| Group | What they get | Role |
|---|---|---|
| **Children 10–17** | Report from any phone, any language, without a name; get help and follow their case | Users (free) |
| **Sauti 116 child helpline** (Ministry of Gender, Labour and Social Development) | Reports arrive already prioritised, with a summary and evidence; no case is lost | Main operator |
| **Police Child and Family Protection Unit** | Severity 4 referrals with evidence, tracked acknowledgement | Partner |
| **UCC** | National picture of online harms (heat map, trends), platform and scam reports | Funder and regulator |
| **Schools, NGOs, child-protection organisations** | A ready reporting channel and referral pathway for their children | Customers |

## Business model

A **public-good platform with paid deployments**:

1. **Government and regulator funding (main route).** A national deployment funded by UCC (for example through the Uganda Communications Universal Service and Access Fund) or the Ministry, run with Sauti 116.
2. **Licences for organisations.** NGOs, school networks and private helplines pay a yearly fee per deployment (their own officers, partners and reports), on the same shared platform.
3. **Donor grants for pilots and research.** Child online safety funders such as Safe Online and UNICEF fund pilots, language work and independent evaluation.
4. **Telecom partnerships.** Mobile operators give a free (zero-rated) SMS shortcode and USSD code as part of their child online protection commitments, so children are never charged.

## Costs (estimates for a two-district pilot; to be confirmed)

| Item | Estimate | Notes |
|---|---|---|
| Hosting (app server with AI, database) | Low hundreds of USD per month | Hosted in Uganda to meet the Data Protection and Privacy Act |
| SMS and USSD | Depends on volume and operator rates | Goal: zero-rated by operators. Until then, a per-message cost |
| Speech and language AI (Sunbird) | Per-request pricing or partnership | Ugandan provider of Luganda and Runyankore models |
| Staff | Officers are provided by partners (Sauti 116, NGOs) | Habari makes their existing staff faster; it does not replace them |
| Development and support | Our team | Maintenance, language updates, partner onboarding |
| Safeguarding and data protection | Specialist review, audits | Required before handling real reports |

**The biggest cost is people, not servers.** Habari's value is that each officer handles more cases safely: automatic triage, summaries, duplicate and repeat-offender detection, and no case slipping through.

## Route to adoption

| Stage | What happens | Measure of success |
|---|---|---|
| **1. Now** | Hackathon prototype; recommendation to UCC incubation | Working demo, honest evaluation |
| **2. Validation (about 3 months)** | Native-speaker review of languages; child-protection review of the referral rule; outside test set; Sunbird integration | Blind triage accuracy at or above 90% |
| **3. Pilot (about 6 months)** | Two districts with Sauti 116, Police CFPU and partner schools; Africa's Talking shortcode | Reports received, time to acknowledgement, referrals completed, children's safety check-ins |
| **4. National** | UCC and Ministry deployment, operator zero-rating | Share of reports reaching a service (today 3%–11%) |
| **5. Region** | Other East African countries with 116 child helplines | Deployments licensed |

## Why Habari can win adoption
- **It fits existing services** (Sauti 116, Police CFPU, UCC) instead of building a new one.
- **Any phone, local languages, no name**: it removes the barriers that keep 74.2% of children silent.
- **Every case is tracked to a response.** Deadlines, escalation and the child's own case code mean reports aren't lost.
- **Safety and the law are built in**: data minimisation, no data on the device, district-level location only, and a design for the Data Protection and Privacy Act and the ITU Child Online Protection Guidelines.

## Risks and how we handle them

| Risk | Response |
|---|---|
| Too many reports for staff | Prioritisation, duplicate detection, partner escalation; scale officers with demand |
| AI misses or false alarms | Rules only raise severity; humans review; published false positive and false negative rates |
| Children's data | Pseudonymous IDs, a raw-contact vault, hashing, local hosting, retention limits |
| Partner capacity | Agreed response deadlines per partner; automatic second-partner escalation |
