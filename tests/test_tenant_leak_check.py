from scripts.tenant_leak_check import scan_text


def test_tenant_leak_check_rejects_realistic_ocid_and_profile():
    text = (
        "profile = 'cap'\n"
        "id = 'ocid1.compartment.oc1..aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'\n"
    )
    names = {item.rsplit(": ", 1)[-1] for item in scan_text("fixture", text)}
    assert names == {"internal_profile", "literal_ocid"}


def test_placeholders_are_allowed():
    assert not scan_text(
        "fixture",
        "profile = '<OCI_PROFILE>'\nid = '<COMPARTMENT_OCID>'\nregion='<OCI_REGION>'",
    )
