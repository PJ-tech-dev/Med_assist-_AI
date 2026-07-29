# Module 7 Test Development - TODO

## Progress Tracking

### A. ReportParser — New detect_report_type variants (6 tests)
- [x] test_detect_kft
- [x] test_detect_lipid_profile
- [x] test_detect_blood_sugar
- [x] test_detect_hba1c
- [x] test_detect_vitamin_d
- [x] test_detect_vitamin_b12

### B. ReportParser — Malformed text (1 test)
- [x] test_detect_garbage_text_returns_unknown

### C. ReportParser — clean_report_text edge case (1 test)
- [x] test_clean_empty_string

### D. ReportParser — extract_numeric_values_regex edge case (1 test)
- [x] test_extract_values_with_reference_brackets

### E. OCRProcessor — BaseOCRProcessor (1 test)
- [x] test_base_ocr_processor_cannot_instantiate

### F. DefaultOCRProcessor — Scanned PDF fallback (1 test)
- [x] test_ocr_pdf_text_layer_empty_fallback_to_image

### G. DefaultOCRProcessor — Additional image formats (2 tests)
- [x] test_ocr_image_jpeg_extracted
- [x] test_ocr_image_tiff_extracted

### H. DefaultOCRProcessor — Empty/invalid (2 tests)
- [x] test_ocr_empty_bytes_returns_empty
- [x] test_ocr_corrupted_pdf_returns_error_engine

### Verification
- [x] Run tests to confirm all pass without modifying production code

