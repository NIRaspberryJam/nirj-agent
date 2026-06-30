from nirj_agent.manifests import AptManifest, Manifest
from nirj_agent.services.reconciliation import build_package_plan


def manifest(*packages: str, enforce: bool = True) -> Manifest:
    return Manifest(
        schema=1,
        apt=AptManifest(enforce=enforce, packages=packages),
        overlay_enabled=False,
        background_enabled=False,
    )


def test_build_package_plan_classifies_packages() -> None:
    plan = build_package_plan(
        manifest=manifest("git", "python3", "thonny"),
        installed_packages={"git", "python3", "unmanaged"},
        previously_managed_packages={"git", "obsolete"},
    )

    assert plan.desired == ("git", "python3", "thonny")
    assert plan.install == ("thonny",)
    assert plan.remove == ("obsolete",)
    assert plan.unchanged == ("git", "python3")
    assert plan.changes_required is True


def test_unmanaged_installed_packages_are_never_removed() -> None:
    plan = build_package_plan(
        manifest=manifest("git"),
        installed_packages={"git", "curl", "python3"},
        previously_managed_packages={"git"},
    )

    assert plan.remove == ()


def test_enforcement_disabled_prevents_removal() -> None:
    plan = build_package_plan(
        manifest=manifest("git", enforce=False),
        installed_packages={"git", "obsolete"},
        previously_managed_packages={"git", "obsolete"},
    )

    assert plan.remove == ()
    assert plan.changes_required is False


def test_package_plan_is_sorted_and_deduplicated() -> None:
    plan = build_package_plan(
        manifest=manifest("z-package", "a-package", "z-package"),
        installed_packages=set(),
        previously_managed_packages=set(),
    )

    assert plan.desired == ("a-package", "z-package")
    assert plan.install == ("a-package", "z-package")


def test_package_plan_reports_no_changes() -> None:
    plan = build_package_plan(
        manifest=manifest("git"),
        installed_packages={"git"},
        previously_managed_packages={"git"},
    )

    assert plan.install == ()
    assert plan.remove == ()
    assert plan.changes_required is False
