import pytest
from sqlalchemy.orm import configure_mappers

from app.models import Household, HouseholdMembership, User


def test_email_normalization_on_assignment():
    user = User(email=" Alex@Example.COM ")
    assert user.email == "alex@example.com"
    user.email = " BLAIR@Example.COM "
    assert user.email == "blair@example.com"


def test_empty_email_rejected():
    with pytest.raises(ValueError, match="email cannot be empty"):
        User(email="   ")


def test_relationship_mapping_without_database():
    configure_mappers()
    user = User(email="alex@example.com")
    household = Household(name="Home")
    membership = HouseholdMembership(user=user, household=household)
    assert user.memberships == [membership]
    assert household.memberships == [membership]
    assert "password" not in User.__table__.columns
