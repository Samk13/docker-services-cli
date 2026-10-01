# SPDX-FileCopyrightText: 2020 CERN.
# SPDX-FileCopyrightText: 2024 Graz University of Technology.
# SPDX-FileCopyrightText: 2025-2026 CESNET z.s.p.o.
# SPDX-FileCopyrightText: 2026 KTH Royal Institute of Technology.
# SPDX-License-Identifier: MIT

"""Services module."""

import os
import time
from os import path
from subprocess import PIPE, Popen, check_call

import click

from .config import DOCKER_SERVICES_FILEPATH, MYSQL, RUSTFS, SERVICE_TYPES


def _run_healthcheck_command(command, verbose=False):
    """Runs a given command, returns True if it succeeds, False otherwise."""
    p = Popen(command, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate()
    output = output.decode("utf-8")
    error = error.decode("utf-8")
    if p.returncode == 0:
        if verbose:
            click.secho(output, fg="green")
        return True
    if p.returncode != 0:
        if verbose:
            click.secho(
                f"Healthcheck failed.\nOutput: {output}\nError:{error}", fg="red"
            )
        return False


def search_healthcheck(*args, **kwargs):
    """{Elastic,Open}Search healthcheck."""
    verbose = kwargs["verbose"]

    return _run_healthcheck_command(
        ["curl", "-f", "localhost:9200/_cluster/health?wait_for_status=green"], verbose
    )


def postgresql_healthcheck(*args, **kwargs):
    """Postgresql healthcheck."""
    filepath = kwargs["filepath"]
    verbose = kwargs["verbose"]

    return _run_healthcheck_command(
        [
            "docker",
            "compose",
            "--file",
            filepath,
            "exec",
            "-T",
            "postgresql",
            "bash",
            "-c",
            "pg_isready",
        ],
        verbose,
    )


def mysql_healthcheck(*args, **kwargs):
    """Mysql healthcheck."""
    filepath = kwargs["filepath"]
    verbose = kwargs["verbose"]
    password = MYSQL["CONTAINER_CONFIG_ENVIRONMENT_VARIABLES"]["MYSQL_ROOT_PASSWORD"]

    return _run_healthcheck_command(
        [
            "docker",
            "compose",
            "--file",
            filepath,
            "exec",
            "-T",
            "mysql",
            "bash",
            "-c",
            f'mysql -p{password} -e "select Version();"',
        ],
        verbose,
    )


def rabbitmq_healthcheck(*args, **kwargs):
    """Rabbitmq healthcheck."""
    filepath = kwargs["filepath"]
    verbose = kwargs["verbose"]

    return _run_healthcheck_command(
        [
            "docker",
            "compose",
            "--file",
            filepath,
            "exec",
            "-T",
            "rabbitmq",
            "bash",
            "-c",
            "rabbitmq-diagnostics check_running",
        ],
        verbose,
    )


def redis_healthcheck(*args, **kwargs):
    """Redis healthcheck."""
    filepath = kwargs["filepath"]
    verbose = kwargs["verbose"]

    return _run_healthcheck_command(
        [
            "docker",
            "compose",
            "--file",
            filepath,
            "exec",
            "-T",
            "redis",
            "bash",
            "-c",
            "redis-cli ping",
            "|",
            "grep 'PONG'",
            "&>/dev/null;",
        ],
        verbose,
    )


def _rustfs_s3_client():
    """Return a botocore S3 client for the local RustFS instance."""
    # botocore is only needed to initialize RustFS's default bucket, so it is
    # imported lazily here instead of being a hard dependency of the whole CLI.
    import botocore.session

    envvars = RUSTFS["CONTAINER_CONNECTION_ENVIRONMENT_VARIABLES"]["s3"]
    return botocore.session.get_session().create_client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL", envvars["S3_ENDPOINT_URL"]),
        aws_access_key_id=os.environ.get(
            "S3_ACCESS_KEY_ID", envvars["S3_ACCESS_KEY_ID"]
        ),
        aws_secret_access_key=os.environ.get(
            "S3_SECRET_ACCESS_KEY", envvars["S3_SECRET_ACCESS_KEY"]
        ),
    )


def _rustfs_configure_bucket_cors(client, bucket):
    """Configure local browser uploads only if the bucket has no CORS policy."""
    from botocore.exceptions import ClientError

    origins = [
        origin.strip()
        for origin in os.environ.get(
            "S3_CORS_ALLOWED_ORIGINS", RUSTFS["CORS_ALLOWED_ORIGINS"]
        ).split(",")
        if origin.strip()
    ]
    if not origins:
        return

    try:
        client.get_bucket_cors(Bucket=bucket)
        return
    except ClientError as error:
        if error.response["Error"]["Code"] != "NoSuchCORSConfiguration":
            raise

    client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": origins,
                    "AllowedMethods": ["GET", "HEAD", "PUT", "POST", "DELETE"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )


def rustfs_create_default_bucket(bucket="default", verbose=False):
    """Create the RustFS bucket used by default by Invenio's S3 storage.

    Unlike MinIO, RustFS does not auto-create buckets from directories present
    on its data volume at startup, so this replicates that behaviour. Configure
    CORS for local browser uploads without replacing an existing bucket policy.
    """
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        click.secho(
            "botocore is required to initialize the RustFS default bucket. "
            "Install it with `pip install docker-services-cli[s3]`.",
            fg="red",
        )
        exit(1)

    client = _rustfs_s3_client()

    try:
        client.create_bucket(Bucket=bucket)
    except client.exceptions.BucketAlreadyOwnedByYou:
        # Continue with CORS configuration for an existing owned bucket.
        pass
    except (ClientError, BotoCoreError) as error:
        if verbose:
            click.secho(f"Could not create default bucket: {error}", fg="red")
        return False

    try:
        _rustfs_configure_bucket_cors(client, bucket)
        return True
    except (ClientError, BotoCoreError) as error:
        if verbose:
            click.secho(f"Could not configure default bucket CORS: {error}", fg="red")
        return False


def rustfs_healthcheck(*args, **kwargs):
    """Check RustFS health."""
    verbose = kwargs["verbose"]

    if not _run_healthcheck_command(
        ["curl", "-f", "http://localhost:9000/health"], verbose
    ):
        return False

    return rustfs_create_default_bucket(verbose=verbose)


HEALTHCHECKS = {
    "elasticsearch": search_healthcheck,
    "opensearch": search_healthcheck,
    "postgresql": postgresql_healthcheck,
    "mysql": mysql_healthcheck,
    "rabbitmq": rabbitmq_healthcheck,
    "redis": redis_healthcheck,
    "rustfs": rustfs_healthcheck,
}
"""Health check functions module path, as string."""


def wait_for_services(
    services, filepath=DOCKER_SERVICES_FILEPATH, max_retries=6, verbose=False
):
    """Wait for services to be up.

    It performs configured healthchecks in a serial fashion, following the
    order given in the ``up`` command. If the services is an empty list, to be
    compliant with `docker compose` it will perform the healthchecks of all the
    services.
    """
    if len(services) == 0:
        services = HEALTHCHECKS.keys()

    for service in services:
        exp_backoff_time = 2
        try_ = 1
        # Using plain __import__ to avoid depending on invenio-base
        check = HEALTHCHECKS[service]
        ready = check(filepath=filepath, verbose=verbose)
        while not ready and try_ < max_retries:
            click.secho(
                f"{service} not ready at {try_} retries, waiting {exp_backoff_time}s",
                fg="yellow",
            )
            try_ += 1
            time.sleep(exp_backoff_time)
            exp_backoff_time *= 2
            ready = check(filepath=filepath, verbose=verbose)

        if not ready:
            click.secho(f"Unable to boot up {service}", fg="red")
            exit(1)
        else:
            click.secho(f"{service} up and running!", fg="green")


def services_up(
    services, filepath=DOCKER_SERVICES_FILEPATH, wait=True, retries=6, verbose=False
):
    """Start the given services up.

    docker compose is smart about not rebuilding an image if
    there is no need to, so --build is not a slow default. In addition
    ``--detach`` is not supported in 1.17.0 or previous.
    """
    services = services or [
        service for _, services in SERVICE_TYPES.items() for service in services
    ]
    if not path.exists(filepath):
        click.secho(
            f"Filepath {filepath} for docker-services.yml file does not exist.",
            fg="red",
        )
        exit(1)

    command = ["docker", "compose", "--file", filepath, "up", "-d"]
    command.extend(services)

    check_call(command)
    if wait:
        wait_for_services(services, filepath, max_retries=retries, verbose=verbose)


def services_down(filepath=DOCKER_SERVICES_FILEPATH):
    """Stops the given services.

    It does not requries the services. It stops containers and removes
    containers, networks, volumes, and images created by ``up``.
    """
    command = ["docker", "compose", "--file", filepath, "down", "--volumes"]

    check_call(command)
