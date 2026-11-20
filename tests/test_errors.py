from kv.coordinator.errors import ApiError

ERROR_CODE = "bad_gateway"
SHARD_ID = "s1"


def test_api_error_body_includes_detail_and_extra_fields():
    err = ApiError(502, ERROR_CODE, "down", shard=SHARD_ID)
    assert err.body == {"error": ERROR_CODE, "detail": "down", "shard": SHARD_ID}
    assert ApiError(404, "not_found").body == {"error": "not_found"}
