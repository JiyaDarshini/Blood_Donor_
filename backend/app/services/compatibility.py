"""
Blood Group Compatibility Service for Red Blood Cell (RBC) Transfusions.

Standard ABO/Rh compatibility rules:
- Recipient A+  : A+, A-, O+, O-
- Recipient A-  : A-, O-
- Recipient B+  : B+, B-, O+, O-
- Recipient B-  : B-, O-
- Recipient AB+ : All eight listed ABO/Rh groups (AB+, AB-, A+, A-, B+, B-, O+, O-)
- Recipient AB- : AB-, A-, B-, O-
- Recipient O+  : O+, O-
- Recipient O-  : O- (Universal Donor)

Note: For this application, this service acts as an initial matching filter.
Actual compatibility, donor eligibility, component type, and transfusion decisions
must always be confirmed by qualified healthcare professionals.
"""

from typing import List, Set

COMPATIBILITY_RULES: dict[str, Set[str]] = {
    "A+": {"A+", "A-", "O+", "O-"},
    "A-": {"A-", "O-"},
    "B+": {"B+", "B-", "O+", "O-"},
    "B-": {"B-", "O-"},
    "AB+": {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"},
    "AB-": {"AB-", "A-", "B-", "O-"},
    "O+": {"O+", "O-"},
    "O-": {"O-"},
}


def get_compatible_donor_groups(recipient_group: str) -> List[str]:
    """Return a list of compatible donor blood groups for a given recipient."""
    cleaned = recipient_group.strip().upper()
    compatible_set = COMPATIBILITY_RULES.get(cleaned)
    if compatible_set is None:
        raise ValueError(f"Unknown recipient blood group: {recipient_group}")
    return sorted(list(compatible_set))


def is_compatible(recipient_group: str, donor_group: str) -> bool:
    """Return True if donor blood group is compatible for red blood cell transfusion to recipient."""
    cleaned_rec = recipient_group.strip().upper()
    cleaned_don = donor_group.strip().upper()
    compatible_set = COMPATIBILITY_RULES.get(cleaned_rec)
    if compatible_set is None:
        return False
    return cleaned_don in compatible_set
