from dataclasses import dataclass

from nirj_agent.manifests import Manifest


@dataclass(frozen=True)
class PackagePlan:
    desired: tuple[str, ...]
    install: tuple[str, ...]
    remove: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def changes_required(self) -> bool:
        return bool(self.install or self.remove)


@dataclass(frozen=True)
class PythonPackagePlan:
    desired: tuple[tuple[str, str], ...]
    install: tuple[str, ...]
    remove: tuple[str, ...]
    unchanged: tuple[tuple[str, str], ...]

    @property
    def changes_required(self) -> bool:
        return bool(self.install or self.remove)


@dataclass(frozen=True)
class ReconciliationPlan:
    apt: PackagePlan
    python: PythonPackagePlan

    @property
    def changes_required(self) -> bool:
        return self.apt.changes_required or self.python.changes_required


def build_package_plan(
    manifest: Manifest,
    installed_packages: set[str],
    previously_managed_packages: set[str],
) -> PackagePlan:
    desired = set(manifest.apt.packages)
    install = desired - installed_packages
    unchanged = desired & installed_packages
    remove = (
        previously_managed_packages - desired
        if manifest.apt.enforce
        else set()
    )

    return PackagePlan(
        desired=tuple(sorted(desired)),
        install=tuple(sorted(install)),
        remove=tuple(sorted(remove)),
        unchanged=tuple(sorted(unchanged)),
    )


def build_python_package_plan(
    manifest: Manifest,
    installed_packages: dict[str, str],
    previously_managed_packages: set[str],
) -> PythonPackagePlan:
    desired = dict(manifest.python.packages)

    install = tuple(
        f"{name}=={version}"
        for name, version in sorted(desired.items())
        if installed_packages.get(name) != version
    )

    unchanged = tuple(
        (name, version)
        for name, version in sorted(desired.items())
        if installed_packages.get(name) == version
    )

    remove = tuple(sorted(previously_managed_packages - desired.keys()))

    return PythonPackagePlan(
        desired=tuple(sorted(desired.items())),
        install=install,
        remove=remove,
        unchanged=unchanged,
    )
