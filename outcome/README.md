# Outcome

The consolidated deliverables. Each HTML file is self-contained — download and open in a browser. Regenerate with the builders in `analysis/` (see the root README).

| File | Audience | What |
|---|---|---|
| `intelligence_hub.html` | Leadership · Tech leads · Sales | One-stop hub: top-250 screen, 25 dossiers + pitches, market map, outreach playbook, method & QC |
| `access_architecture.html` | Tech leads · Security · Platform | Layered IAM data-access design with a live per-role lens from `policy.py`, and what Claude users need |
| `project_walkthrough.html` | Everyone | Nine-stage walkthrough of how the project was built |
| `How_the_Banyan_Screen_Was_Built.docx` | Everyone | Word version of the walkthrough with charts |

`intelligence_hub.html` embeds the full unfiltered dataset — treat it as a Leadership / tech-lead artifact and share accordingly; role-filtered views come from `analysis/build_dossiers.py` (fails closed on role) or from serving data through the enforcement point described in `access_architecture.html`.
