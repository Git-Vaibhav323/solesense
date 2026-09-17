# SOLESENSE — Funding Proposal & Scale-Up Plan
### From Research Prototype → Clinical-Grade Wearable
#### Updated to reflect: Gait Analysis v2 · Bilateral roadmap · India MedTech context

> *"Every 30 seconds a lower limb is amputated somewhere in the world as a consequence
> of diabetes. 85% of those amputations started with a foot ulcer that started with
> elevated, undetected plantar pressure. SoleSense detects that pressure before damage begins."*

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [The Problem — Market Context](#2-the-problem--market-context)
3. [What We Have Built Today](#3-what-we-have-built-today)
4. [Why Now — Technology Readiness](#4-why-now)
5. [Funding Ask — How Much and Why](#5-funding-ask)
6. [Phase-by-Phase Budget](#6-phase-by-phase-budget)
7. [Revenue Model & Unit Economics](#7-revenue-model--unit-economics)
8. [Go-to-Market Strategy](#8-go-to-market-strategy)
9. [Market Size](#9-market-size)
10. [Competitive Landscape](#10-competitive-landscape)
11. [Team & Hiring Plan](#11-team--hiring-plan)
12. [Milestones & Timeline](#12-milestones--timeline)
13. [Risk Register & Mitigation](#13-risk-register--mitigation)
14. [Scale-Up Architecture](#14-scale-up-architecture)
15. [Cross-Questions Funders Will Ask](#15-cross-questions-funders-will-ask)

---

## 1. Executive Summary

| Field | Detail |
|---|---|
| **Project** | SoleSense — Continuous Foot Loading & Gait Monitor |
| **Stage** | TRL 4 — Technology validated in lab |
| **Current build** | Research pipeline (150-subject validation) + ESP32-S3 hardware prototype |
| **Ask** | ₹35,00,000 (~$42,000 USD) — 18-month Phase 1–2 seed |
| **What it buys** | Hardware v2 · clinical pilot · mobile app · patent · regulatory groundwork |
| **Revenue model** | Hardware unit sale + SaaS subscription + B2B data licensing |
| **Target market** | Diabetic foot · sports medicine · rehabilitation — $18B combined TAM |
| **Exit** | Acquisition by medtech (DJO, Össur) or health insurance platform — or independent IPO |

**One-paragraph pitch:**

SoleSense is a $25-BOM smart insole that monitors foot loading, temperature, and gait
in real time, using an explainable risk engine to tell patients and clinicians exactly
*which* pressure pattern is elevated and *why* — before it causes a diabetic foot ulcer,
stress fracture, or fall. The algorithm is validated on 150 subjects. The hardware
prototype streams live data to a polished dashboard with an 8-section gait analysis.
We need ₹35 lakh to go from "works in the lab" to "works in the clinic."

---

## 2. The Problem — Market Context

### The numbers

| Statistic | Source |
|---|---|
| 537 million people with diabetes globally | IDF Diabetes Atlas 2021 |
| 101 million in India — world's highest | ICMR 2023 |
| 15–25% will develop a diabetic foot ulcer | IWGDF 2023 |
| 85% of amputations preceded by a foot ulcer | WHO |
| Diabetic foot care global market: $7.7B by 2030 | Grand View Research |
| Athletes with lower-limb stress injuries (India): ~3M/year | NIH Sports Medicine estimates |
| Elderly fall-related healthcare cost (India): growing rapidly with 14% elderly growth | Census projections |

### Why the market is unserved

**Clinical tools (Tekscan, Pedar, RSscan):** ₹20–80 lakh per system. Lab-only. One
session = snapshot. Not continuous, not wearable, not affordable for community clinics.

**Consumer wearables (Nurvv, Superfeet AI):** Designed for runners. No temperature.
No bilateral pressure asymmetry. No explainable clinical risk score. Not for diabetics.

**Research insoles (Moticon OpenGo):** ₹3–15 lakh. Short research sessions only.
No temperature. No real-time risk indicator.

**The gap:** An affordable, daily-wear, explainable clinical-intent insole that tells
patients and clinicians *exactly* what is wrong before injury occurs. That is SoleSense.

### India-specific opportunity

- 1 podiatrist per 300,000 diabetic patients in India — critical shortage
- PM-JAY covers amputation (₹4–8 lakh) but not prevention (₹12,000 device)
- Preventive economics: device pays for itself if it delays or prevents one complication
- BIRAC, DST, and ICMR have active MedTech funding programs for chronic disease prevention
- Digital health regulatory framework (CDSCO MDR 2017, DPDP Act 2023) now established

---

## 3. What We Have Built Today

### Current capabilities (TRL 4)

✅ **Analytics pipeline** validated on StepUP-P150 (150 subjects, 100 Hz):
- 134 biomechanical features per footstep
- 10-rule explainable risk engine (NORMAL / MONITOR / ALERT)
- 78 automated tests covering all modules

✅ **ESP32-S3 hardware prototype:**
- FSR1 (forefoot) + FSR2 (heel) pressure sensors
- TMP117 temperature at ±0.1 °C
- MPU6050 IMU (3-axis accel + 3-axis gyro)
- Wi-Fi streaming at 20 Hz via HTTP POST

✅ **3-page Streamlit + Plotly dashboard:**
- Quick Analysis (live sliders, instant risk)
- Dataset Explorer (8-section deep-dive)
- Live Hardware (8-section real-time: pressure map, gait analysis, temperature,
  persistence, hotspot, personal baseline, risk breakdown)

✅ **Gait Analysis section (v2):**
- Activity: STANDING / WALKING / RUNNING / ACTIVE / LOW ACTIVITY
- Step count estimate, cadence (spm), movement intensity (0–100)
- Gait variability CV (coefficient of variation of |A|)
- Current gait vs personal session baseline
- Trend: STABLE / CHANGING / DEVIATING
- GAIT ANALYSIS card with plain-language interpretation
- Acceleration (g) and angular velocity (°/s) charts with clean labels

✅ **Anatomically correct UI:**
- Left foot SVG (forefoot=top, heel=bottom)
- All units labelled: g, °/s, p-kPa (proxy), °C, steps/min

### What this funding closes

❌ Calibrated kPa (FSR bench calibration with known weights)
❌ 4-FSR full regional coverage (midfoot sensor)
❌ Battery-powered wearable form factor
❌ BLE + mobile app (Wi-Fi + laptop is current limitation)
❌ Bilateral simultaneous measurement (two insoles)
❌ Longitudinal session history (resets on power cycle)
❌ Clinical validation study (30-subject physiotherapy pilot)

---

## 4. Why Now

**Hardware cost curve:** ESP32-S3 is ₹400. FSR sensor is ₹400. TMP117 is ₹350.
Clinical-relevant foot monitor BOM is now under ₹2,500. In 2020 this would have
been ₹15,000+.

**TinyML frameworks:** TFLite Micro and CMSIS-NN now deploy shallow autoencoders on
MCUs with 256 KB flash — personal anomaly detection at the edge is feasible for
the first time.

**Regulatory pathway:** CDSCO Medical Devices Rules 2017 provides Class A/B digital
health pathway. FDA's Digital Health CoE has published SaMD guidance. Regulatory
risk is lower than it was 3 years ago.

**Post-COVID chronic disease surge:** Indian diabetes prevalence increased ~15%
2019–2023. Prevention and monitoring market is growing faster than treatment.

**Dataset availability:** StepUP-P150 (CC BY 4.0, 2024) enabled algorithm validation
without a proprietary clinical study. This removed the biggest technical risk.

---

## 5. Funding Ask

### Total ask: ₹35,00,000 (~$42,000 USD)

18-month programme from current prototype to clinical pilot with validated hardware.

### Breakdown

```
Category                              Amount (₹)    %
──────────────────────────────────────────────────────
Hardware development (v2 insole)      8,00,000     22.9
Software (BLE, mobile app, backend)   6,00,000     17.1
Clinical pilot study (30 subjects)    8,00,000     22.9
Salaries / stipends (18 months)       7,00,000     20.0
Regulatory & IP (patent + CDSCO)      3,00,000      8.6
Operations (lab, cloud, travel)       2,00,000      5.7
Contingency (10%)                     1,00,000      2.8
──────────────────────────────────────────────────────
TOTAL                                35,00,000    100.0
```

### Comparable grants and sources

| Source | Amount | Status |
|---|---|---|
| BIRAC BIG | ₹50L | Apply Month 6 once hardware v2 complete |
| DST NIDHI Prayas | ₹10L | Apply now |
| AIC / Startup India seed | ₹20–50L | Continuous open |
| Angel / family round | ₹20–35L | This ask |

Private seed funding buys execution speed. Government grants provide non-dilutive
validation. Both should be pursued in parallel.

---

## 6. Phase-by-Phase Budget

### Phase 1 — Hardware v2 (Months 1–6) — ₹8,00,000

**Goal:** Wearable, battery-powered, 4-FSR, calibrated insole pair.

| Line Item | Qty | Unit (₹) | Total (₹) |
|---|---|---|---|
| ESP32-S3 DevKitC-1 | 10 | 800 | 8,000 |
| nRF52840 modules (BLE target) | 5 | 2,500 | 12,500 |
| FSR 402 sensors | 30 | 400 | 12,000 |
| TMP117 breakouts | 10 | 700 | 7,000 |
| MPU6050 breakouts | 10 | 300 | 3,000 |
| LiPo 500 mAh + TP4056 charger | 10 | 700 | 7,000 |
| Custom PCB (JLCPCB 4-layer, 40×20 mm) | 10 | 5,000 | 50,000 |
| Insole EVA foam (40A hardness) | — | — | 8,000 |
| 3D-printed heel-cup enclosures | 5 | 1,500 | 7,500 |
| Reference weights (FSR calibration) | — | — | 3,000 |
| Lab equipment (logic analyser) | 1 | 8,000 | 8,000 |
| Soldering consumables | — | — | 3,000 |
| PCB + hardware engineering (2 FTE × 6m) | — | 35,000/mo | 4,20,000 |
| PCB iteration runs × 3 | — | — | 1,50,000 |
| **Phase 1 subtotal** | | | **7,01,000** |
| Buffer 15% | | | 99,000 |
| **Phase 1 Total** | | | **8,00,000** |

---

### Phase 2 — Software & Clinical Pilot (Months 7–18) — ₹20,00,000

#### Software — ₹7,00,000

| Line Item | Cost (₹) |
|---|---|
| BLE firmware (replace Wi-Fi stack) | 80,000 |
| Flutter mobile app (iOS + Android) | 2,00,000 |
| FastAPI + PostgreSQL backend | 60,000 |
| AWS hosting (12 months) | 40,000 |
| App store fees | 20,000 |
| Software engineer (1 FTE × 12m @ ₹25k) | 3,00,000 |
| **Software Total** | **7,00,000** |

#### Clinical Pilot — ₹5,30,000

| Line Item | Cost (₹) |
|---|---|
| Physiotherapy clinic MOU | 20,000 |
| IRB/Ethics committee application | 15,000 |
| 30 subjects × 3 sessions (₹1,000 each) | 90,000 |
| Clinical coordinator (12m @ ₹20k) | 2,40,000 |
| Podiatrist advisory (12m @ ₹5k) | 60,000 |
| Consumables (insole replacement, cleaning) | 20,000 |
| Statistical analysis consultant | 40,000 |
| Journal submission (open access) | 25,000 |
| Travel to clinical site | 20,000 |
| **Clinical Total** | **5,30,000** |

#### Regulatory & IP — ₹3,00,000

| Line Item | Cost (₹) |
|---|---|
| Provisional patent (India) | 50,000 |
| PCT provisional (12-month international window) | 1,00,000 |
| CDSCO pathway analysis (regulatory consultant) | 80,000 |
| ISO 13485 readiness gap assessment | 40,000 |
| Legal (NDAs, partnership agreements) | 30,000 |
| **Regulatory Total** | **3,00,000** |

#### Operations — ₹2,00,000

| Line Item | Cost (₹) |
|---|---|
| Lab consumables (monthly restocking) | 60,000 |
| Conferences / demos (2 events) | 40,000 |
| Domain, website, branding | 20,000 |
| Software licenses | 15,000 |
| Miscellaneous | 65,000 |
| **Operations Total** | **2,00,000** |

---

### Phase 3 — Scale (Months 19–36) — ₹80,00,000 Series A

*Not part of current ask. This is the post-pilot Series A.*

| Category | Cost (₹) | Purpose |
|---|---|---|
| Manufacturing tooling (injection moulding) | 15,00,000 | 500-unit pilot run |
| Clinical validation study (300 subjects) | 25,00,000 | Regulatory submission |
| CDSCO + CE marking | 10,00,000 | Device registration |
| Sales & marketing | 15,00,000 | Clinician outreach, distribution |
| Team expansion (5 FTE × 12m) | 15,00,000 | Engineering + sales |
| **Series A Total** | **80,00,000** | |

---

## 7. Revenue Model & Unit Economics

### Hardware streams

| Tier | Price (₹) | COGS (₹) | Gross Margin |
|---|---|---|---|
| Consumer pair (2 insoles) | 12,000 | 2,500 | 79% |
| Clinical pair (calibrated + report) | 18,000 | 3,500 | 81% |
| Research kit (API + raw data export) | 30,000 | 4,000 | 87% |

**COGS per pair at 1,000 units/year:**

```
nRF52840 × 2:          ₹500
FSR sensors × 8:       ₹400
TMP117 × 2:            ₹200
MPU6050 × 2:           ₹100
Custom PCB:            ₹400
LiPo + charger:        ₹300
Insole + assembly:     ₹400
Packaging + shipping:  ₹200
───────────────────────────
Total COGS:           ₹2,500
```

### SaaS subscription

| Plan | Price/month | Target User |
|---|---|---|
| Personal | ₹299 | Individual patient / athlete |
| Professional | ₹999 | Physiotherapist (up to 20 patients) |
| Hospital | ₹4,999 | Clinic (unlimited patients + EHR API) |

**Year 3 SaaS ARR projection (5,000 active devices):**

```
Personal    3,500 × ₹299 × 12  = ₹1,25,58,000
Pro         1,250 × ₹999 × 12  = ₹1,49,85,000
Hospital      250 × ₹4,999 × 12 = ₹1,49,97,000
─────────────────────────────────────────────────
Total ARR                        ≈ ₹4.25 crore
```

### Data licensing (Year 3+)

Anonymised gait + pressure datasets (consent-based) licensed to:
- Pharmaceutical companies (neuropathy drug trials): ₹20–50L per dataset
- Orthotic/footwear manufacturers: ₹10–30L per study
- Algorithm licensing to OEM insole brands: 5% royalty

### Financial projections

| Year | Units | Hardware Revenue | SaaS ARR | Total |
|---|---|---|---|---|
| Year 1 | 50 | ₹9L | ₹1.8L | ₹10.8L |
| Year 2 | 500 | ₹90L | ₹36L | ₹1.26 Cr |
| Year 3 | 5,000 | ₹9 Cr | ₹4.25 Cr | ₹13.25 Cr |
| Year 5 | 50,000 | ₹90 Cr | ₹35 Cr | ₹1.25 Cr |

Break-even: ~Month 22 (first 300 units + 800 SaaS subscribers).

---

## 8. Go-to-Market Strategy

### Phase 1 GTM — Clinician champions (Year 1)

**Who:** 10–20 physiotherapy and diabetic foot care centres in metro India
(Chennai, Mumbai, Bengaluru, Delhi).

**Why clinicians first:** A single physiotherapist with 50 active patients = potential
₹18,000 × 50 = ₹9L hardware channel + ₹999/month subscription.

**How:**
- Free pilot units to 5 partner clinics (exchange for data sharing agreement)
- Monthly clinical webinar on foot loading and gait monitoring
- Peer-reviewed publication from pilot (most powerful clinical marketing)
- Endorsement from IDA (Indian Diabetes Association) and RSSDI

### Phase 2 GTM — Direct to patient (Year 2)

- Amazon/Flipkart listing for consumer pair
- Partnership with Apollo, Fortis, Manipal diabetology departments
- Patient referral from physiotherapy network

### Phase 3 GTM — International (Year 3)

- CE marking → UK, EU (NHS diabetic foot care protocols)
- FDA 510(k) → US market
- Distribution via Bauerfeind, Össur, or DJO partner network

---

## 9. Market Size

### Total Addressable Market (TAM)

| Segment | Market Size | CAGR |
|---|---|---|
| Diabetic foot care (global) | $7.7B by 2030 | 6.8% |
| Sports medicine wearables | $5.3B by 2028 | 11.2% |
| Elderly fall prevention | $4.8B by 2027 | 9.4% |
| **Combined TAM** | **~$18B** | |

### India SAM

```
Diabetic patients requiring foot monitoring:  ~5 million
At ₹12,000 per device pair:                  ₹6,000 Cr hardware TAM
Sports physiotherapy India:                   ~2 million users
                                              ₹2,400 Cr
─────────────────────────────────────────────────────────
India SAM:                                    ~₹8,400 Cr  ($1B)
```

### SOM (Year 5 target)

0.1% India SAM = ₹84 Cr revenue ($10M) — achievable with 50,000 devices + SaaS.

---

## 10. Competitive Landscape

| Product | Price | Pressure | Temp | Bilateral | Explainable Risk | Gait Analysis | Mobile |
|---|---|---|---|---|---|---|---|
| **SoleSense** | ₹12,000 | ✅ FSR | ✅ TMP117 | ✅ Roadmap | ✅ Full | ✅ CV+activity+trend | ✅ Roadmap |
| Nurvv Run | ₹21,000 | ✅ 16pt | ❌ | ❌ | ❌ | Cadence only | ✅ |
| Moticon OpenGo | ₹3,50,000 | ✅ 13pt | ❌ | ✅ | Partial | Basic | Partial |
| Tekscan F-Scan | ₹8,00,000+ | ✅ Hi-res | ❌ | ✅ | ❌ | ❌ | ❌ |
| Plantiga | ₹25,000 | IMU only | ❌ | ✅ | ❌ | IMU only | ✅ |
| Superfeet AI | ₹8,000 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

**Our differentiators:**
1. Only affordable device with pressure + temperature + IMU + explainable risk
2. Full gait analysis: activity class, step count, cadence, movement intensity, variability CV, personal baseline comparison, trend
3. Open-source analytics pipeline validated on 150-subject research dataset
4. Left-foot correct anatomy in UI + correct unit labelling throughout

**Moat:**
- Proprietary 134-feature pipeline (validated, open to review, patent-pending algorithm)
- Clinical relationships from pilot (cannot be bought)
- Longitudinal pressure + gait + temperature data post-Year 2 (most valuable asset)

---

## 11. Team & Hiring Plan

### Current team capability

The prototype demonstrates: embedded firmware (C++/Arduino), signal processing (Python/NumPy),
interactive dashboard (Streamlit/Plotly), hardware design (ESP32-S3, FSR, I²C sensors),
analytics pipeline architecture, and test coverage. This represents rare full-stack
hardware+software depth.

### Seed phase hiring (18 months)

| Role | Start | Cost/month | Why critical |
|---|---|---|---|
| Embedded systems engineer | Month 1 | ₹35,000 | Custom PCB, BLE nRF52840 firmware |
| Full-stack / mobile developer | Month 7 | ₹30,000 | Flutter app, FastAPI backend |
| Clinical research coordinator | Month 7 | ₹20,000 | IRB, data collection, clinician liaison |

Total salary: ₹9,60,000 over 18 months.

### Advisory board needed

- Podiatrist / Diabetic foot specialist — clinical threshold validation
- Sports physiotherapist — athlete use case validation
- Regulatory affairs consultant — CDSCO / CE / FDA pathway
- Medtech entrepreneur — commercialisation strategy

---

## 12. Milestones & Timeline

| Month | Milestone | Success Metric |
|---|---|---|
| 1 | BOM finalised, PCB design started | Schematic complete |
| 2 | 4-FSR insole assembled and tested | All sensors reading |
| 3 | FSR bench calibration complete | R² > 0.95 fit |
| 4 | Bilateral prototype (2 insoles) | Both streaming simultaneously |
| 5 | BLE firmware proof-of-concept | Packet on Android |
| 6 | Phase 1 review + demo | Demo to advisors |
| 7 | IRB submission | Application submitted |
| 8 | Mobile app alpha (BLE + basic dashboard) | Runs iOS + Android |
| 9 | First 5 pilot subjects enrolled | Data collection started |
| 10 | Mobile app beta (full 8 sections) | All Live Hardware sections on mobile |
| 12 | 20 pilot subjects complete | 60 sessions collected |
| 14 | Provisional patent filed | Filing receipt |
| 15 | Pilot report + journal submission | Internal report complete |
| 16 | App on TestFlight / Play Beta | External testers |
| 18 | Phase 2 demo day | 30 subjects, working app, pilot data |

---

## 13. Risk Register & Mitigation

### Technical

| Risk | Prob. | Impact | Mitigation |
|---|---|---|---|
| FSR non-linearity at high loads | High | Medium | Log calibration curve + software correction |
| BLE interference in hospital | Medium | Low | Test early; Wi-Fi fallback |
| nRF52840 firmware migration | Medium | High | Keep ESP32-S3 as validated fallback |
| Battery life < 8 h | Medium | High | BLE + sleep modes → 5× power reduction vs Wi-Fi |
| PCB manufacturing defects | Low | Medium | 3 iteration runs budgeted |

### Clinical / Regulatory

| Risk | Prob. | Impact | Mitigation |
|---|---|---|---|
| IRB > 3 months | Medium | Medium | Submit Month 7; observational design = faster |
| Pilot dropouts | Low | Medium | Over-recruit 40 for 30 completions |
| CDSCO Class III classification | Low | Very High | Pre-submission meeting; wellness device positioning |
| Patent conflict | Low | High | Prior art search before filing |

### Market

| Risk | Prob. | Impact | Mitigation |
|---|---|---|---|
| Clinician adoption slow | Medium | High | Free pilot + CME credits + peer-reviewed publication |
| Competitor copies open-source | Low | High | Patent + data moat + clinical relationships |
| Insurance non-reimbursable (initially) | High | Medium | B2B direct to clinics as primary Year 1–2 channel |

---

## 14. Scale-Up Architecture

### Hardware manufacturing scale

| Volume | Strategy | Unit COGS (₹) |
|---|---|---|
| 1–50 (prototype) | Hand-assembled | 3,500 |
| 50–500 (pilot) | JLCPCB SMT + hand final | 3,000 |
| 500–5,000 (early commercial) | Contract manufacturer | 2,200 |
| 5,000–50,000 (commercial) | ODM + insole tooling | 1,800 |
| 50,000+ (scale) | Dedicated line | 1,200 |

### Software infrastructure scale

| Users | Stack | Monthly Cost (₹) |
|---|---|---|
| < 100 | EC2 + RDS (AWS Mumbai) | 8,000 |
| 100–1,000 | Auto-scaling + RDS Multi-AZ | 25,000 |
| 1,000–10,000 | ECS Fargate + Aurora | 75,000 |
| 10,000+ | Microservices + CDN | 2,00,000+ |

**Data architecture:**
- Time-series pressure: Amazon Timestream
- User profiles / sessions: PostgreSQL (RDS)
- ML training: AWS SageMaker (pay-per-use)
- Mobile sync: AWS AppSync (offline-first GraphQL)

### Regulatory scale

| Geography | Path | Timeline | Cost (₹) |
|---|---|---|---|
| India | CDSCO Class B | 6–12 months | 5–15L |
| EU | CE Class IIa | 12–18 months | 20–40L |
| USA | FDA 510(k) De Novo | 18–24 months | 40–80L |
| UK | UKCA | 6–12 months after CE | 10–20L |

---

## 15. Cross-Questions Funders Will Ask

---

**Q1: Why should I fund this and not wait for a more mature version?**

Because the two highest-risk milestones are not yet cleared:
(a) Hardware calibration — does the insole give repeatable, reliable data outside
    a lab? → Phase 1 answers this.
(b) Clinical relevance — does the algorithm detect real patterns in real patients?
    → Phase 2 pilot answers this.

Without this funding, both questions remain open and Series A investors will not commit.
₹35L closes the two highest risks. That is exactly what seed funding is for.

---

**Q2: The BOM is ₹2,500 but retail is ₹12,000 — isn't 79% gross margin exploitative?**

No. Medical devices commonly run 70–85% gross margin because the price reflects value
delivered, not COGS. A ₹12,000 device that prevents one ₹5L diabetic foot ulcer
treatment has a 40× value-to-cost ratio. The margin funds R&D, clinical trials,
regulatory submissions, customer support, and software infrastructure.
Compare: pharmaceutical gross margins are 80–90%.

---

**Q3: You're using an open-source analytics pipeline — anyone can copy it.**

True. The algorithm itself can be copied (though it is patent-pending). What cannot
be copied:
(a) Clinical relationships built during the 30-subject pilot
(b) Longitudinal data from real patients (most valuable asset, takes years to build)
(c) The validated hardware + software integration (replicating this takes 6–12 months)
(d) Trust built with clinicians through peer-reviewed publications

This is the same defence as any open-source company (MongoDB, Elastic) — the product
is not the code alone.

---

**Q4: How do you handle liability if a user misses a critical warning?**

Three layers:
(a) Device labelling: "SoleSense is a supplementary monitoring tool, not a diagnostic
    device. It does not replace clinical assessment."
(b) Conservative thresholds: tuned to minimise false negatives (over-alerts rather
    than under-alerts) — we prefer unnecessary MONITOR alerts over missed ALERT events.
(c) EULA and informed consent: user acknowledges the research prototype status.

Long-term: CDSCO/CE/FDA registration with appropriate intended-use statement is the
formal liability protection.

---

**Q5: What is the actual data privacy plan for health data?**

India's DPDP Act 2023 applies. Our plan:
- Explicit consent before any collection
- Data localisation: AWS Mumbai region
- No identifiable health data shared without separate Data Processing Agreement
- On-device processing where possible (pressure fractions do not leave device in production)
- Right to erasure on request
- ISO 27001 certification planned for Year 3

---

**Q6: CDSCO takes forever — how do you commercialise while waiting?**

Two-track approach:
(a) **Wellness device positioning:** A device that monitors loading without making a
    diagnostic claim operates as a wellness/fitness device under current CDSCO framework.
    This allows market entry immediately.
(b) **B2B clinical sales:** Hospitals and clinics can procure research tools under
    institutional procurement without consumer device registration.

Medical device registration runs in parallel — it does not block revenue.

---

**Q7: FSR sensors have a 6-month lifespan — doesn't that destroy retention?**

Yes, this is a real issue and the plan is to turn it into a recurring revenue stream.
The electronics module clips into a replaceable insole insert containing the sensors.
The insert is sold as a ₹600–800 consumable with 6-month expected replacement.
This mirrors the razor/blade model — hardware (high margin) + consumable (recurring).
Self-calibration check firmware alerts the user when sensor drift exceeds 15%.

---

**Q8: The gait analysis uses CV of acceleration magnitude — is that validated?**

CV of |A| as a gait stability metric is derived from published accelerometry literature.
Menz et al. (2003, Gait & Posture) and Kavanagh & Menz (2008) demonstrated that
trunk/foot acceleration CV correlates with gait stability in elderly subjects.
Our implementation uses the same mathematical construct (std/mean) applied to the
foot-mounted sensor — which is actually more sensitive to local foot motion irregularity
than trunk-mounted sensors. The 15% CV threshold as MONITOR and 30% as elevated
are conservatively set — empirical validation against clinical outcomes is Phase 3.

---

**Q9: Why ₹35L specifically — how did you arrive at this number?**

The number is built bottom-up from itemised line costs (see Section 6), not top-down
from "what seems reasonable." Key validation points:
- Hardware cost: 3 PCB runs × ₹50K + engineering salary × 6m = ₹5.7L (hardware alone)
- Clinical pilot: IRB + 30 subjects × 3 sessions + coordinator salary = ₹3.65L (minimum viable study)
- Mobile app: 12 months × ₹25K + Flutter outsourcing = ₹5L (conservative estimate)
- Regulatory: patent (₹1.5L) + consultant (₹1.2L) = ₹2.7L
- These four pillars total ₹17L; operations, salaries, and contingency account for the rest.

Anything less than ₹25L would not fund a publishable clinical study, which is the
single most important deliverable for Series A fundraising.

---

**Q10: What does this funding buy in terms of the final product quality?**

At the end of 18 months, SoleSense will be:
- A calibrated (real kPa, not proxy) 4-FSR insole pair with LiPo battery
- Connected to iOS and Android via BLE
- With a published 30-subject safety and usability study
- With a provisional patent protecting the algorithm
- With CDSCO wellness device registration in progress
- With a working cloud backend and session history

This is the package needed to raise ₹80L Series A from a serious medtech investor.

---

**Q11: What is the exit valuation basis?**

Year 3 projection: ₹13.25 Cr total revenue, growing ~3× annually.
At 3–5× ARR valuation (standard for health SaaS): ₹40–65 Cr.

Strategic acquisition premium from medtech (DJO, Össur, Bauerfeind): 5–8×
revenue = ₹65–105 Cr at Year 3, higher at Year 5 with regulatory clearance.

Insurance platform acquisition (Star Health, Niva Bupa): prevention programme
ROI argument — if SoleSense prevents 1 in 50 amputations at ₹6L cost per
amputation, per 10,000 users it saves ₹12 Cr annually in claims. Worth paying
₹50–100 Cr for that capability.

---

**Q12: How is the gait data from the IMU used commercially beyond the core device?**

Three downstream uses:
(a) **Pharmaceutical trials:** Gait quality as an endpoint for neuropathy drug trials.
    Current trials use expensive GAITRite mats in lab settings. SoleSense provides
    continuous real-world gait data at a fraction of the cost.
(b) **Footwear optimisation:** Shoe manufacturers pay for load + gait data to validate
    that their designs reduce pressure in high-risk populations.
(c) **Rehabilitation outcomes:** Physiotherapy outcomes are notoriously hard to measure
    objectively. SoleSense provides week-by-week gait improvement data — this has
    direct billing and insurance reimbursement value.

---

*For the complete technical explanation of every formula, threshold, and graph,
see UNDERSTANDING.md in this directory.*

*For architecture overview and quick-start, see the main README.md.*

---

<div align="center">

**SoleSense** · Preventing foot complications through continuous, affordable monitoring

*"Every step matters. We make sure it's a safe one."*

Contact: [your email] | Repository: solesense-main | Patent pending

</div>
