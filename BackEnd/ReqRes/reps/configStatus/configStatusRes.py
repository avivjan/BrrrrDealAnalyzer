"""GET /reps/config-status

No `response_model` is registered for this route; it returns a plain dict.
Shape, for documentation only:

{"configured": True, "sheet_tab", "bucket_name", "base_prefix", "min_description_length"}
or, on RepsConfigError: {"configured": False, "detail", "min_description_length"}
"""
