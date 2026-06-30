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
