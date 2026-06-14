def test_user_model_columns():
    from backend.models.user import User
    assert User.__tablename__ == "users"
    assert hasattr(User, "id")
    assert hasattr(User, "authentik_username")
    assert hasattr(User, "is_admin")
    assert hasattr(User, "created_at")


def test_setting_model_has_user_id():
    from backend.models.setting import Setting
    assert hasattr(Setting, "id")
    assert hasattr(Setting, "user_id")
    assert hasattr(Setting, "key")
    assert hasattr(Setting, "value")


def test_owned_models_have_user_id():
    from backend.models.company import Company
    from backend.models.job import Job
    from backend.models.run import Run
    from backend.models.application import ApplicationTracking
    from backend.models.feedback import FeedbackExample
    from backend.models.resume import Resume
    for model in [Company, Job, Run, ApplicationTracking, FeedbackExample, Resume]:
        assert hasattr(model, "user_id"), f"{model.__name__} missing user_id"
