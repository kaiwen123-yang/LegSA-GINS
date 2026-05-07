"""SOURCE_MANIFEST helpers for dataset provenance boundaries.

中文说明：manifest 模块记录 claim boundary 和输出合同，禁止把 dry-run 或 baseline parser 写成数值性能证据。
"""


SOURCE_MANIFEST_REQUIRED_FIELDS = [
    "dataset_name",
    "time_bases",
    "sensors",
    "frames",
    "extrinsics",
    "reference",
    "raw_data_policy",
]

RAW_DATA_POLICY_REQUIRED_FIELDS = [
    "raw_data_committed",
    "large_files_committed",
    "external_data_required",
]


def default_source_manifest(dataset_name: str) -> dict:
    return {
        "dataset_name": dataset_name,
        "time_bases": [],
        "sensors": [],
        "frames": [],
        "extrinsics": {},
        "reference": {},
        "raw_data_policy": {
            "raw_data_committed": False,
            "large_files_committed": False,
            "external_data_required": True,
        },
    }


def validate_source_manifest(manifest: dict) -> bool:
    missing = [
        field for field in SOURCE_MANIFEST_REQUIRED_FIELDS if field not in manifest
    ]
    if missing:
        raise ValueError(f"SOURCE_MANIFEST missing required fields: {missing}")

    raw_data_policy = manifest.get("raw_data_policy")
    if not isinstance(raw_data_policy, dict):
        raise ValueError("SOURCE_MANIFEST raw_data_policy must be a dict.")

    policy_missing = [
        field
        for field in RAW_DATA_POLICY_REQUIRED_FIELDS
        if field not in raw_data_policy
    ]
    if policy_missing:
        raise ValueError(
            f"SOURCE_MANIFEST raw_data_policy missing fields: {policy_missing}"
        )

    return True
