-- Target-class registry and label tables (ROADMAP "Scope", A1). Idempotent: safe to re-run.
--
-- ref.target_class is the single source of truth for every class's detectability, grid,
-- burial sensitivity, and detection parameters. Nothing scores, detects, validates, or
-- renders without a class_id from this table (CLAUDE.md invariants: "No unqualified
-- score", "Detection parameters are per class, never global").
--
-- The seed uses ON CONFLICT DO UPDATE so `midden db init` refreshes params in place.
-- Parameter values are starting points chosen against the landform-archaeology feature
-- catalog (radius ~ feature size: hearth 8-15 m, mound 20-80 m base, mill race ~1 m wide,
-- cellar hole 3-6 m). They are swept parameters, not decisions — a sweep records which
-- class it was swept for, and the registry row is where the winning value lands.

-- ---------------------------------------------------------------------------
-- The class registry.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref.target_class (
    class_id           text PRIMARY KEY,
    period             text NOT NULL,
    morphology         text NOT NULL,      -- plan form and expected size range, metres
    grid               text NOT NULL,      -- which grid(s) this class is worked on
    detectability      text NOT NULL,      -- honest, per class, never global
    burial_sensitivity boolean NOT NULL,   -- does overbank burial remove the signature?
    label_source       text NOT NULL,      -- where controls for this class come from
    -- Per-class detection parameters. Shape:
    --   openness.search_radius_m, openness.num_directions, slrm.smoothing_radius_m,
    --   min_area_m2, and a detect block for the firing rule:
    --   detect.surfaces (raster kinds), detect.threshold_pctile, detect.min_cells.
    -- Model-grid proxy classes carry '{}' — their parameters are the weight set keyed
    -- by class_id under weights/.
    params             jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes              text,

    CONSTRAINT target_class_period_check CHECK (period IN
        ('precontact', 'historic', 'either')),
    CONSTRAINT target_class_grid_check CHECK (grid IN
        ('detection', 'model', 'both')),
    CONSTRAINT target_class_detectability_check CHECK (detectability IN
        ('direct', 'proxy', 'invisible'))
);

COMMENT ON TABLE ref.target_class IS
    'Single source of truth for target classes: detectability, grid, burial '
    'sensitivity, and per-class detection parameters. Every scoring, detection, '
    'validation, and render operation takes a class_id from here.';

-- ---------------------------------------------------------------------------
-- Control sites: labelled points with mandatory provenance. Replaces the n=2
-- whole-park-AOI control situation (ROADMAP A1). positional_confidence_m travels
-- with every point and is the tolerance radius in validation — a "hit" inside a
-- tolerance that was never recorded is not a hit.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref.control_sites (
    site_id                 serial PRIMARY KEY,
    class_id                text NOT NULL REFERENCES ref.target_class(class_id),
    name                    text NOT NULL,
    source                  text NOT NULL,  -- 'usgs_histmap' | 'nrhp' | ...
    source_id               text,           -- registry number, catalogue id
    source_sheet            text,           -- histmap: ref.histmap_sheet.sheet_id
    map_year                int,            -- histmap: edition year the symbol appears on
    positional_confidence_m real,
    -- Machine-digitized labels stay 'unreviewed' until a human confirms them.
    -- Unreviewed labels may drive detection runs; they are flagged in every
    -- validation report and never silently promoted.
    review_status           text NOT NULL DEFAULT 'unreviewed',
    geom                    geometry(Point, 26916) NOT NULL,
    derivation_id           int REFERENCES derived.derivation(id) ON DELETE SET NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT control_sites_review_check CHECK (review_status IN
        ('unreviewed', 'confirmed', 'rejected'))
);
CREATE INDEX IF NOT EXISTS control_sites_geom_idx
    ON ref.control_sites USING gist (geom);
CREATE INDEX IF NOT EXISTS control_sites_class_idx
    ON ref.control_sites (class_id);
CREATE INDEX IF NOT EXISTS control_sites_sheet_idx
    ON ref.control_sites (source_sheet) WHERE source_sheet IS NOT NULL;

COMMENT ON TABLE ref.control_sites IS
    'Labelled control points with mandatory provenance (source, sheet/id, class, '
    'positional confidence). Labels from different sources are never pooled without '
    'recording it.';

-- ---------------------------------------------------------------------------
-- Historic map sheets (USGS HTMC quads). One row per fetched, warped, catalogued
-- scan. Points digitized from a sheet reference it via control_sites.source_sheet.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref.histmap_sheet (
    sheet_id                text PRIMARY KEY,  -- HTMC scan identifier
    cell_name               text NOT NULL,     -- quad cell, e.g. 'Kingston Springs'
    map_year                int NOT NULL,      -- edition year printed on the sheet
    scale                   int NOT NULL,      -- denominator, e.g. 62500
    source_url              text NOT NULL,
    path                    text,              -- local COG, warped to EPSG:26916
    -- NMAS-derived horizontal error for the scale plus a georeferencing margin;
    -- the value and its derivation are recorded in the fetch derivation params.
    positional_confidence_m real NOT NULL,
    footprint               geometry(Polygon, 26916),
    derivation_id           int REFERENCES derived.derivation(id) ON DELETE SET NULL,
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS histmap_sheet_footprint_idx
    ON ref.histmap_sheet USING gist (footprint);

COMMENT ON TABLE ref.histmap_sheet IS
    'Historic USGS topographic quad scans: edition year, scale, source URL, and the '
    'positional error that every point digitized from the sheet inherits.';

-- ---------------------------------------------------------------------------
-- Seed: the initial registry from ROADMAP "Scope". Detectability is honest and
-- per class; params follow the radius ~ feature-size rule from the
-- landform-archaeology visualization guide.
-- ---------------------------------------------------------------------------
INSERT INTO ref.target_class
    (class_id, period, morphology, grid, detectability, burial_sensitivity,
     label_source, params, notes)
VALUES
    -- Precontact -----------------------------------------------------------
    ('mound_earthwork', 'precontact',
     'Flat-topped platform or conical mound, banks and ditches; 20-80 m base, 0.3-8 m relief',
     'both', 'direct', false, 'nrhp',
     '{"openness": {"search_radius_m": 50.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 25.0},
       "min_area_m2": 300,
       "detect": {"surfaces": {"openness_pos": "high", "openness_neg": "high", "slrm": "high"},
                  "threshold_pctile": 95, "min_cells": 200, "feature_radius_m": 40.0}}',
     'What mound-bottom and castalian-springs actually are. Site plan (plaza '
     'arrangement) is the strongest identifier; a single isolated rise usually is not one.'),

    ('rockshelter', 'precontact',
     'Bluff-line overhang; concave recess at bluff base, metres to tens of metres wide',
     'detection', 'direct', false, 'none_yet',
     '{"openness": {"search_radius_m": 15.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 15.0},
       "min_area_m2": 25,
       "detect": {"surfaces": {"openness_neg": "high", "slrm": "low"},
                  "threshold_pctile": 95, "min_cells": 40, "feature_radius_m": 10.0}}',
     'Gated on a bluff mask, not a suitability surface (ROADMAP E). The reason the '
     '0.5 m chain exists on the Highland Rim margin.'),

    ('chert_quarry', 'precontact',
     'Pit clusters on outcrop, 2-8 m pits with adjacent spoil; elevation-following alignment',
     'detection', 'direct', false, 'none_yet',
     '{"openness": {"search_radius_m": 10.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 10.0},
       "min_area_m2": 10,
       "detect": {"surfaces": {"openness_neg": "high", "openness_pos": "high"},
                  "threshold_pctile": 95, "min_cells": 12, "feature_radius_m": 5.0}}',
     'Pit-and-spoil pairing distinguishes from sinkholes (no spoil). Constrained to '
     'chert-bearing outcrop once dist_to_chert_outcrop_m exists (C4).'),

    ('cave_entrance', 'precontact',
     'Karst entrance: sinkhole margin or bluff-base concavity, metres wide',
     'detection', 'direct', false, 'none_yet',
     '{"openness": {"search_radius_m": 15.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 15.0},
       "min_area_m2": 10,
       "detect": {"surfaces": {"openness_neg": "high"},
                  "threshold_pctile": 95, "min_cells": 20, "feature_radius_m": 5.0}}',
     'Feeds saltpeter_works. Cave locations are sensitive; treat detections as '
     'restricted-adjacent and do not publish coordinates.'),

    ('open_habitation', 'precontact',
     'No surface expression; landform suitability only (terrace, confluence, soils)',
     'model', 'proxy', true, 'none_yet',
     '{}',
     'The current predictive target. Weight set: weights/open_habitation.yml. Never '
     'present a proxy result as a detection.'),

    ('midden', 'precontact',
     'Low convex refuse lens, tens of metres, usually buried or plowed flat',
     'model', 'proxy', true, 'none_yet',
     '{}',
     'Keep, do not lead with. High burial risk; absence in LiDAR is not evidence of absence.'),

    ('stone_box_cemetery', 'precontact',
     'Subsurface slab-lined graves; no reliable surface expression',
     'model', 'proxy', true, 'none_yet',
     '{}',
     'Middle Cumberland Mississippian. Model-grid proxy only.'),

    -- Historic --------------------------------------------------------------
    ('charcoal_hearth', 'historic',
     'Flat circular platform 8-15 m, 0.2-0.5 m relief; cut-and-fill D-shape on slopes',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 10.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 15.0},
       "min_area_m2": 50,
       "detect": {"surfaces": {"slrm": "high", "openness_pos": "high"},
                  "threshold_pctile": 95, "min_cells": 50, "feature_radius_m": 7.0}}',
     'Montgomery Bell iron district. Clustering 50-200 m apart is the identifier; '
     'the confuser is a log landing (20-40 m, skid trails converge on it).'),

    ('iron_works', 'historic',
     'Furnace stack, forge, ore pits with spoil, race cuts; mixed convex and concave',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 15.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 15.0},
       "min_area_m2": 20,
       "detect": {"surfaces": {"openness_pos": "high", "openness_neg": "high"},
                  "threshold_pctile": 95, "min_cells": 30, "feature_radius_m": 5.0}}',
     'Anchors hearth clusters: hearths sit within hauling distance of the furnace.'),

    ('mill_seat', 'historic',
     'Headrace cut ~1 m wide, dam abutment, leveled seat; linear concave features',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 5.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 10.0},
       "min_area_m2": 2,
       "detect": {"surfaces": {"openness_neg": "high", "slrm": "low"},
                  "threshold_pctile": 95, "min_cells": 8, "feature_radius_m": 10.0}}',
     'The A2 vanished-feature class. Metre-scale cut: the global 10 m radius is blind '
     'to it, which is why parameters are per class. Fords nearby are multi-component.'),

    ('homestead', 'historic',
     'Cellar depression 3-6 m rectangular, chimney fall mound, terraced yard, springhouse',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 8.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 10.0},
       "min_area_m2": 9,
       "detect": {"surfaces": {"openness_neg": "high", "slrm": "low"},
                  "threshold_pctile": 95, "min_cells": 24, "feature_radius_m": 5.0}}',
     'Rectangularity at 4 m is a strong cultural indicator. Historic quads mark '
     'structures: symbol + cellar hole is near-certain confirmation.'),

    ('civic_structure', 'historic',
     'School or church building site: foundation, chimney fall, terraced ground; 4-10 m footprint',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 8.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 10.0},
       "min_area_m2": 9,
       "detect": {"surfaces": {"openness_neg": "high", "slrm": "low"},
                  "threshold_pctile": 95, "min_cells": 24, "feature_radius_m": 5.0}}',
     'Added 2026-09-05 (owner decision, 23 symbols on the first two sheets). Same '
     'detection signature as homestead, so the two pool naturally at 0.5 m; separate '
     'class because the siting model differs (crossroads/centrality vs '
     'water/fields/springhouse), and a class is a siting model plus a signature. '
     'Unpooling must never depend on parsing name strings.'),

    ('family_cemetery', 'historic',
     'Rows of small regular depressions, low enclosure wall or fence line',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 10.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 10.0},
       "min_area_m2": 2,
       "detect": {"surfaces": {"openness_neg": "high", "slrm": "low"},
                  "threshold_pctile": 95, "min_cells": 8, "feature_radius_m": 10.0}}',
     'High public value, frequently unrecorded. Report, never investigate; suspected '
     'burials get appropriate-care handling.'),

    ('road_trace', 'historic',
     'Sunken roadbed, braided linear depressions, ford approach cuts',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 10.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 15.0},
       "min_area_m2": 20,
       "detect": {"surfaces": {"openness_neg": "high"},
                  "threshold_pctile": 95, "min_cells": 40, "feature_radius_m": 10.0}}',
     'Modern skid trails look similar; age is not readable from form alone — '
     'cross-check the quad edition dates.'),

    ('saltpeter_works', 'historic',
     'Cave-linked leaching vats and spoil at entrances; mostly interior, little surface form',
     'detection', 'proxy', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 15.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 15.0},
       "min_area_m2": 10,
       "detect": {"surfaces": {"openness_neg": "high"},
                  "threshold_pctile": 95, "min_cells": 20, "feature_radius_m": 5.0}}',
     'Proxy: cave entrance detection plus the historic record. Never report entrance '
     'detection alone as a saltpeter detection.'),

    ('field_boundary', 'historic',
     'Stone fence ~1 m wide linear rise; cleared-line edges',
     'detection', 'direct', false, 'usgs_histmap',
     '{"openness": {"search_radius_m": 5.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 10.0},
       "min_area_m2": 10,
       "detect": {"surfaces": {"openness_pos": "high", "slrm": "high"},
                  "threshold_pctile": 95, "min_cells": 20, "feature_radius_m": 5.0}}',
     'Stops at property lines by construction; that regularity is the identifier, '
     'unlike conservation terracing which follows contour with machine precision.')

ON CONFLICT (class_id) DO UPDATE SET
    period             = EXCLUDED.period,
    morphology         = EXCLUDED.morphology,
    grid               = EXCLUDED.grid,
    detectability      = EXCLUDED.detectability,
    burial_sensitivity = EXCLUDED.burial_sensitivity,
    label_source       = EXCLUDED.label_source,
    params             = EXCLUDED.params,
    notes              = EXCLUDED.notes;

-- Review notes travel with the point (added 2026-09-05 with the first human review).
ALTER TABLE ref.control_sites ADD COLUMN IF NOT EXISTS review_note text;

-- ---------------------------------------------------------------------------
-- Shape gates, added 2026-09-06 after the amplitude-only rule was falsified by
-- its own negative control (94-100% background fire; ROADMAP A2). Gates come
-- from each class's morphology column, never from tuning against controls:
-- max_cells bounds the plausible footprint, elongation separates compact
-- anomalies from the background's linear texture (gullies, roadbeds), and
-- iron_works' pair block encodes pit-plus-spoil (a sinkhole has no spoil).
-- Full detect blocks: jsonb || merges shallow, so each is restated whole.
-- ---------------------------------------------------------------------------
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_pos": "high", "openness_neg": "high", "slrm": "high"}, "threshold_pctile": 95, "min_cells": 200, "feature_radius_m": 40.0, "max_cells": 40000, "max_elongation": 3.0}}' WHERE class_id = 'mound_earthwork';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 40, "feature_radius_m": 10.0, "max_cells": 8000, "max_elongation": 6.0}}' WHERE class_id = 'rockshelter';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "openness_pos": "high"}, "threshold_pctile": 95, "min_cells": 12, "feature_radius_m": 5.0, "max_cells": 2000, "max_elongation": 3.0}}' WHERE class_id = 'chert_quarry';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high"}, "threshold_pctile": 95, "min_cells": 20, "feature_radius_m": 5.0, "max_cells": 2000, "max_elongation": 3.0}}' WHERE class_id = 'cave_entrance';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"slrm": "high", "openness_pos": "high"}, "threshold_pctile": 95, "min_cells": 50, "feature_radius_m": 7.0, "max_cells": 1200, "max_elongation": 2.0}}' WHERE class_id = 'charcoal_hearth';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_pos": "high", "openness_neg": "high"}, "threshold_pctile": 95, "min_cells": 30, "feature_radius_m": 5.0, "max_cells": 8000, "max_elongation": 3.0, "pair": {"surfaces": ["openness_neg", "openness_pos"], "max_gap_m": 30.0}}}' WHERE class_id = 'iron_works';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 8, "feature_radius_m": 10.0, "max_cells": 4000, "min_elongation": 2.5}}' WHERE class_id = 'mill_seat';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 24, "feature_radius_m": 5.0, "max_cells": 2000, "max_elongation": 3.0}}' WHERE class_id = 'homestead';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 24, "feature_radius_m": 5.0, "max_cells": 2000, "max_elongation": 3.0}}' WHERE class_id = 'civic_structure';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 8, "feature_radius_m": 10.0, "max_cells": 10000, "max_elongation": 2.5}}' WHERE class_id = 'family_cemetery';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high"}, "threshold_pctile": 95, "min_cells": 40, "feature_radius_m": 10.0, "min_elongation": 3.0}}' WHERE class_id = 'road_trace';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high"}, "threshold_pctile": 95, "min_cells": 20, "feature_radius_m": 5.0, "max_cells": 2000, "max_elongation": 3.0}}' WHERE class_id = 'saltpeter_works';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_pos": "high", "slrm": "high"}, "threshold_pctile": 95, "min_cells": 20, "feature_radius_m": 5.0, "min_elongation": 3.0}}' WHERE class_id = 'field_boundary';

-- Relational rules round 2, 2026-09-06: multi-element for cemeteries (rows of small
-- regular depressions — the catalog's own identifier; a tree-throw carpet is Poisson
-- in position so its NN-spacing CV sits near 1, graves in rows near constant), and a
-- PCA-oriented-bounding-box fill gate for structures (nature rarely makes clean
-- rectangles at 4 m). Later UPDATE wins over the earlier block above; restated whole.
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high"}, "threshold_pctile": 95, "min_cells": 8, "feature_radius_m": 10.0, "multi": {"surface": "openness_neg", "min_elements": 4, "element_min_cells": 4, "element_max_cells": 80, "element_max_elongation": 4.0, "nn_max_m": 8.0, "nn_cv_max": 0.6}}}' WHERE class_id = 'family_cemetery';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 24, "feature_radius_m": 5.0, "max_cells": 2000, "max_elongation": 3.0, "min_fill_ratio": 0.55}}' WHERE class_id = 'homestead';
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 24, "feature_radius_m": 5.0, "max_cells": 2000, "max_elongation": 3.0, "min_fill_ratio": 0.55}}' WHERE class_id = 'civic_structure';

-- Cemetery rule v3, 2026-09-08: the ENCLOSURE rule, specified by the owner's review
-- (three cemeteries whose plot outline is visible in the LiDAR panels while the
-- grave-scale multi-element rule scored 0/8). A fence line, wall or ditch around a
-- plot CLOSES; a gully, roadbed or tree-throw scatter does not — binary_fill_holes
-- measures that directly. Drops the `multi` block (jsonb || replaces the whole
-- detect object), gates on enclosure_ratio and plot-scale span instead.
UPDATE ref.target_class SET params = params || '{"detect": {"surfaces": {"openness_neg": "high", "slrm": "low"}, "threshold_pctile": 95, "min_cells": 20, "feature_radius_m": 10.0, "max_cells": 10000, "min_enclosure_ratio": 1.2, "span_cells_range": [20, 140]}}' WHERE class_id = 'family_cemetery';

-- ---------------------------------------------------------------------------
-- Context classes, added 2026-09-08. A landform that is NOT an archaeological
-- target but whose presence is evidence for one: the invisible class (midden,
-- open_habitation) cannot be detected, but the visible ground it sits beside can.
-- Owner observation that motivated it: a midden near Hidden Lake sat on a dry
-- gravel channel littered with worked material - the flakes are far below any
-- LiDAR grid, but the channel is squarely detectable, and gravel bars here carry
-- chert, so the same landform argues for both camp and raw material.
-- Recorded design note: if context classes multiply, they want their own table
-- or a `role` column rather than crowding ref.target_class.
-- ---------------------------------------------------------------------------
INSERT INTO ref.target_class
    (class_id, period, morphology, grid, detectability, burial_sensitivity,
     label_source, params, notes)
VALUES
    ('relict_channel', 'either',
     'Abandoned or seasonally dry channel: linear concave trace, 5-40 m wide, on a floodplain or terrace surface',
     'detection', 'direct', false, 'none_yet',
     '{"openness": {"search_radius_m": 15.0, "num_directions": 16},
       "slrm": {"smoothing_radius_m": 15.0},
       "min_area_m2": 200,
       "detect": {"surfaces": {"openness_neg": "high", "slrm": "low"},
                  "threshold_pctile": 95, "min_cells": 60,
                  "feature_radius_m": 15.0, "min_elongation": 3.0}}',
     'CONTEXT CLASS, not a target: detected as evidence for proxy classes that '
     'cannot be detected directly. A dry gravel channel is both a camp-adjacent '
     'landform and (in Middle TN) a chert source, so it argues for midden and '
     'open_habitation on two independent grounds. Promotion of dist_to_relict_'
     'channel_m to a scored feature requires the usual B2 ablation bar.')
ON CONFLICT (class_id) DO UPDATE SET
    morphology = EXCLUDED.morphology, params = EXCLUDED.params, notes = EXCLUDED.notes;

-- Declared context associations (co-occurrence stacking, 2026-09-08). Each is a
-- LINE OF EVIDENCE for a class that cannot be detected directly, with the distance
-- over which the association is argued and the reason it is claimed. Independence
-- between them is measured at run time, never assumed: layers that restate each
-- other collapse toward one effective layer. dist_to_road is absent by invariant.
UPDATE ref.target_class SET params = params || '{"context": [
  {"source": "relict_channel", "kind": "class", "max_dist_m": 200,
   "rationale": "owner observation at Hidden Lake: midden on a dry gravel channel; channel-adjacent terrace is the camp surface"},
  {"source": "dist_to_confluence_m", "kind": "feature", "max_dist_m": 500,
   "rationale": "resource-edge overlap plus travel-network position (Smith 1978); causal weighting interpretive"},
  {"source": "dist_to_stream_m", "kind": "feature", "max_dist_m": 300,
   "rationale": "water access; EXPECTED to correlate with the channel layer - the redundancy check should show it"},
  {"source": "dist_to_chert_outcrop_m", "kind": "feature", "max_dist_m": 2000,
   "rationale": "C4, NOT BUILT: the first genuinely independent line of evidence. Declared so the stack reports it as missing rather than silently omitting it"}
]}' WHERE class_id = 'midden';
