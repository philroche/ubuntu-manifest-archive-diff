#!/usr/bin/env python3
"""Console script for ubuntu_manifest_archive_diff."""
import faulthandler
import logging
import sys
import click
import requests

from debian import debian_support
from launchpadlib.launchpad import Launchpad
from launchpadlib.uris import service_roots

# Which archive pockets are checked
ARCHIVE_POCKETS = ["Updates", "Security", "Release"]
SNAP_REFRESH_URL = "https://api.snapcraft.io/v2/snaps/refresh"

faulthandler.enable()


def _get_snapstore_versions(snap_package_names, architecture):
    """
    Get the current versions of all snaps contained in snap_dict as available
    on the snap store.

    The arch parameter is a string indicating the Debian architecture (amd64,
    armhf, ...). The snap_dict is a dictionary mapping snap names to tuples
    of the form (channel, version).

    Returns a dictionary mapping snap names to tuples of the form (channel,
    version), where version corresponds to the snap's version available in the
    snap store.
    """
    manifest_snapstore_versions = []

    # Only iterate over the snaps in snap_dict if snap_dict is not None.
    # snap_dict can be None in the case where a manifest for the given arch
    # does not exist due to that suite not supporting that arch or that
    # this is the first build for a suite.

    for (snap_name, snap_channel) in snap_package_names:
        data = {
            'context': [],
            'actions': [
                {
                    'action': 'download',
                    'instance-key': '0',
                    'name': snap_name,
                    'channel': snap_channel,
                }
            ]
        }
        headers = {
            'Snap-Device-Series': '16',
            'Snap-Device-Architecture': architecture,
            'Content-Type': 'application/json',
        }

        response = requests.post(SNAP_REFRESH_URL,
                                 headers=headers,
                                 json=data)
        if not response.ok:
            print("Failed to get info on snap '%s', in channel "
                        "'%s', for arch '%s'" % (snap_name, snap_channel, architecture))
            continue

        # The response looks like this:
        # {
        #     'error-list': [],
        #     'results': [
        #         {
        #             'effective-channel': 'stable',
        #             'instance-key': '0',
        #             'name': 'core',
        #             'released-at': '2018-12-18T15:16:56.723501',
        #             'result': 'download',
        #             'snap': {
        #                 'created-at': '2018-12-14T10:56:30.622674+00:00',
        #                 'download': {
        #                     'deltas': [],
        #                     'sha3-384': 'a6e9...0150',
        #                     'size': 93835264,
        #                     'url': 'https://api.snapcraft.io/...'
        #                 },
        #                 'license': 'Other Open Source',
        #                 'name': 'core',
        #                 'prices': {},
        #                 'publisher': {
        #                     'display-name': 'Canonical',
        #                     'id': 'canonical',
        #                     'username': 'canonical',
        #                     'validation': 'verified'
        #                 },
        #                 'revision': 6130,
        #                 'snap-id': '99T7MUlRhtI3U0QFgl5mXXESAiSwt776',
        #                 'summary': 'snapd runtime environment',
        #                 'title': 'core',
        #                 'type': 'os',
        #                 'version': '16-2.36.3'
        #             },
        #             'snap-id': '99T7MUlRhtI3U0QFgl5mXXESAiSwt776'
        #         }
        #     ]
        # }
        snap_info = response.json()['results'][0]['snap']

        # Use the same format we used for the manifest output.
        manifest_snapstore_versions.append((snap_name, snap_channel, snap_info['revision']))

    return manifest_snapstore_versions


def _get_binary_packages(archive, binary_package_name, lp_arch_series, pocket, status="Published"):
    binaries = archive.getPublishedBinaries(
        exact_match=True,
        binary_name=binary_package_name,
        distro_arch_series=lp_arch_series,
        pocket=pocket,
        order_by_date=True,
        status=status,
    )
    return binaries


def get_archive_versions(series, binary_package_names=[], architecture="amd64", ppas=[], lp_user=None):
    if lp_user:
        launchpad = Launchpad.login_with(
            lp_user,
            service_root=service_roots['production'], version='devel')
    else:
        # Log in to launchpad annonymously - we use launchpad to find
        # the package publish time
        launchpad = Launchpad.login_anonymously(
            'ubuntu-manifest-archive-diff',
            service_root=service_roots['production'], version='devel')

    ubuntu = launchpad.distributions["ubuntu"]
    lp_series = ubuntu.getSeries(name_or_version=series)
    lp_arch_series = lp_series.getDistroArchSeries(archtag=architecture)
    manifest_archive_versions = []
    for binary_package_name in binary_package_names:
        # ensure that the architecture is stripped from the package name
        binary_package_name = binary_package_name.replace(f':{architecture}', '')
        binary_package_versions_found_in_archive = []
        if ppas:
            for ppa in ppas:
                ppa_owner, ppa_name = ppa.split('/')
                archive = launchpad.people[ppa_owner].getPPAByName(name=ppa_name)
                print(f'using pocket "Release" when using a PPA {ppa} ...')
                pocket = 'Release'

                ppa_binaries = _get_binary_packages(archive,
                                                binary_package_name,
                                                lp_arch_series,
                                                pocket, )
                for ppa_binary in ppa_binaries:
                    print(
                        f'Found {ppa_binary.status} {ppa_binary.binary_package_name} version {ppa_binary.binary_package_version} in {ppa} ppa.')
                    binary_package_versions_found_in_archive.append(ppa_binary.binary_package_version)

        for pocket in ARCHIVE_POCKETS:
            archive = ubuntu.main_archive

            archive_binaries = _get_binary_packages(archive,
                                                    binary_package_name,
                                                    lp_arch_series,
                                                    pocket,)
            if len(archive_binaries):
                # there were published binaries with this name.
                # now get the source package name so we can get the changelog
                for archive_binary in archive_binaries:
                    print(
                        f'Found {archive_binary.status}  {archive_binary.binary_package_name} version {archive_binary.binary_package_version} in {archive_binary.pocket} pocket of the archive')
                    binary_package_versions_found_in_archive.append(archive_binary.binary_package_version)
        # find the max debian package version from the binary_package_versions_found_in_archive list
        # and add to manifest_archive_versions
        max_version = "0.0.0"
        for binary_package_version_found_in_archive in binary_package_versions_found_in_archive:
            if debian_support.version_compare(binary_package_version_found_in_archive, max_version) > 0:
                max_version = binary_package_version_found_in_archive
        manifest_archive_versions.append((binary_package_name, max_version))
        print(f"Max version of package {binary_package_name} found in archive is {max_version}")
    return manifest_archive_versions

@click.command()
@click.option(
    "--series",
    help="The Ubuntu series eg. '20.04' or 'focal'.",
    required=True,
)
@click.option(
    "--manifest-filename",
    "manifest",
    help="Package version manifest to compare against the archive",
    type=click.File("r"),
    required=True,
)
@click.option(
    "--logging-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    required=False,
    default="ERROR",
    help="How detailed would you like the output.",
    show_default=True
)
@click.option(
    "--architecture",
    help="The architecture to use when querying package "
    "versions in the archive. We use this in our Launchpad "
    'query to query either "source" package or "amd64" package '
    'version. Using "amd64" will query the version of the '
    'binary package. "source" is a valid value for '
    "architecture with Launchpad and will query the version of "
    "the source package. The default is amd64. ",
    required=True,
    default="amd64",
    show_default=True
)
@click.option(
    "--ppa",
    "ppas",
    required=False,
    multiple=True,
    type=click.STRING,
    help="Additional PPAs that you wish to query for package version status."
    "Expected format is "
    "ppa:'%LAUNCHPAD_USERNAME%/%PPA_NAME%' eg. ppa:philroche/cloud-init"
    "Multiple --ppa options can be specified",
    default=[]
)
@click.option(
    "--launchpad-user",
    "lp_user",
    required=False,
    type=click.STRING,
    help="Launchpad username to use when querying PPAs. This is important id "
         "you are querying PPAs that are not public.",
    default=None
)
@click.option(
    "--archive-manifest-filename",
    required=True,
    type=click.STRING,
    help="Filename to write the archivr versions to",
    default=None
)
@click.pass_context
def ubuntu_manifest_archive_diff(
    ctx, series, manifest, logging_level, architecture, ppas, lp_user, archive_manifest_filename
):
    """
    Compare a package manifest to the versions of the packages currently in the Ubuntu archive.
    """

    # We log to stderr so that a shell calling this will not have logging
    # output in the $() capture.
    level = logging.getLevelName(logging_level)
    logging.basicConfig(
        level=level, stream=sys.stderr, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    binary_package_names = []
    snap_package_names = []
    for line in manifest:
        if "snap:" in line:
            snap_package_name, snap_package_channel, snap_package_version = line.strip().split()
            snap_package_name = snap_package_name.replace("snap:", "")
            snap_package_names.append((snap_package_name, snap_package_channel))
        else:
            binary_package_name, package_version = line.strip().split()
            binary_package_names.append(binary_package_name)

    manifest_archive_versions = get_archive_versions(series, binary_package_names, architecture, list(ppas), lp_user)
    manifest_snapstore_versions = _get_snapstore_versions(snap_package_names, architecture)
    # write the manifest_archive_versions to a file
    with open(archive_manifest_filename, 'w') as archive_manifest_file:
        for binary_package_name, binary_package_version in manifest_archive_versions:
            archive_manifest_file.write(f'{binary_package_name}\t{binary_package_version}\n')
        for snap_name, snap_channel, snap_revision in manifest_snapstore_versions:
            archive_manifest_file.write(f'snap:{snap_name}\t{snap_channel}\t{snap_revision}\n')
    print(f"Manifest written to {archive_manifest_filename}.")


if __name__ == "__main__":
    ubuntu_manifest_archive_diff(obj={})
