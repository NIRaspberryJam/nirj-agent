from nirj_agent.manifests import (
    AptManifest,
    DesktopManifest,
    Manifest,
    PythonManifest,
)
from nirj_agent.services.reconciliation import (
    build_package_plan,
    build_python_package_plan,
)


def manifest(
    *packages: str,
    enforce: bool = True,
    python_packages: tuple[tuple[str, str], ...] = (),
) -> Manifest:
    return Manifest(
        schema=1,
        apt=AptManifest(enforce=enforce, packages=packages),
        python=PythonManifest(packages=python_packages),
        desktop=DesktopManifest(shortcuts=()),
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

def test_python_plan_installs_missing_and_wrong_versions() -> None:
    plan = build_python_package_plan(
        manifest=manifest(
            python_packages=(
                ("jamkit", "0.2.0"),
                ("requests", "2.32.5"),
            )
        ),
        installed_packages={
            "jamkit": "0.1.0",
            "unmanaged": "1.0",
        },
        previously_managed_packages={"jamkit", "obsolete"},
    )

    assert plan.desired == (
        ("jamkit", "0.2.0"),
        ("requests", "2.32.5"),
    )
    assert plan.install == (
        "jamkit==0.2.0",
        "requests==2.32.5",
    )
    assert plan.remove == ("obsolete",)
    assert plan.unchanged == ()


def test_python_plan_preserves_unmanaged_packages() -> None:
    plan = build_python_package_plan(
        manifest=manifest(
            python_packages=(("jamkit", "0.1.0"),)
        ),
        installed_packages={
            "jamkit": "0.1.0",
            "pip": "25.2",
            "setuptools": "80.0",
        },
        previously_managed_packages={"jamkit"},
    )

    assert plan.install == ()
    assert plan.remove == ()
    assert plan.unchanged == (("jamkit", "0.1.0"),)
    assert plan.changes_required is False
