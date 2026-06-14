def test_user_model_columns():
    from backend.models.user import User
    assert User.__tablename__ == "users"
    assert hasattr(User, "id")
    assert hasattr(User, "authentik_username")
    assert hasattr(User, "is_admin")
    assert hasattr(User, "created_at")
