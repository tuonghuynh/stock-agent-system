from stock_agent.release import load_release_manifest


def test_release_manifest_versions_all_changeable_boundaries() -> None:
    manifest = load_release_manifest("release-manifest.yaml")
    assert manifest.release_version == "release-v1"
    assert manifest.workflow_version == "workflow-v1"
    assert manifest.schema_version == "contracts-v1"
    assert set(manifest.prompt_versions) == {"research", "critic", "portfolio", "single_agent"}
