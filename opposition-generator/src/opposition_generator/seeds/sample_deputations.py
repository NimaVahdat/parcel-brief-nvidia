"""Committed synthetic deputation corpus for local development and tests.

The real corpus is scraped from TMMIS into data/deputations.jsonl (gitignored).
These hand-written samples mirror the shape and voice of real Toronto deputations
so the embed -> retrieve -> generate pipeline is runnable and testable without a
scrape. They are clearly synthetic and must not be presented as real submissions.

Concern tags use the canonical taxonomy keys (see forecast/taxonomy.py).
"""

from __future__ import annotations

SAMPLE_DEPUTATIONS: list[dict] = [
    {
        "deputation_id": "seed-tb-001",
        "agenda_item_id": "TE-SEED.1",
        "committee": "te",
        "meeting_date": "2023-04-12",
        "neighborhood": "Trinity-Bellwoods",
        "project_type": "midrise-residential",
        "concerns": ["shadow", "character", "affordability"],
        "groups": ["Friends of Trinity-Bellwoods"],
        "text": (
            "As a homeowner on Montrose Avenue for twenty-two years, I am writing to "
            "oppose the proposed nine-storey building on Dundas Street West. The shadow "
            "study will show late-afternoon shadows falling across Trinity-Bellwoods Park "
            "where our children play. A building of this height is utterly out of "
            "character with the two- and three-storey main street we have always known. "
            "Worst of all, not a single unit is affordable while long-time renters are "
            "being pushed out of this neighbourhood. I urge the Committee to refuse this "
            "application as submitted."
        ),
    },
    {
        "deputation_id": "seed-tb-002",
        "agenda_item_id": "TE-SEED.2",
        "committee": "te",
        "meeting_date": "2022-11-03",
        "neighborhood": "Trinity-Bellwoods",
        "project_type": "midrise-mixed-use",
        "concerns": ["traffic", "parking", "density"],
        "groups": ["Trinity-Bellwoods Residents Association"],
        "text": (
            "On behalf of the Trinity-Bellwoods Residents Association, we object to the "
            "intensification proposed at this corner. Ossington is already gridlocked on "
            "weekends and the reduced parking provision will push dozens of cars onto our "
            "residential side streets. The density being requested far exceeds what the "
            "avenue can absorb. We are not opposed to development, but this proposal is "
            "too much, too fast."
        ),
    },
    {
        "deputation_id": "seed-tb-003",
        "agenda_item_id": "TE-SEED.3",
        "committee": "te",
        "meeting_date": "2024-02-20",
        "neighborhood": "Trinity-Bellwoods",
        "project_type": "midrise-residential",
        "concerns": ["construction", "privacy"],
        "groups": [],
        "text": (
            "My rear yard backs directly onto the proposed development site. The "
            "construction-management impacts alone will be severe: two years of noise, "
            "dust, and haul trucks down a narrow laneway. The proposed balconies look "
            "directly into my bedroom windows. At minimum the applicant must increase the "
            "side setbacks and commit to limited construction hours."
        ),
    },
    {
        "deputation_id": "seed-ros-001",
        "agenda_item_id": "TE-SEED.4",
        "committee": "te",
        "meeting_date": "2023-06-15",
        "neighborhood": "Rosedale",
        "project_type": "lowrise-residential",
        "concerns": ["heritage", "character", "height"],
        "groups": ["Rosedale-Moore Park Residents Association"],
        "text": (
            "The Rosedale-Moore Park Residents Association strongly opposes the demolition "
            "of the heritage home at this address. This is a designated property within an "
            "established low-rise neighbourhood, and the replacement structure's height is "
            "wholly inappropriate to the streetscape. The heritage frontage must be "
            "retained and integrated, not erased."
        ),
    },
    {
        "deputation_id": "seed-ros-002",
        "agenda_item_id": "TE-SEED.5",
        "committee": "te",
        "meeting_date": "2021-09-08",
        "neighborhood": "Rosedale",
        "project_type": "lowrise-residential",
        "concerns": ["privacy", "environment", "character"],
        "groups": ["Rosedale-Moore Park Residents Association"],
        "text": (
            "This over-scaled addition will overlook three neighbouring rear gardens and "
            "requires removing two mature oak trees protected under the ravine bylaw. The "
            "tree canopy here is part of what defines Rosedale. We ask that the protected "
            "trees be preserved and the massing be reduced to respect adjacent privacy."
        ),
    },
    {
        "deputation_id": "seed-les-001",
        "agenda_item_id": "TE-SEED.6",
        "committee": "te",
        "meeting_date": "2023-10-25",
        "neighborhood": "Leslieville",
        "project_type": "midrise-mixed-use",
        "concerns": ["affordability", "displacement", "density"],
        "groups": ["Leslieville Tenants Network"],
        "text": (
            "The Leslieville Tenants Network speaks for the renters who will be displaced "
            "by this project. The existing affordable rental units on this site will be "
            "demolished and replaced with condominiums none of us can afford. We are "
            "facing renoviction in all but name. We demand right-of-first-refusal at "
            "comparable rents and a meaningful affordable set-aside."
        ),
    },
    {
        "deputation_id": "seed-les-002",
        "agenda_item_id": "TE-SEED.7",
        "committee": "te",
        "meeting_date": "2022-05-19",
        "neighborhood": "Leslieville",
        "project_type": "midrise-residential",
        "concerns": ["traffic", "shadow"],
        "groups": [],
        "text": (
            "Queen Street East cannot handle the additional traffic this building will "
            "generate, and the morning shadow will fall across the daycare playground "
            "next door. I ask the applicant to step back the upper floors so the daycare "
            "keeps its morning sun."
        ),
    },
    {
        "deputation_id": "seed-ken-001",
        "agenda_item_id": "TE-SEED.8",
        "committee": "te",
        "meeting_date": "2024-01-17",
        "neighborhood": "Kensington-Chinatown",
        "project_type": "highrise-mixed-use",
        "concerns": ["displacement", "character", "affordability", "height"],
        "groups": ["Friends of Kensington Market"],
        "text": (
            "Friends of Kensington Market cannot stay silent as a thirty-storey tower is "
            "proposed on the edge of one of Toronto's last truly affordable, "
            "independent-business neighbourhoods. The height is alien to the Market. The "
            "ground-floor rents will drive out the small grocers and vendors who give "
            "Kensington its character, and existing tenants will be displaced. This tower "
            "does not belong here."
        ),
    },
    {
        "deputation_id": "seed-ken-002",
        "agenda_item_id": "TE-SEED.9",
        "committee": "te",
        "meeting_date": "2023-03-02",
        "neighborhood": "Kensington-Chinatown",
        "project_type": "midrise-mixed-use",
        "concerns": ["traffic", "parking", "construction"],
        "groups": ["Kensington Market BIA"],
        "text": (
            "The Kensington Market BIA is concerned that the loading and parking plan will "
            "choke our already narrow pedestrian streets, and that years of construction "
            "will starve our member businesses of foot traffic. We need a construction "
            "mitigation plan and a realistic loading strategy before this proceeds."
        ),
    },
    {
        "deputation_id": "seed-ann-001",
        "agenda_item_id": "TE-SEED.10",
        "committee": "te",
        "meeting_date": "2022-08-11",
        "neighborhood": "Annex",
        "project_type": "highrise-residential",
        "concerns": ["height", "shadow", "density"],
        "groups": ["Annex Residents Association"],
        "text": (
            "The Annex Residents Association objects to the requested height and density, "
            "which would cast new shadows on the historic houses along Madison Avenue and "
            "overwhelm the area's mid-rise scale. We support gentle density, but this "
            "proposal seeks far more than the Official Plan contemplates for this site."
        ),
    },
    {
        "deputation_id": "seed-ann-002",
        "agenda_item_id": "TE-SEED.11",
        "committee": "te",
        "meeting_date": "2024-04-09",
        "neighborhood": "Annex",
        "project_type": "midrise-residential",
        "concerns": ["heritage", "character"],
        "groups": ["Annex Residents Association"],
        "text": (
            "This block contains several listed properties and the proposed facade is a "
            "blank glass box that ignores the brick-and-bay-window character of the Annex. "
            "We ask that the design respond to the heritage context rather than override "
            "it."
        ),
    },
    {
        "deputation_id": "seed-bea-001",
        "agenda_item_id": "TE-SEED.12",
        "committee": "te",
        "meeting_date": "2023-07-06",
        "neighborhood": "Beaches-East York",
        "project_type": "midrise-residential",
        "concerns": ["parking", "traffic", "character"],
        "groups": ["Beaches Residents Association"],
        "text": (
            "Queen Street in the Beaches is a low-rise main street and this proposal does "
            "not fit. Parking is already impossible near the boardwalk in summer, and the "
            "reduced parking ratio will make it worse for everyone. Please respect the "
            "scale of our community."
        ),
    },
    {
        "deputation_id": "seed-bea-002",
        "agenda_item_id": "TE-SEED.13",
        "committee": "te",
        "meeting_date": "2021-10-14",
        "neighborhood": "Beaches-East York",
        "project_type": "lowrise-residential",
        "concerns": ["environment", "privacy"],
        "groups": [],
        "text": (
            "The site drains toward the beach and this development will worsen stormwater "
            "runoff into the lake. It also removes a mature silver maple. I urge green-roof "
            "and stormwater-retention conditions and retention of the tree."
        ),
    },
    {
        "deputation_id": "seed-jct-001",
        "agenda_item_id": "TE-SEED.14",
        "committee": "te",
        "meeting_date": "2024-03-21",
        "neighborhood": "Junction",
        "project_type": "midrise-mixed-use",
        "concerns": ["affordability", "density", "traffic"],
        "groups": ["Junction Residents Association"],
        "text": (
            "The Junction has welcomed growth, but this proposal offers no affordable "
            "housing while requesting significant additional density. Dundas Street West "
            "is increasingly congested. We would support this with a real affordable "
            "component and transit-supportive measures."
        ),
    },
    {
        "deputation_id": "seed-jct-002",
        "agenda_item_id": "TE-SEED.15",
        "committee": "te",
        "meeting_date": "2022-12-01",
        "neighborhood": "Junction",
        "project_type": "highrise-residential",
        "concerns": ["height", "shadow", "construction"],
        "groups": ["Junction Residents Association"],
        "text": (
            "A twenty-five storey tower at this rail-adjacent site will shadow the "
            "townhomes to the north all winter and subject them to years of construction "
            "disruption. The height should transition down toward the existing low-rise "
            "fabric."
        ),
    },
    {
        "deputation_id": "seed-dav-001",
        "agenda_item_id": "TE-SEED.16",
        "committee": "te",
        "meeting_date": "2023-05-30",
        "neighborhood": "Davisville",
        "project_type": "highrise-residential",
        "concerns": ["density", "traffic", "parking", "shadow"],
        "groups": ["Sherwood Park Residents Association"],
        "text": (
            "Yonge and Davisville is already a wall of towers. Adding another at this "
            "density will overload the intersection, eliminate visitor parking, and shadow "
            "Sherwood Park. The community has absorbed more than its share of growth; this "
            "site should deliver real public benefit if it proceeds."
        ),
    },
]
