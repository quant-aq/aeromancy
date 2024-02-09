"""Tool for examining Aeromancy/W&B artifacts.

Run with:

    shell> pdm aeroview <aeromancy URI>

or:

    shell> pdm aeroview <Weights and Biases artifact name>
"""
import subprocess
from pathlib import Path

import hyperlink
import pandas as pd
import rich_click as click
import skops.io
import wandb
from rich import inspect, print
from rich.console import Console

from .artifacts import AeromancyArtifact
from .s3 import S3Client, VersionedS3Object

CLICK_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
console = Console()


def view_aeromancy_uri(
    aeromancy_uri: hyperlink.URL | hyperlink.DecodedURL,
    s3_client: S3Client,
) -> None:
    """Interactively view an Aeromancy artifact.

    Parameters
    ----------
    aeromancy_uri
        Aeromancy URI (i.e., with "aeromancy://" scheme)
    s3_client
        An S3 client to look up artifact files.
    """
    console.rule(f"URI: {aeromancy_uri}")

    s3 = VersionedS3Object.from_aeromancy_uri(aeromancy_uri)
    local_path = s3_client.fetch(s3)
    real_filename = Path(*aeromancy_uri.path)
    match real_filename.suffix:
        case ".yaml":
            subprocess.check_call(
                [  # noqa: S607
                    "bat",
                    local_path,
                    "--file-name",
                    real_filename,
                ],
            )
        case ".feather":
            artifact_df = pd.read_feather(local_path)
            print("[bold]Head:[/bold]")
            print(artifact_df.head())
            print()
            print("[bold]Described:[/bold]")
            print(artifact_df.describe())
            print()
            print("[bold]Info:[/bold]")
            artifact_df.info()
        case ".skops":
            skops.io.visualize(local_path)
        case _:
            console.log(f"No viewer for {real_filename.suffix} files.")


@click.command(context_settings=CLICK_CONTEXT_SETTINGS, no_args_is_help=True)
@click.argument("artifact_full_name")
def main(artifact_full_name: str) -> None:
    """Display information about Weights & Biases artifacts.

    ARTIFACT_FULL_NAME can be an Aeromancy URI (starts with `aeromancy://`") or
    a Weights and Biases artifact name, with or without a version.
    """
    s3_client = S3Client.from_env_variables()

    if artifact_full_name.startswith("aeromancy://") or ":" not in artifact_full_name:
        aeromancy_uri = hyperlink.parse(artifact_full_name)
        view_aeromancy_uri(aeromancy_uri, s3_client)
    else:
        wandb_api = wandb.Api()
        wandb_api_artifact = wandb_api.artifact(artifact_full_name)
        inspect(wandb_api_artifact)
        aeromancy_artifact = AeromancyArtifact.from_wandb_api_artifact(
            wandb_api_artifact,
        )
        if len(aeromancy_artifact.s3) > 1:
            console.log(f"{len(aeromancy_artifact.s3)} entries in manifest:")
        for s3 in aeromancy_artifact.s3:
            view_aeromancy_uri(s3.to_aeromancy_uri(), s3_client)


if __name__ == "__main__":
    main()
