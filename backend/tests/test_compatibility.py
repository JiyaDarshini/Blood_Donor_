import pytest
from app.services.compatibility import get_compatible_donor_groups, is_compatible, COMPATIBILITY_RULES


def test_compatibility_all_eight_groups():
    """Verify red blood cell transfusion compatibility rules for all 8 blood groups."""
    
    # 1. Recipient A+: Donors A+, A-, O+, O-
    assert set(get_compatible_donor_groups("A+")) == {"A+", "A-", "O+", "O-"}
    assert is_compatible("A+", "A+") is True
    assert is_compatible("A+", "A-") is True
    assert is_compatible("A+", "O+") is True
    assert is_compatible("A+", "O-") is True
    assert is_compatible("A+", "B+") is False
    assert is_compatible("A+", "AB+") is False

    # 2. Recipient A-: Donors A-, O-
    assert set(get_compatible_donor_groups("A-")) == {"A-", "O-"}
    assert is_compatible("A-", "A-") is True
    assert is_compatible("A-", "O-") is True
    assert is_compatible("A-", "A+") is False
    assert is_compatible("A-", "O+") is False

    # 3. Recipient B+: Donors B+, B-, O+, O-
    assert set(get_compatible_donor_groups("B+")) == {"B+", "B-", "O+", "O-"}
    assert is_compatible("B+", "B+") is True
    assert is_compatible("B+", "B-") is True
    assert is_compatible("B+", "O+") is True
    assert is_compatible("B+", "O-") is True
    assert is_compatible("B+", "A+") is False

    # 4. Recipient B-: Donors B-, O-
    assert set(get_compatible_donor_groups("B-")) == {"B-", "O-"}
    assert is_compatible("B-", "B-") is True
    assert is_compatible("B-", "O-") is True
    assert is_compatible("B-", "B+") is False
    assert is_compatible("B-", "O+") is False

    # 5. Recipient AB+: All eight listed ABO/Rh groups (Universal Recipient)
    all_groups = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    assert set(get_compatible_donor_groups("AB+")) == all_groups
    for donor in all_groups:
        assert is_compatible("AB+", donor) is True

    # 6. Recipient AB-: Donors AB-, A-, B-, O-
    assert set(get_compatible_donor_groups("AB-")) == {"AB-", "A-", "B-", "O-"}
    assert is_compatible("AB-", "AB-") is True
    assert is_compatible("AB-", "A-") is True
    assert is_compatible("AB-", "B-") is True
    assert is_compatible("AB-", "O-") is True
    assert is_compatible("AB-", "A+") is False
    assert is_compatible("AB-", "AB+") is False

    # 7. Recipient O+: Donors O+, O-
    assert set(get_compatible_donor_groups("O+")) == {"O+", "O-"}
    assert is_compatible("O+", "O+") is True
    assert is_compatible("O+", "O-") is True
    assert is_compatible("O+", "A+") is False
    assert is_compatible("O+", "B+") is False

    # 8. Recipient O-: Donor O- only (Universal Donor)
    assert set(get_compatible_donor_groups("O-")) == {"O-"}
    assert is_compatible("O-", "O-") is True
    assert is_compatible("O-", "O+") is False
    assert is_compatible("O-", "A-") is False


def test_invalid_blood_group():
    with pytest.raises(ValueError):
        get_compatible_donor_groups("XYZ")
    assert is_compatible("XYZ", "O+") is False
