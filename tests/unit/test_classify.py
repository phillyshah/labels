"""Unit tests for document-type validation against the WI052 templates."""

from processor.classify import classify_documents, describe

# Minimal synthetic text carrying each template's distinctive markers.
BATCH = ("Certificate of Compliance  Certificate No 2603000843  Shipped to Maxx Orthopedics  "
         "Address 2460 General Armistead Ave  Quantity shipped 38  Drawing Revision RD  "
         "FIR Report No FI2603843  Customer PO 2000003839  Description TIBIAL BASE 4 METALBACKED")
STERILE_COC = ("CERTIFICATE OF COMPLIANCE  Customer P/N MTUUX400-K  Batch/Lot V11022719  "
               "Mfg. Date 2026-03-01  Exp. Date 2031-02-28  Description TIBIAL BASE 4 METALBACKED  "
               "Lot M26-179  Sr No Customer Quantity 38 line items follow for the sterile lot")
SLR = ("Sterile Lot Record  Form 1023-2  Sterile Lot Number M26-179  Contract Sterilizer ISL  "
       "Chamber C  B.l Lot Number BAD-026  Revision 03  Effective Date 24 Aug 2023  "
       "MTUUX400-K Tibial Base Plate Size 4 quantities released for this sterile batch")
LABEL = ""  # image-only


def test_correct_slots_are_clean():
    issues = classify_documents({
        "label_form": LABEL, "batch_coc": BATCH,
        "sterile_coc": STERILE_COC, "sterile_lot_record": SLR,
    })
    assert issues == []


def test_swapped_cocs_are_flagged():
    issues = classify_documents({
        "batch_coc": STERILE_COC, "sterile_coc": BATCH,
        "sterile_lot_record": SLR,
    })
    slots = {i["slot"] for i in issues}
    assert "batch_coc" in slots and "sterile_coc" in slots
    assert "Sterile Certificate" in describe(issues)


def test_paper_form_in_label_slot_is_flagged():
    issues = classify_documents({"label_form": BATCH})
    assert any(i["slot"] == "label_form" for i in issues)


def test_image_only_in_text_slot_is_flagged():
    issues = classify_documents({"batch_coc": LABEL})
    assert any(i["slot"] == "batch_coc" for i in issues)


def test_label_slot_image_only_is_clean():
    assert classify_documents({"label_form": LABEL}) == []
