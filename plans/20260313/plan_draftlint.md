# DraftLint Data Architecture and Data Model

This document captures the current implementation so you can port it into RapidDraft with clear module and data boundaries.

## 1) Workflow and Data Architecture (Current Code)

```mermaid
flowchart LR
    A[Input Drawing<br/>PDF/PNG/JPG] --> B[Document Processor<br/>load_drawing]
    B --> C[Preprocess<br/>enhanced + binary]
    C --> D[Layout Analyzer<br/>regions dict]
    D --> E[regions_df<br/>Polars]
    C --> F[OCR Engine<br/>extract_text_with_context]
    D --> F
    F --> G[text_df<br/>Polars]
    C --> H[YOLO Symbol Detector]
    H --> I[symbols_df<br/>Polars]

    J[Standards Rules CSV<br/>data/standards/*.csv] --> K[rules_df]

    C --> L[AI Validator<br/>Azure OpenAI via LangChain]
    D --> L
    I --> L
    L --> M[ai_results<br/>title_block, gdt_callouts, dimensions]

    E --> N[Rule Validation]
    G --> N
    I --> N
    M --> N
    K -.loaded at init.- N
    N --> O[issues: list[ComplianceIssue]]
    O --> P[ValidationReport]
    M --> P

    P --> Q[Report Generator]
    A --> Q
    E --> Q
    G --> Q
    I --> Q

    Q --> R1[Annotated PNG]
    Q --> R2[Report JSON]
    Q --> R3[Report HTML]
    Q --> R4[regions/text/symbols/issues CSV]
```

## 2) Detailed Step Sequence

1. Load drawing from PDF/image.
2. Preprocess image (`enhanced`, `binary`).
3. Detect layout regions (`title_block`, `drawing_views`, etc.).
4. Export regions to `regions_df`.
5. OCR each region and create `text_df`.
6. Detect GD&T symbols and create `symbols_df`.
7. AI validation (optional flag, but validator init expects Azure config).
8. Build issues from AI outputs in `_run_rule_validation`.
9. Create `ValidationReport` with severity buckets and summary.
10. Persist outputs (JSON/HTML/CSV/annotated image).

## 3) Data Model Diagram (Canonical Porting Model)

```mermaid
erDiagram
    DRAWING {
        string drawing_id PK
        string source_path
        string standard_profile
        int width
        int height
        datetime processed_at
    }

    RULE_DEFINITION {
        string rule_id PK
        string standard
        string category
        string description
        string severity
        bool enabled
    }

    REGION {
        string region_id PK
        string drawing_id FK
        string region_type
        float x1
        float y1
        float x2
        float y2
        float width
        float height
        float area
        string block_type
    }

    TEXT_ELEMENT {
        string text_id PK
        string drawing_id FK
        string region_id FK
        string text
        float confidence
        float local_x1
        float local_y1
        float local_x2
        float local_y2
        float global_x1
        float global_y1
        float global_x2
        float global_y2
    }

    DETECTED_SYMBOL {
        string symbol_id PK
        string drawing_id FK
        string symbol_type
        float confidence
        float x1
        float y1
        float x2
        float y2
        float center_x
        float center_y
        float width
        float height
    }

    AI_TITLE_BLOCK_RESULT {
        string drawing_id PK
        bool has_drawing_number
        bool has_title
        bool has_scale
        bool has_projection_method
        bool has_date
        bool has_author
        string missing_fields_json
        float confidence
    }

    AI_GDT_RESULT {
        string gdt_result_id PK
        string drawing_id FK
        string symbol_id FK
        bool is_compliant
        string issues_json
        string datum_references_json
        string tolerance_value
        string modifiers_json
        float confidence
        float x1
        float y1
        float x2
        float y2
    }

    AI_DIMENSION_RESULT {
        string dimension_result_id PK
        string drawing_id FK
        string region_id FK
        bool has_duplicates
        bool lines_crossing
        bool proper_arrowheads
        bool text_orientation_ok
        string issues_json
        float confidence
    }

    COMPLIANCE_ISSUE {
        string issue_id PK
        string drawing_id FK
        string rule_id FK
        string standard
        string category
        string severity
        string description
        json details
        float x1
        float y1
        float x2
        float y2
    }

    VALIDATION_REPORT {
        string report_id PK
        string drawing_id FK
        string standard
        bool compliant
        int total_issues
        int total_critical
        int total_major
        int total_minor
        bool overall_compliant
        json ai_analysis
        datetime validation_date
    }

    DRAWING ||--o{ REGION : contains
    DRAWING ||--o{ TEXT_ELEMENT : extracts
    DRAWING ||--o{ DETECTED_SYMBOL : detects
    DRAWING ||--|| AI_TITLE_BLOCK_RESULT : validates
    DRAWING ||--o{ AI_GDT_RESULT : validates
    DRAWING ||--o{ AI_DIMENSION_RESULT : validates
    DRAWING ||--o{ COMPLIANCE_ISSUE : yields
    DRAWING ||--|| VALIDATION_REPORT : summarized_by
    REGION ||--o{ TEXT_ELEMENT : scoped_by
    REGION ||--o{ AI_DIMENSION_RESULT : view_slice
    DETECTED_SYMBOL ||--o{ AI_GDT_RESULT : source_symbol
    RULE_DEFINITION ||--o{ COMPLIANCE_ISSUE : triggered_by
```

## 4) RapidDraft Porting Notes

1. Keep three storage layers:
   - Raw assets: original and cropped images.
   - Feature tables: `regions`, `text_elements`, `detected_symbols`, AI result tables.
   - Decision layer: `compliance_issues`, `validation_report`.
2. Use `drawing_id` as the primary join key across all tables.
3. Keep `rule_id` explicit in every emitted issue so standards updates do not break historical reports.
4. Persist both model confidence and coordinates for auditability and UI trace-back.

## 5) Current Implementation Reality (Important)

1. `rules_df` is loaded at startup but not used directly in issue generation logic.
2. `_run_rule_validation` currently derives issues from `ai_results` only.
3. `compliant`/`overall_compliant` is `len(critical)==0`, so major issues can still return compliant.
4. `rule_validator.py`, `api/routes.py`, `src/models/standards.py`, and `src/utils/image_utils.py` are placeholders (empty files).
5. Azure settings are required by config fields even though docs describe AI as optional.
