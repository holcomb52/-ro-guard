# Stellantis OEM Warranty Audit — RO Guard Integration

RO Guard applies the **Stellantis North America Dealer Audit — Warranty Audit Reason Code Application Guide** as configurable **hard stops** and **warnings** on every review.

## Where it lives

| Location | Purpose |
|----------|---------|
| **Review tab** | Stellantis OEM audit section — customer signature (S) and optional mileage (X) |
| **Admin → Audit Rules** | Enable/disable each rule; set Hard Stop vs Warning |
| **Admin → Audit Rules → expander** | Full reason code reference (A–X) |
| **`core/stellantis_audit.py`** | Reason code catalog, rule mapping, detection logic |
| **OEM Audit Guide tab** | Upload updated Stellantis PDF guides; active upload drives reason codes + B-keyword checks |

## Uploading an updated guide

1. Open **OEM Audit Guide** in the top navigation.
2. Upload the new Stellantis warranty audit PDF (scanned PDFs use OCR automatically).
3. Leave **Set as active guide after upload** checked.
4. RO Guard parses reason codes and B-subcode keyword checks from the document.

If Supabase was created before this feature, run the `stellantis_audit_documents` block in `docs/SUPABASE_SCHEMA.sql` once.

## Stellantis reason codes

| Code | Title | RO Guard rules |
|------|-------|----------------|
| **A** | Parts Unavailable (Short Parts) | Parts warranty — MOPAR |
| **B** | Non-Warranty Item | Stellantis B — narrative keyword scan |
| **C** | Labor Not Supported | Tech time |
| **D** | Duplications / Comebacks | *(manual / future)* |
| **E** | Add-On Operations | W+ add-on |
| **F** | New Vehicle Prep | *(manual / future)* |
| **G** | Labor Op Unsupported | *(manual / future)* |
| **H** | Labor Repair Efficiency | Tech time |
| **I** | Claim Alteration | *(post-submit)* |
| **J** | Unsupported Sublet | Sublet documentation |
| **K** | Required Specs Not Recorded | Battery, A/C EVAC, alignment, oil dye |
| **L** | Management Authorization | Rental, W+, zero-mile paint |
| **M** | Tech Notes (Pencil Wrench) | Narrative + cause/correction quality |
| **N** | Missing Claims | *(post-audit)* |
| **O** | Overcharges | *(future)* |
| **P** | Unsupported Mopar Claims | Parts warranty — MOPAR |
| **Q** | Invalid Coverage | *(manual)* |
| **R** | Related Parts Unavailable | Parts warranty — MOPAR |
| **S** | Customer Signature Missing | Customer RO signature checkbox |
| **T** | Diagnostic Operation | Diagnostic op / DTC support |
| **X** | Zero Mile Paint/Trim | Paint/trim at low mileage without manager sign-off |

## Hard stops vs warnings

Default severity is **Hard Stop** for all Stellantis-specific rules:

- `stellantis_customer_signature` (S)
- `stellantis_non_warranty_item` (B)
- `stellantis_diagnostic_op` (T)
- `stellantis_zero_mile_paint` (X)

Managers can downgrade any rule to **Warning** under Admin → Audit Rules without turning off the underlying check.

## Review workflow

1. Enter job narrative and check warranty documentation boxes as today.
2. Under **Stellantis OEM audit**, confirm **Customer RO signature on file** when signed.
3. Enter **vehicle mileage** when paint/trim work may trigger code **X** (≤50 miles).
4. Run audit — findings show as `Stellantis S: …` (etc.) on hard stops.
5. **DO NOT SUBMIT** when any enabled hard stop is present.

## Source document

Dealer copy: `WARRANTY AUDIT.pdf` (Stellantis Reason Code Application Guide).  
OCR reference: `docs/stellantis_audit_ocr.txt`
